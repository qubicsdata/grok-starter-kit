# Private business profile (template keys)

The business profile holds what your Grok Bot learns about your school from your own website and social accounts: its name, studios, styles, schedule, prices and channels. The templates in `dance-school/` read their values from it (a key in double braces, such as `{{studio.1.name}}`), so you write those facts once.

- **Built only with your OK** (`AGENTS.md` checkpoint 3b): your Grok Bot reads only the site and accounts you name, never logs in, shows you the whole profile with `unknown` for anything it could not see, and saves it after your OK.
- **Location:** `dance-school/private/business-profile.yaml` in your second brain (`<channel>/private/business-profile.yaml` for another channel). Nothing of the kit ships under any `private/` folder.
- **It never goes into git or a public fork.** The kit's `.gitignore` ignores every `private/` folder and every `business-profile*.yaml`. If your second brain is a git repo of its own, add the same two lines to its `.gitignore`.
- **Refuse-to-commit check:** `python3 tools/business_profile.py check` (run from your kit folder against the repo you are in, or with `--repo <folder>`) fails when the staged changes hold a file in a `private/` folder, a `business-profile*.yaml` file, or any file with the profile's marker line, whatever its name. `--all` checks every tracked file instead; run it before you make a fork public. It prints paths only, never contents.
- **Pre-commit hook (optional, your OK first):** save these two lines as `.git/hooks/pre-commit` in your notes repo and make the file executable (`chmod +x`); git then refuses every commit the check refuses:

  ```
  #!/bin/sh
  exec python3 "<your kit folder>/tools/business_profile.py" check
  ```

## Commands

| Command | What it does |
|---|---|
| `python3 tools/business_profile.py draft <saved-site-folder>` | reads pages you saved from your own website (`*.html`, local files only; it never fetches anything) and prints a draft profile; anything the pages do not declare is `unknown` |
| `python3 tools/business_profile.py fill --profile <profile> <template>` | prints the template with every double-brace key (such as `{{school.name}}`) filled; a key that is missing or `unknown` stays as it is and is named on stderr (exit 1) |
| `python3 tools/business_profile.py check [--repo <folder>] [--all]` | the refuse-to-commit check above (exit 1 when it refuses) |

None of them writes a file: your Grok Bot shows the output and saves a draft note only after your OK.

## Format

One `key: "value"` per line, `#` for comments. Keys are lowercase with dots; put every value in double quotes and keep double quotes out of the value. The first line is the marker the check looks for: `profile.private: true`. A filled template keeps its `<...>` placeholders (`<date>`, `<amount>`): you fill those per post.

## Keys

Every example is a placeholder. The number of studios is yours: add `studio.3.name` and so on for a third studio.

| Key | Example value | What it is |
|---|---|---|
| `profile.private` | `true` | the marker; a file holding this line is never committed |
| `channel` | `dance-school` | the second-brain channel of the profile |
| `school.name` | `<school name>` | your school's name as you use it in posts |
| `school.website` | `https://example.invalid` | your own website |
| `school.local_language` | `<local language>` | the first language of your posts |
| `school.second_language` | `English` | the second language of bilingual posts |
| `studios.count` | `<n>` | how many studios or locations you teach in |
| `studio.1.name` | `Studio A` | first studio |
| `studio.1.town` | `<town>` | its town or district |
| `studio.1.address` | `<address>` | its public address |
| `studio.2.name` | `Studio B` | second studio |
| `studio.2.town` | `<town>` | its town or district |
| `studio.2.address` | `<address>` | its public address |
| `styles` | `salsa, bachata, kizomba, zouk, ladies styling` | the styles you teach |
| `groups.adults` | `<adult groups and levels>` | adult groups, beginners to advanced |
| `groups.seniors` | `<seniors group, if you run one>` | seniors group |
| `groups.kids` | `<kids groups by age band>` | kids groups, for example by school year |
| `groups.teens` | `<teens groups by age band>` | teens groups |
| `groups.english` | `<English-language group, if you run one>` | a group taught in English |
| `term.autumn_start` | `<date>` | first week of the autumn intake |
| `term.january_start` | `<date>` | first week of the January intake |
| `schedule.opening_hours` | `<days and hours per studio>` | the short form; the timetable lives in `dance-school/classes-schedule/` |
| `price.currency` | `<currency>` | the currency of your prices |
| `price.single` | `<amount>` | a single class |
| `price.couple` | `<amount>` | a couple pass |
| `price.pass_4` | `<amount>` | a 4-session pass |
| `price.pass_8` | `<amount>` | an 8-session pass |
| `price.drop_in` | `<amount>` | a drop-in class |
| `price.benefit_platforms` | `<employer-benefit platforms you accept>` | employer-benefit platforms |
| `offer.first_month` | `<first-month offer for new groups>` | the launch offer of a new group |
| `offer.refund_guarantee` | `<refund guarantee terms, or none>` | an optional refund guarantee |
| `social.instagram` | `https://example.invalid/<instagram-account>` | your Instagram account |
| `social.facebook` | `https://example.invalid/<facebook-page>` | your Facebook page |
| `social.whatsapp_broadcast` | `<broadcast list name>` | the WhatsApp broadcast list you send from (sending stays yours) |

`draft` fills what your pages declare in schema.org markup: the school's name, website, studios (`location`), styles (`knowsAbout`), opening hours, prices of offers named single, couple, 4 or 8 sessions and drop-in, and the Instagram and Facebook links (`sameAs`). Everything else starts as `unknown` for you to answer at checkpoint 3b.
