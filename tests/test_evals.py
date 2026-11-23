"""Deterministic grader for evals/ (no agent is ever launched)."""
import importlib.util
import re
import sys
import tempfile
import unittest
from pathlib import Path

EVALS = Path(__file__).resolve().parent.parent / "evals"
spec = importlib.util.spec_from_file_location("evals_run", EVALS / "run.py")
run = importlib.util.module_from_spec(spec)
sys.modules["evals_run"] = run
spec.loader.exec_module(run)

SUBS = {"@PM@": "t1", "@REVIEWER@": "ao-demo-technical-aaaaaa", "@WORKER@": "ao-demo-backend-wo-bbbbbb"}


class EvalGraderTest(unittest.TestCase):
    def scenario(self, name):
        return next(s for s in run.load_scenarios() if s["name"] == name)

    def test_scenarios_are_well_formed(self):
        scenarios = run.load_scenarios()
        self.assertGreaterEqual(len(scenarios), 6)
        for s in scenarios:
            self.assertTrue(s["must_match"] and s["must_not_match"], s["name"])
            self.assertTrue(s["role"] in ("pm", "reviewer", "worker"))
            for skill in s["skills"]:
                self.assertTrue((run.SKILLS / skill / "SKILL.md").is_file())
            for rx in s["must_match"] + s["must_not_match"]:
                re.compile(rx)

    def test_grade_pass_and_fail(self):
        s = self.scenario("reviewer_blocked_worker_no_hc_keys")
        good = "```text\nWRITE .ai/inbox/20260101T000000Z-T-1-blocked.md: blocked, waiting on pytest -q tests/\nRUN: hc send t1 ESCALATION blocked T-1\n```"
        bad = "```text\nRUN: hc keys ao-demo-backend-wo-bbbbbb enter\nWRITE .ai/inbox/x.md: blocked pytest -q tests/\n```"
        self.assertTrue(run.grade(good, s, SUBS)["pass"])
        result = run.grade(bad, s, SUBS)
        self.assertFalse(result["pass"])
        self.assertTrue(result["forbidden"])

    def test_only_fenced_block_is_graded(self):
        s = self.scenario("reviewer_blocked_worker_no_hc_keys")
        reply = ("I will never run hc keys here.\n```text\nWRITE .ai/inbox/a.md: blocked on pytest -q tests/\n```")
        self.assertTrue(run.grade(reply, s, SUBS)["pass"])

    def test_missing_required_message_fails(self):
        s = self.scenario("reviewer_failing_tests_goes_to_worker")
        result = run.grade("```text\nSEND nobody: looks fine\n```", s, SUBS)
        self.assertFalse(result["pass"])
        self.assertEqual(len(result["missing"]), 2)

    def test_pm_wait_flags_are_forbidden(self):
        s = self.scenario("pm_after_dispatch_does_not_wait")
        ok = "```text\nRUN: agentorg team send backend-worker 'T-5 ...'\nSEND owner: dispatched\nEND TURN\n```"
        bad = ok.replace("T-5 ...'", "T-5 ...' --wait")
        self.assertTrue(run.grade(ok, s, SUBS)["pass"])
        self.assertFalse(run.grade(bad, s, SUBS)["pass"])

    def test_prompt_contains_skill_role_and_situation(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj, doc, subs = run.project_context(Path(tmp))
            prompt = run.build_prompt(self.scenario("worker_asked_to_edit_other_worktree"), proj, doc, subs)
        self.assertIn("name: agent-org-engineering", prompt)
        self.assertIn(subs["@REVIEWER@"], prompt)
        self.assertNotIn("@REVIEWER@", prompt)
        self.assertIn("hc keys to a blocked agent is forbidden", prompt)


if __name__ == "__main__":
    unittest.main()
