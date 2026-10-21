"""The dance-school tailoring of the second-brain template: the templates a
generic Latin/social dance school needs, the drafts-only marketing starter,
the private business-profile onboarding step and the privacy wording.

Every specific in these templates is a placeholder (`Studio A`,
`Instructor 1`, `<town>`, `<amount>`, https://example.invalid); the
placeholder test fails on a planted price, link, handle, phone number or
founding year. `KIT_TAILORING_ROOT` points the suite at another copy of the
kit. Stdlib only, Python 3.9+.
"""

import os
import re
import unittest

ROOT = os.environ.get("KIT_TAILORING_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DANCE = "second-brain/dance-school"
MARKETING_RULES = DANCE + "/marketing/README-drafts-only.md"
COMMS_RULES = DANCE + "/comms/README-roster-lives-elsewhere.md"
CHECKLIST = "onboarding/setup-checklist.md"

# Item 1 (templates and examples) and item 2 (marketing starter and social).
REQUIRED = {
    "schedule": DANCE + "/classes-schedule/term-schedule-example.md",
    "group card": DANCE + "/classes-schedule/class-template.md",
    "instructors": DANCE + "/classes-schedule/instructor-roster-template.md",
    "launch": DANCE + "/marketing/campaigns/new-group-launch-campaign.md",
    "trial funnel": DANCE + "/marketing/campaigns/trial-class-funnel.md",
    "social night": DANCE + "/events-recitals/social-night-event-plan.md",
    "workshop": DANCE + "/events-recitals/workshop-module-plan.md",
    "pricing": DANCE + "/finances/pass-pricing-table-template.md",
    "bilingual": DANCE + "/marketing/social/bilingual-post-template.md",
    "parents": DANCE + "/comms/parent-update-template.md",
    "adults": DANCE + "/comms/adult-group-update-template.md",
    "competition": DANCE + "/marketing/social/competition-team-news-template.md",
    "reviews": DANCE + "/marketing/reviews-testimonials-template.md",
    "consent": DANCE + "/admin/consent-record-template.md",
    "calendar": DANCE + "/marketing/social/content-calendar-example.md",
    "instagram": DANCE + "/marketing/social/instagram-post-draft-example.md",
    "facebook post": DANCE + "/marketing/social/facebook-post-template.md",
    "facebook event": DANCE + "/marketing/social/facebook-event-template.md",
    "whatsapp": DANCE + "/marketing/social/whatsapp-broadcast-template.md",
    "targeting": DANCE + "/marketing/targeting-per-location.md",
    "metrics": DANCE + "/marketing/campaign-metrics-template.md",
    "rules": MARKETING_RULES,
}

# A post or broadcast draft: a human approves it, minors are excluded by default.
POST_TEMPLATES = ("bilingual", "competition", "instagram", "facebook post", "facebook event", "whatsapp")

# Shapes a real business detail would take. A link must be https://example.invalid.
FORBIDDEN = {
    "link": re.compile(r"\bhttps?://(?!example\.invalid\b)|\bwww\.", re.I),
    "price": re.compile(r"[€$£]\s?\d|\b\d+(?:[.,]\d+)?\s?(?:eur|euro|euros|usd|gbp|ron|lei|chf|pln)\b", re.I),
    "handle": re.compile(r"(?<![\w.<])@[A-Za-z0-9_][A-Za-z0-9_.]{2,}"),
    "phone": re.compile(r"(?<![\w-])\+?\d[\d ()./-]{7,}\d(?![\w-])"),
    "founding year": re.compile(r"\b(?:since|founded|established|est\.)\s+(?:in\s+)?(?:19|20)\d\d\b", re.I),
}
FRONT_MATTER_ID_RE = re.compile(r"^(id|created): ")


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def exists(rel):
    return os.path.isfile(os.path.join(ROOT, rel))


def md_files(rel):
    out = []
    for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, rel)):
        dirnames.sort()
        for name in sorted(filenames):
            if name.endswith(".md"):
                out.append(os.path.relpath(os.path.join(dirpath, name), ROOT).replace(os.sep, "/"))
    return out


def placeholder_findings(text):
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        if FRONT_MATTER_ID_RE.match(line):
            continue
        for label, regex in FORBIDDEN.items():
            if regex.search(line):
                found.append("%d %s" % (number, label))
    return found


def phase_section(text, number):
    m = re.search(r"(?ms)^## Phase %d:.*?(?=^## )" % number, text)
    return m.group(0) if m else ""


