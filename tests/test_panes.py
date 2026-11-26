"""Pane arrangement for `team up --apply`: everything is mocked; no real herdr-app is ever called."""
import contextlib
import io
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from agentorg import runtime

ROLES = [{"id": "r1", "mode": "reviewer"}, {"id": "r2", "mode": "reviewer"},
         {"id": "w1", "mode": "worker", "reviewer_role": "r1"}, {"id": "w2", "mode": "worker", "reviewer_role": "r2"}]
ADDR = {"r1": "t1", "r2": "t2", "w1": "t3", "w2": "t4"}
RESULTS = [{"role": r, "terminal": "ao-" + r} for r in ("r1", "r2", "w1", "w2")]


class FakeHerdr:
    def __init__(self, paned=("tPM",), keep_tab="tab1", appear=True):
        self.panes = {t: ("p" + t, "tab1") for t in paned}
        self.keep_tab, self.appear, self.calls = keep_tab, appear, []

    def __call__(self, argv, **kw):
        ok = lambda out="": subprocess.CompletedProcess(argv, 0, stdout=out, stderr="")
        if argv[0] == "hc":
            name = argv[2][3:]
            return ok(json.dumps({"address": ADDR[name]}))
        self.calls.append(argv[1:])
        if argv[1] == "ls":
            terms = [{"terminal": t, "pane": p} for t, (p, _) in self.panes.items()]
            return ok(json.dumps({"spaces": [{"tabs": [{"id": "tab1", "terminals": terms}]}]}))
        if argv[2] == "terminal.keep":
            t = argv[4]
            if self.appear:
                self.panes[t] = ("p" + t, self.keep_tab)
            return ok(json.dumps({"pending": True, "terminal": t, "pane": "p" + t, "tab": self.keep_tab}))
        return ok("{}")

    def mutations(self):
        return [c for c in self.calls if c[0] == "do"]


@patch("agentorg.runtime.time.sleep", lambda s: None)
@patch("agentorg.runtime.load_project", lambda p: {"roles": ROLES})
class PanesTest(unittest.TestCase):
    def run_arrange(self, fake, pm="tPM", which="/mock/herdr-app"):
        err = io.StringIO()
        with patch("agentorg.runtime.run_process", side_effect=fake), patch("agentorg.runtime.which", return_value=which), \
             patch("agentorg.runtime.pm_terminal", return_value=pm), contextlib.redirect_stderr(err):
            return runtime.arrange_panes(Path("."), RESULTS), err.getvalue()

    def test_command_order_two_reviewers_two_workers(self):
        fake = FakeHerdr()
        out, _ = self.run_arrange(fake)
        self.assertEqual(out, {"arranged": ["r1", "r2", "w1", "w2"]})
        self.assertEqual(fake.mutations(), [
            ["do", "pane.focus", "--pane", "ptPM"], ["do", "terminal.keep", "--terminal", "t1", "--place", "right"],
            ["do", "pane.focus", "--pane", "pt1"], ["do", "terminal.keep", "--terminal", "t2", "--place", "down"],
            ["do", "pane.focus", "--pane", "pt1"], ["do", "terminal.keep", "--terminal", "t3", "--place", "right"],
            ["do", "pane.focus", "--pane", "pt2"], ["do", "terminal.keep", "--terminal", "t4", "--place", "right"],
            ["do", "pane.focus", "--pane", "ptPM"]])

    def test_keep_retries_while_terminal_is_not_running_yet(self):
        # live (resume): herdr-app answered "no running terminal" for a terminal created a moment earlier
        fake, fails = FakeHerdr(), {"t3": 2}

        def flaky(argv, **kw):
            if argv[0] != "hc" and len(argv) > 4 and argv[2] == "terminal.keep" and fails.get(argv[4], 0) > 0:
                fails[argv[4]] -= 1
                fake.calls.append(argv[1:])
                return subprocess.CompletedProcess(argv, 1, stdout="", stderr='{"error": "no running terminal \\"t3\\""}')
            return fake(argv, **kw)
        out, err = self.run_arrange(flaky)
        self.assertEqual(out, {"arranged": ["r1", "r2", "w1", "w2"]})
        self.assertEqual(len([c for c in fake.mutations() if c[1] == "terminal.keep" and c[3] == "t3"]), 3)
        self.assertEqual(err, "")

    def test_wrong_tab_parks_and_stops(self):
        fake = FakeHerdr(keep_tab="other")
        out, err = self.run_arrange(fake)
        self.assertEqual(out["arranged"], [])
        self.assertEqual(fake.mutations()[-1], ["do", "terminal.park", "--terminal", "t1"])
        self.assertEqual(len([c for c in fake.mutations() if c[1] == "terminal.keep"]), 1)
        self.assertIn("WARNING", err)

    def test_no_herdr_app_or_no_pm_makes_no_calls(self):
        for kw in ({"which": None}, {"pm": None}):
            fake = FakeHerdr()
            out, _ = self.run_arrange(fake, **kw)
            self.assertEqual(fake.calls, [])
            self.assertIn("skipped", out)

    def test_pm_without_pane_does_nothing(self):
        fake = FakeHerdr(paned=())
        out, _ = self.run_arrange(fake)
        self.assertEqual(fake.mutations(), [])
        self.assertIn("skipped", out)

    def test_already_paned_roles_are_skipped(self):
        fake = FakeHerdr(paned=("tPM", "t1", "t3"))
        out, _ = self.run_arrange(fake)
        self.assertEqual(out, {"arranged": ["r2", "w2"]})
        keeps = [c for c in fake.mutations() if c[1] == "terminal.keep"]
        self.assertEqual(keeps, [["do", "terminal.keep", "--terminal", "t2", "--place", "down"],
                                 ["do", "terminal.keep", "--terminal", "t4", "--place", "right"]])

    def test_pending_pane_that_never_appears_warns_and_stops(self):
        fake = FakeHerdr(appear=False)
        out, err = self.run_arrange(fake)
        self.assertEqual(out["arranged"], [])
        self.assertIn("did not appear", err)
        self.assertEqual(len([c for c in fake.mutations() if c[1] == "terminal.keep"]), 1)

    def test_no_panes_flag_skips_arrangement(self):
        with patch("agentorg.runtime.arrange_panes") as arrange, patch("agentorg.runtime.validate_binaries", return_value=[]), \
             patch("agentorg.runtime.load_profiles", return_value={}), patch("agentorg.runtime.hc_ready"), \
             patch("agentorg.runtime.install_protocol"), patch("agentorg.runtime.write_json"), \
             patch("agentorg.runtime.read_json", return_value={"terminals": {}}), \
             patch("agentorg.runtime.load_project", lambda p: {"roles": [], "kind": "content"}):
            report = {}
            runtime.start_team(Path("."), apply=True, panes=False, report=report)
        arrange.assert_not_called()
        self.assertEqual(report["panes"]["skipped"], "--no-panes")


if __name__ == "__main__":
    unittest.main()
