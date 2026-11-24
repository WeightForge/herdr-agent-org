"""v0.4 features: codex containment, blocked status, task files/handoff prompts, disabled roles in team down."""
import contextlib
import io
import json
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agentorg import cli, config, runtime
from test_v03 import Fixture

SECRET = "sk-live-FAKE-SECRET-123"


class CodexContainmentTest(Fixture):
    def _launch_argv(self, role_id):
        seen = {}

        def capture(argv, **kw):
            seen["cmd"] = argv
            raise RuntimeError("capture")

        with patch("agentorg.runtime.which", return_value="/mock/bin"), \
             patch("agentorg.runtime.subprocess.run", side_effect=capture), \
             patch("agentorg.runtime.os.execvpe", side_effect=lambda b, a, e: capture(a)):
            with self.assertRaisesRegex(RuntimeError, "capture"):
                runtime.launch_agent_process(self.project, role_id)
        return seen["cmd"]

    def test_codex_argv_has_no_daemon_and_claude_does_not(self):
        self.init()
        self.make_profiles()
        codex = self._launch_argv("frontend-worker")
        self.assertEqual(codex[1], "--no-daemon")  # top-level option, before the prompt
        self.assertNotIn("--no-daemon", self._launch_argv("backend-worker"))

    def test_labels_nodaemon_only_for_codex(self):
        self.init()
        self.make_profiles()
        doc = config.load_project(self.project)
        self.assertEqual(runtime.role_labels(self.project, config.resolve_role(doc, "frontend-worker"))["nodaemon"], "1")
        for rid in ("backend-worker", "technical-reviewer"):
            self.assertNotIn("nodaemon", runtime.role_labels(self.project, config.resolve_role(doc, rid)))

    def test_pre_fix_codex_terminal_without_label_is_refused(self):
        self.init()
        self.make_profiles()
        role = config.resolve_role(config.load_project(self.project), "frontend-worker")
        labels = runtime.role_labels(self.project, role)
        name = runtime.terminal_name(self.project, role["id"])
        stale = {k: v for k, v in labels.items() if k != "nodaemon"}
        out = subprocess.CompletedProcess(["hc"], 0, stdout=json.dumps({"name": name, "state": "live", "labels": stale}), stderr="")
        with patch("agentorg.runtime.run_process", return_value=out):
            with self.assertRaisesRegex(config.OrgError, "label nodaemon differs"):
                runtime.existing_terminal(name, labels)


class BlockedStatusTest(Fixture):
    def _status(self, record):
        if not (self.project / ".ai").exists():
            self.init()
            self.make_profiles()
        out = io.StringIO()
        with patch("agentorg.cli.hc_ready"), patch("agentorg.cli.existing_terminal", return_value=record), \
             patch("agentorg.cli.role_labels", return_value={}), contextlib.redirect_stdout(out):
            cli.team_cmd(SimpleNamespace(path=str(self.project), op="status"))
        return out.getvalue()

    def test_blocked_lists_role_terminal_kind_and_never_msg(self):
        text = self._status({"state": "live", "status": {"app": "claude-code", "state": "blocked", "kind": "permission",
                                                          "msg": f"Allow Bash(curl -H 'Authorization: {SECRET}')?"}})
        self.assertNotIn(SECRET, text)
        data = json.loads(text)
        self.assertEqual(len(data["blocked"]), len(data["status"]))
        self.assertEqual(set(data["blocked"][0]), {"role", "terminal", "kind"})
        self.assertEqual(data["blocked"][0]["kind"], "permission")

    def test_unknown_kind_and_healthy(self):
        data = json.loads(self._status({"state": "live", "status": {"state": "blocked", "msg": SECRET}}))
        self.assertEqual({b["kind"] for b in data["blocked"]}, {"unknown"})
        self.assertNotIn(SECRET, json.dumps(data))
        data = json.loads(self._status({"state": "live", "status": {"state": "working"}}))
        self.assertEqual(data["blocked"], [])

    def test_blocked_info_sanitizes_kind(self):
        self.assertEqual(runtime.blocked_info("r", "t", {"status": "blocked"})["kind"], "unknown")
        self.assertEqual(runtime.blocked_info("r", "t", {"status": {"state": "blocked", "kind": SECRET + " x"}})["kind"], "unknown")
        self.assertIsNone(runtime.blocked_info("r", "t", {"status": {"state": "idle"}}))


class PromptTest(Fixture):
    def test_handoff_and_task_files_in_prompts(self):
        self.init()
        doc = config.load_project(self.project)
        worker = runtime.make_agent_prompt(self.project, config.resolve_role(doc, "backend-worker"), "t7")
        self.assertLess(worker.index("Commit your report"), worker.index("hc send"))
        self.assertIn(".ai/handoff/TASK.md", worker)
        reviewer = runtime.make_agent_prompt(self.project, config.resolve_role(doc, "technical-reviewer"), "t7")
        for text in ("progress.md", "HEX4"):
            self.assertIn(text, reviewer)
        protocol = Path(runtime.__file__).parent.joinpath("data", "PROTOCOL.md").read_text(encoding="utf-8")
        for text in ("blocked_by", "git show <commit>:.ai/handoff/<task>.md", "<hex4>"):
            self.assertIn(text, protocol)

    def test_init_state_has_handled_escalations_and_tasks_not_ignored(self):
        self.init()
        self.assertIn("## Handled escalations", (self.project / ".ai" / "STATE.md").read_text(encoding="utf-8"))
        self.assertNotIn("tasks", (self.project / ".ai" / ".gitignore").read_text(encoding="utf-8"))


class TeamDownDisabledTest(Fixture):
    def _run(self, existing, apply=True):
        if not (self.project / ".ai").exists():
            self.init()
            self.make_profiles()
            self.git_commit()
        doc = config.load_project(self.project)
        config.resolve_role(doc, "frontend-worker")["enabled"] = False
        config.write_json(config.project_file(self.project), doc)
        calls = []

        def fake_run(argv, **kw):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, stdout="{}", stderr="")

        with patch("agentorg.runtime.existing_terminal", side_effect=existing), patch("agentorg.runtime.run_process", side_effect=fake_run):
            rows = {x["role"]: x for x in runtime.stop_team(self.project, apply=apply)}
        return rows, calls

    def test_disabled_not_running_and_mismatch_report_disabled(self):
        rows, calls = self._run(lambda n, l=None: None)
        self.assertEqual(rows["frontend-worker"]["action"], "disabled")
        self.assertEqual(rows["backend-worker"]["action"], "not_running")

        def mismatch(name, labels=None):
            raise config.OrgError("label cfg differs")
        rows, calls = self._run(mismatch)
        self.assertEqual(rows["frontend-worker"]["action"], "disabled")
        self.assertEqual(rows["backend-worker"]["action"], "skipped")  # enabled roles keep `skipped`
        self.assertEqual(calls, [])

    def test_disabled_live_label_matching_terminal_is_stopped(self):
        rows, calls = self._run(lambda n, l=None: {"state": "live"})
        self.assertEqual(rows["frontend-worker"]["action"], "stopped")
        self.assertIn("frontend-worker", [r for r in rows])
        self.assertEqual(len([c for c in calls if c[1] == "kill"]), len(rows))


if __name__ == "__main__":
    unittest.main()
