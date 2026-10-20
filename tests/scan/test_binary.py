"""Image files known by their magic bytes: counted as `BINARY <n>`, never `SKIP binary`.

A NUL-bearing file is content-skipped. When it starts with the magic of a PNG,
JPEG, GIF or WebP image it is counted on a `BINARY <n>` line (not a finding,
not part of TOTAL); any other NUL-bearing file still gives `SKIP binary`,
which `tools/ci_local.py --release` turns into a failure. The file name never
decides: there is no extension check, no path allow-list and no
`--allow-binary` flag. Every header is built at run time.
"""

import argparse
import importlib.util
import io
import os
import unittest

try:
    from tests.scan import support
except ImportError:  # run with: python3 -m unittest discover -s tests/scan
    import support

P = support.planted()
needs_git = unittest.skipUnless(support.git_available(), "git not installed")

CI_LOCAL = os.path.join(support.KIT_ROOT, "tools", "ci_local.py")


def body():
    """Image-like payload after the magic: NUL bytes and a planted value that must not be counted."""
    return b"\x00" * 32 + P["email"].encode("ascii") + b"\x00\xff\xfe" * 40


def png():
    return bytes.fromhex("89504e47" + "0d0a1a0a") + body()


def jpeg():
    return bytes.fromhex("ffd8" + "ffe0") + body()


def gif87a():
    return ("GIF" + "87a").encode("ascii") + body()


def gif89a():
    return ("GIF" + "89a").encode("ascii") + body()


def webp():
    payload = body()
    size = (4 + len(payload)).to_bytes(4, "little")
    return ("RI" + "FF").encode("ascii") + size + ("WE" + "BP").encode("ascii") + payload


IMAGES = {
    "png": ("img/icon.png", png),
    "jpeg": ("img/photo.jpg", jpeg),
    "gif87a": ("img/old.gif", gif87a),
    "gif89a": ("img/anim.gif", gif89a),
    "webp": ("img/pic.webp", webp),
}
FOUR_KINDS = ("png", "jpeg", "gif89a", "webp")


def unknown_binary():
    """NUL-bearing bytes with no known image magic."""
    return ("KIT" + "BLOB").encode("ascii") + b"\x00\x01\x02" * 20


def plant_four_kinds(tree):
    for kind in FOUR_KINDS:
        rel, build = IMAGES[kind]
        tree.write(rel, build())


class ImageMagicTest(support.ScanTestCase):
    def test_each_image_format_is_binary_not_skip(self):
        for kind, (rel, build) in sorted(IMAGES.items()):
            with self.subTest(kind=kind):
                tree = support.Tree()
                self.addCleanup(tree.cleanup)
                tree.write(rel, build())
                result = self.scan(tree.root)
                self.assert_clean(result)
                self.assertEqual(result.binary, 1, "an image should count as BINARY 1")
                self.assertNotIn("binary", result.skips)

    def test_image_content_is_not_scanned(self):
        self.tree.write("img/icon.png", png())
        result = self.scan_tree()
        self.assert_clean(result)
        self.assertEqual(result.count("EMAIL"), 0)

    def test_four_kinds_are_counted_together(self):
        plant_four_kinds(self.tree)
        result = self.scan_tree()
        self.assert_clean(result)
        self.assertEqual(result.binary, 4)
        self.assertNotIn("binary", result.skips)

    def test_image_path_rules_still_apply(self):
        self.tree.write("img/" + P["real_name"], png())
        result = self.scan_tree()
        self.assert_single(result, "CAPTURE")
        self.assertEqual(result.binary, 1)


class NotAnImageTest(support.ScanTestCase):
    def test_nul_file_without_known_magic_still_skips(self):
        self.tree.write("data/blob.txt", unknown_binary())
        result = self.scan_tree()
        self.assert_clean(result)
        self.assertIn("binary", result.skips)
        self.assertEqual(result.binary, 0)

    def test_png_extension_without_png_magic_is_not_an_image(self):
        self.tree.write("img/fake.png", unknown_binary())
        result = self.scan_tree()
        self.assertIn("binary", result.skips)
        self.assertEqual(result.binary, 0)

    def test_short_png_signature_is_not_an_image(self):
        self.tree.write("img/short.png", bytes.fromhex("89504e47") + b"\x00" * 16)
        result = self.scan_tree()
        self.assertIn("binary", result.skips)
        self.assertEqual(result.binary, 0)

    def test_riff_without_webp_tag_is_not_an_image(self):
        payload = b"\x00" * 16
        data = ("RI" + "FF").encode("ascii") + (4 + len(payload)).to_bytes(4, "little") + ("WA" + "VE").encode("ascii") + payload
        self.tree.write("media/sound.webp", data)
        result = self.scan_tree()
        self.assertIn("binary", result.skips)
        self.assertEqual(result.binary, 0)

    def test_image_and_unknown_binary_report_both(self):
        self.tree.write("img/icon.png", png())
        self.tree.write("data/blob.bin", unknown_binary())
        result = self.scan_tree()
        self.assert_clean(result)
        self.assertEqual(result.binary, 1)
        self.assertIn("binary", result.skips)

    def test_text_with_image_magic_is_still_content_scanned(self):
        # No NUL byte: decoded as text like any other file, so the magic grants no skip.
        self.tree.write("notes/gif.md", ("GIF" + "89a " + P["email"] + "\n").encode("ascii"))
        result = self.scan_tree()
        self.assert_single(result, "EMAIL")
        self.assertEqual(result.binary, 0)


