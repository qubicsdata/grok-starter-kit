import unittest

from folio.resolve import ResolveError, resolve

ITEMS = [
    {"id": "aaaa111122223333", "name": "Cloud foundation"},
    {"id": "aaaa999922223333", "name": "Data platform"},
    {"id": "bbbb111122223333", "name": "cloud FOUNDATION", "project": "Other"},
]


class ResolveTests(unittest.TestCase):
    def test_exact_id_wins(self):
        self.assertEqual(resolve(ITEMS, "bbbb111122223333", "project")["name"], "cloud FOUNDATION")

    def test_unique_name_is_case_insensitive(self):
        self.assertEqual(resolve(ITEMS, "data PLATFORM", "project")["id"], "aaaa999922223333")

    def test_duplicate_names_are_ambiguous_with_candidates(self):
        with self.assertRaises(ResolveError) as error:
            resolve(ITEMS, "Cloud Foundation", "project")
        self.assertEqual(error.exception.code, "AMBIGUOUS_REFERENCE")
        self.assertEqual({c["id"] for c in error.exception.candidates}, {"aaaa111122223333", "bbbb111122223333"})
        self.assertIn({"id": "bbbb111122223333", "name": "cloud FOUNDATION", "project": "Other"}, error.exception.candidates)

    def test_id_prefix_needs_four_hex_characters_and_uniqueness(self):
        self.assertEqual(resolve(ITEMS, "bbbb", "project")["id"], "bbbb111122223333")
        with self.assertRaises(ResolveError) as error:
            resolve(ITEMS, "aaaa", "project")
        self.assertEqual(error.exception.code, "AMBIGUOUS_REFERENCE")
        with self.assertRaises(ResolveError) as error:
            resolve(ITEMS, "bbb", "project")
        self.assertEqual(error.exception.code, "NOT_FOUND")

    def test_custom_label_and_not_found_message(self):
        tasks = [{"id": "cccc111122223333", "title": "Design review"}]
        self.assertEqual(resolve(tasks, "design review", "task", "title")["id"], "cccc111122223333")
        with self.assertRaises(ResolveError) as error:
            resolve(tasks, "Missing", "task", "title")
        self.assertEqual(error.exception.code, "NOT_FOUND")
        self.assertIn("task", error.exception.message)


if __name__ == "__main__":
    unittest.main()