class TemplatesTest(unittest.TestCase):
    def test_required_templates_ship(self):
        for label, rel in REQUIRED.items():
            with self.subTest(template=label):
                self.assertTrue(exists(rel), rel)

    def test_templates_are_placeholders_only(self):
        files = md_files(DANCE) + ["second-brain/BUSINESS-PROFILE.md", "second-brain/ROUTER.md"]
        found = []
        for rel in files:
            if exists(rel):
                found += ["%s:%s" % (rel, f) for f in placeholder_findings(read(rel))]
        self.assertEqual(found, [])

    def test_the_placeholder_check_catches_planted_values(self):
        planted = {
            "link": "See https://studio" + ".example.com/classes",
            "price": "Single class: 12 " + "EUR",
            "handle": "Follow @" + "salsa_studio_town",
            "phone": "Call +00 " + "000 000 000",
            "founding year": "Dancing since " + "2011",
        }
        for label, line in planted.items():
            with self.subTest(planted=label):
                self.assertEqual(placeholder_findings(line), ["1 " + label])
        self.assertEqual(placeholder_findings("Link: https://example.invalid/classes, <amount>, @<handle>"), [])

    def test_studios_and_instructors_are_placeholders(self):
        schedule = read(REQUIRED["schedule"])
        for name in ("Studio A", "Studio B", "Instructor 1"):
            with self.subTest(name=name):
                self.assertIn(name, schedule)
        self.assertIn("Instructor 1", read(REQUIRED["instructors"]))
        self.assertIn("placeholder", read(REQUIRED["instructors"]).lower())

    def test_pricing_table_covers_every_pass(self):
        text = read(REQUIRED["pricing"]).lower()
        for item in ("single", "couple", "4-session", "8-session", "drop-in", "employer-benefit", "<amount>"):
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_launch_campaign_and_trial_funnel(self):
        launch = read(REQUIRED["launch"]).lower()
        for item in ("first-month", "refund guarantee", "optional"):
            with self.subTest(launch=item):
                self.assertIn(item, launch)
        funnel = read(REQUIRED["trial funnel"]).lower()
        for item in ("trial", "follow-up", "pass"):
            with self.subTest(funnel=item):
                self.assertIn(item, funnel)

    def test_bilingual_post_has_an_english_group_option(self):
        text = read(REQUIRED["bilingual"])
        self.assertIn("<local language>", text)
        self.assertIn("English", text)
        self.assertIn("English-language group", text)

    def test_parent_comms_are_separate_from_adult_comms(self):
        parents = read(REQUIRED["parents"]).lower()
        adults = read(REQUIRED["adults"]).lower()
        self.assertIn("kids/teens", parents)
        self.assertIn("parents", parents)
        self.assertIn("adult groups", adults)
        self.assertNotIn("<parent", adults, "an adult message never addresses parents")
        self.assertNotIn("kids/teens", adults.replace("kids/teens news goes in", ""))
        self.assertIn("kept separate", read(COMMS_RULES).lower())

    def test_consent_records_for_reviews_and_minors(self):
        reviews = read(REQUIRED["reviews"]).lower()
        self.assertIn("consent record", reviews)
        consent = read(REQUIRED["consent"]).lower()
        for item in ("guardian", "written consent", "withdrawn", "separate"):
            with self.subTest(consent=item):
                self.assertIn(item, consent)


class MarketingRulesTest(unittest.TestCase):
    def test_rules_note_is_drafts_only(self):
        text = read(MARKETING_RULES).lower()
        for phrase in ("drafts only", "a human approves every post", "no auto-posting", "no scheduling",
                       "no tokens or api keys", "guardian's written consent",
                       "check each platform's current terms before posting"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_every_post_template_needs_approval_and_consent(self):
        for label in POST_TEMPLATES:
            text = read(REQUIRED[label])
            with self.subTest(template=label):
                self.assertIn("Approved by", text)
                self.assertIn("guardian's written consent", text)
                self.assertRegex(text, r'(?m)^status: "(draft|template)"$')

    def test_calendar_follows_the_term_cycle(self):
        text = read(REQUIRED["calendar"]).lower()
        for item in ("autumn intake", "january intake", "new-group launch", "social", "festival", "summer"):
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_targeting_and_metrics(self):
        targeting = read(REQUIRED["targeting"])
        self.assertIn("Studio A", targeting)
        self.assertIn("<town>", targeting)
        metrics = read(REQUIRED["metrics"]).lower()
        for item in ("trial signups", "trial-to-pass conversion", "retention per group"):
            with self.subTest(metric=item):
                self.assertIn(item, metrics)


class ProfileOnboardingTest(unittest.TestCase):
    def test_agents_phase_3_has_the_profile_checkpoint(self):
        section = phase_section(read("AGENTS.md"), 3)
        self.assertIn("**CHECKPOINT 3b:**", section)
        write = [l for l in section.splitlines() if l.startswith("- After OK 3b:")]
        self.assertEqual(len(write), 1)
        for phrase in ("private/business-profile.yaml", ".gitignore"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, write[0])
        lower = section.lower()
        for phrase in ("your own website and social accounts", "only with your ok",
                       "tools/business_profile.py check", "never goes into git"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, lower)

    def test_checklist_has_the_profile_step(self):
        text = read(CHECKLIST)
        self.assertIn("business profile", text.lower())
        self.assertIn("checkpoint 3b", text)
        self.assertIn("private/business-profile.yaml", text)
        self.assertIn("tools/business_profile.py check", text)

    def test_readme_says_the_profile_never_goes_into_git(self):
        self.assertIn("never goes into git or a public fork", read("README.md"))


class PrivacyWordingTest(unittest.TestCase):
    def test_conditional_wording_for_adults_and_children(self):
        for rel in ("README.md", "AGENTS.md", CHECKLIST, MARKETING_RULES, COMMS_RULES):
            text = read(rel).lower()
            with self.subTest(file=rel):
                self.assertIn("if you work with children", text)
                self.assertIn("adults and children", text)

    def test_no_mostly_minors_anywhere(self):
        phrase = "mostly " + "minors"
        found = []
        for dirpath, dirnames, filenames in os.walk(ROOT):
            dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__")]
            for name in filenames:
                path = os.path.join(dirpath, name)
                try:
                    with open(path, encoding="utf-8") as fh:
                        if phrase in fh.read():
                            found.append(os.path.relpath(path, ROOT))
                except (UnicodeDecodeError, OSError):
                    continue
        self.assertEqual(found, [])

    def test_minors_are_excluded_by_default(self):
        checklist = read(CHECKLIST).split("## Privacy")[1].lower()
        for phrase in ("guardian's written consent", "separate consent record", "no names or faces of minors"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, checklist)


if __name__ == "__main__":
    unittest.main()
