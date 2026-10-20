"""Golden: the attention rule, "a blocked or overdue task, counted once" (README.md:97).

Overdue means unfinished with a due date strictly before today. The rule is implemented three times
since WP-6 cut `folio tasks list --attention`: folio/brief.py:57 (brief ranking), folio/cli.py (status
rollups, `summarize`) and folio/static/app.js (browser). They must agree on the same matrix.
"""

import re
import unittest
from pathlib import Path
from unittest.mock import patch

from folio import brief, cli

from .fixtures import TASKS, project, state
from .golden import TODAY, FixedDate, assert_golden

APP_JS = Path(cli.__file__).with_name("static") / "app.js"


class AttentionGoldenTests(unittest.TestCase):
    def test_status_rollup_and_attention_items(self):
        result = {"default": cli.summarize(state(), False, TODAY), "with_archived": cli.summarize(state(), True, TODAY)}
        assert_golden(self, "attention_status", result)

    def test_tasks_list_command_is_gone(self):
        """WP-6: the CLI task listing (and its golden) left with the task CRUD group; Backlog lists tasks."""
        self.assertFalse(hasattr(cli, "cmd_tasks_list"))

    @patch("folio.brief.date", FixedDate)
    def test_every_implementation_agrees_on_the_matrix(self):
        expected = {"0000000000000001": "blocked", "0000000000000002": "overdue", "0000000000000007": "blocked",
                    "0000000000000008": "overdue"}
        summary = cli.summarize({"clients": state()["clients"], "projects": [project()]}, False, TODAY)
        self.assertEqual({item["task_id"]: item["reason"] for item in summary["attention_items"]}, expected)
        self.assertEqual(summary["totals"]["attention"], len(expected))
        # The brief ranks attention tasks ahead of others at equal relevance (brief.py:57-58).
        ranked = [r["source"] for r in brief.brief_for_project(project(), "", 40000)["records"] if r["kind"] == "task"]
        self.assertEqual(set(ranked[:len(expected)]), {f"task:{task_id}" for task_id in expected})
        self.assertEqual(len(TASKS) - len(expected), 4)

    def test_browser_rule_is_unchanged(self):
        source = APP_JS.read_text(encoding="utf-8")
        rules = [line for line in source.splitlines() if re.match(r"const (overdue|attention) = task =>", line)]
        self.assertEqual(rules, [
            "const overdue = task => task.status !== 'done' && task.due_date && task.due_date < localToday();",
            "const attention = task => task.status !== 'done' && (task.status === 'blocked' || overdue(task));",
        ])


if __name__ == "__main__":
    unittest.main()