class BinaryOutputTest(support.ScanTestCase):
    def test_binary_line_is_codes_only_and_total_stays_last(self):
        plant_four_kinds(self.tree)
        self.tree.write("data/blob.bin", unknown_binary())
        result = self.scan_tree()
        lines = result.stdout.splitlines()
        self.assertEqual(result.bad_lines, [])
        self.assertIn("BINARY 4", lines)
        self.assertEqual(lines[-1], "TOTAL 0")
        self.assertLess(lines.index("BINARY 4"), lines.index("SKIP binary"))
        for line in lines:
            self.assertRegex(line, r"^(?:[A-Z]+ \d+|SKIP [a-z]+)$")
        self.assertEqual(result.stderr, "")
        self.assert_no_leak(result, [P["email"], "icon.png", "photo.jpg", "anim.gif", "pic.webp",
                                     "blob.bin", self.tree.root])

    def test_no_binary_line_without_images(self):
        self.tree.write("README.md", "clean\n")
        result = self.scan_tree()
        self.assertNotIn("BINARY", result.stdout)

    def test_allow_binary_is_an_unknown_option(self):
        plant_four_kinds(self.tree)
        for extra in (["--allow-binary"], ["--allow-binary", "img/*.png"], ["--allow-binary=img/*.png"]):
            with self.subTest(extra=extra):
                result = self.scan_tree(*extra)
                self.assertEqual(result.code, 2)
                self.assertIsNone(result.total)
                self.assertEqual(result.counts, {})

    def test_help_offers_no_binary_allow_list(self):
        result = self.scan("--help")
        self.assertEqual(result.code, 0)
        self.assertNotIn("allow-binary", result.stdout)


@needs_git
class HistoryImageTest(support.ScanTestCase):
    def setUp(self):
        super().setUp()
        support.init_repo(self.tree)

    def scan_history(self):
        return self.scan_tree("--history", "--allowed-identity", support.ALLOWED_IDENTITY)

    def test_committed_image_is_binary_once(self):
        self.tree.write("img/icon.png", png())
        support.commit_all(self.tree, "add icon")
        result = self.scan_history()
        self.assert_clean(result)
        self.assertEqual(result.binary, 1, "the work-tree copy of a scanned blob is not counted twice")
        self.assertNotIn("binary", result.skips)

    def test_unknown_binary_in_history_still_skips(self):
        self.tree.write("data/blob.bin", unknown_binary())
        support.commit_all(self.tree, "add blob")
        self.tree.write("data/blob.bin", "now text\n")
        support.commit_all(self.tree, "replace blob")
        result = self.scan_history()
        self.assert_clean(result)
        self.assertIn("binary", result.skips)
        self.assertEqual(result.binary, 0)


def load_ci_local():
    spec = importlib.util.spec_from_file_location("ci_local_under_test", CI_LOCAL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.CLEAN_SCAN = support.CLEAN_SCAN  # follow KIT_CLEAN_SCAN like the rest of the suite
    return module


class ReleaseModeTest(support.ScanTestCase):
    """`ci_local.py --release` over a temp tree: images pass, any other binary still fails."""

    def setUp(self):
        super().setUp()
        self.ci = load_ci_local()
        outside = support.Tree()
        self.addCleanup(outside.cleanup)
        self.terms = outside.write("terms.tsv", "zq" + "xfixtureterm" + "\n")

    def run_release(self):
        root = self.tree.root

        def step(ctx):
            sub = argparse.Namespace(**vars(ctx))
            sub.root = root
            result = self.ci.step_clean_scan(sub)
            ctx.failure_output = sub.failure_output
            return result

        out = io.StringIO()
        code = self.ci.main(["--release", "--terms-file", self.terms],
                            steps=[self.ci.Step("clean-scan", step)], out=out)
        return code, out.getvalue()

    def test_four_image_kinds_at_total_zero_pass_release(self):
        plant_four_kinds(self.tree)
        self.tree.write("README.md", "clean\n")
        code, output = self.run_release()
        self.assertEqual(code, 0, output)
        self.assertRegex(output, r"(?m)^STEP clean-scan: PASS \(TOTAL 0")
        self.assertNotIn(self.tree.root, output)

    def test_unknown_binary_still_fails_release(self):
        plant_four_kinds(self.tree)
        self.tree.write("data/blob.txt", unknown_binary())
        code, output = self.run_release()
        self.assertEqual(code, 1)
        self.assertRegex(output, r"(?m)^STEP clean-scan: FAIL \(release forbids SKIP: TOTAL 0.*not run: binary\)$")


if __name__ == "__main__":
    unittest.main()
