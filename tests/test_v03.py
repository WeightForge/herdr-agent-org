"""v0.3 features: validation fixes, antigravity, inbox, team down, team smoke."""
import contextlib
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import test_agentorg as base
from agentorg import cli, config, runtime, smoke


class Fixture(unittest.TestCase):
    """Reuse the temp-project helpers without re-collecting TempOrgTest's own tests."""
    setUp = base.TempOrgTest.setUp
    init = base.TempOrgTest.init
    make_profiles = base.TempOrgTest.make_profiles
    git_commit = base.TempOrgTest.git_commit


class V03Test(Fixture):
    def test_role_disable_reviewer_with_enabled_worker_is_refused_and_file_unchanged(self):
        self.init()
        p = config.project_file(self.project)
        before = p.read_bytes()
        ns = cli.add_parser().parse_args(["role", "set", "technical-reviewer", "--path", str(self.project), "--disable"])
        with self.assertRaisesRegex(config.OrgError, "reviewer_role"):
            cli.role_cmd(ns)
        self.assertEqual(p.read_bytes(), before)
        config.load_project(self.project)  # still loadable

    def test_disabled_worker_may_point_at_disabled_reviewer(self):
        self.init()
        doc = config.load_project(self.project)
        config.resolve_role(doc, "technical-reviewer")["enabled"] = False
        config.resolve_role(doc, "backend-worker")["enabled"] = False
        config.write_json(config.project_file(self.project), doc)
        config.load_project(self.project)
        ns = cli.add_parser().parse_args(["role", "set", "backend-worker", "--enable", "--path", str(self.project)])
        with self.assertRaises(config.OrgError):  # re-enabling the worker alone must fail validation
            cli.role_cmd(ns)

    def test_read_json_accepts_utf8_bom(self):
        f = self.root / "bom.json"
        f.write_bytes(b"\xef\xbb\xbf" + json.dumps({"a": 1}).encode())
        self.assertEqual(config.read_json(f), {"a": 1})

    def test_antigravity_profile_and_launch_argv(self):
        self.init()
        with patch("agentorg.cli.which", return_value="/mock/agy"), contextlib.redirect_stdout(io.StringIO()):
            cli.main(["profile", "add", "reviewer", "--provider", "antigravity", "--model", "gemini-4-hydrogen-medium", "--effort", "low"])
            for bad in (["--config-dir", str(self.root)], ["--native-profile", "x"]):
                with self.assertRaises(config.OrgError):
                    cli.profile_cmd(cli.add_parser().parse_args(["profile", "add", "r2", "--provider", "antigravity"] + bad))
        self.assertEqual(config.load_profiles()["reviewer"]["command"], "agy")
        seen = {}

        def capture(argv, **kw):
            seen["cmd"] = argv
            raise RuntimeError("capture")

        with patch("agentorg.runtime.which", return_value="/mock/agy"), \
             patch("agentorg.runtime.subprocess.run", side_effect=capture), \
             patch("agentorg.runtime.os.execvpe", side_effect=lambda b, a, e: capture(a)):
            with self.assertRaisesRegex(RuntimeError, "capture"):
                runtime.launch_agent_process(self.project, "technical-reviewer", "t7")
        cmd = seen["cmd"]
        self.assertEqual(cmd[:6], ["/mock/agy", "--model", "gemini-4-hydrogen-medium", "--effort", "low", "-i"])
        self.assertEqual(len(cmd), 7)
        self.assertIn("hc send t7", cmd[6])

    def test_prompts_forbid_keys_and_are_cmd_safe(self):
        self.init()
        doc = config.load_project(self.project)
        bad_chars = set('"%&|<>^\n')
        for role in doc["roles"]:
            for pm in (None, "t7"):
                prompt = runtime.make_agent_prompt(self.project, role, pm)
                self.assertIn("hc keys to a blocked agent is forbidden", prompt)
                self.assertIn("escalate blocked", prompt)
                self.assertFalse(set(prompt) & bad_chars, (role["id"], set(prompt) & bad_chars))
        for skill in ("agent-org-manager", "agent-org-engineering"):
            self.assertIn("hc keys", cli.skill_sources().joinpath(skill, "SKILL.md").read_text(encoding="utf-8"))

    def test_reviewer_prompt_uses_inbox_not_state_md(self):
        self.init()
        reviewer = config.resolve_role(config.load_project(self.project), "technical-reviewer")
        with_pm = runtime.make_agent_prompt(self.project, reviewer, "t7")
        no_pm = runtime.make_agent_prompt(self.project, reviewer)
        for prompt in (with_pm, no_pm):
            self.assertIn(".ai/inbox/UTCSTAMP-TASK-CODE-HEX4.md", prompt)
            self.assertIn("Never edit .ai/STATE.md", prompt)
            self.assertNotIn("write the escalation", prompt)
        self.assertIn("hc send t7 ESCALATION CODE TASK: .ai/inbox/FILE", with_pm)
        self.assertNotIn("hc send t7", no_pm)

    def test_init_ignores_inbox_and_status_counts_it(self):
        self.init()
        self.assertIn("inbox/", (self.project / ".ai" / ".gitignore").read_text())
        inbox = self.project / ".ai" / "inbox"
        (inbox / "done").mkdir(parents=True)
        (inbox / "20260101T000000Z-t1-blocked.md").write_text("x", encoding="utf-8")
        (inbox / "done" / "old.md").write_text("x", encoding="utf-8")
        self.assertEqual(runtime.inbox_pending(self.project), 1)
        out = io.StringIO()
        with patch("agentorg.cli.hc_ready"), patch("agentorg.cli.existing_terminal", return_value=None), \
             patch("agentorg.cli.role_labels", return_value={}), contextlib.redirect_stdout(out):
            cli.team_cmd(SimpleNamespace(path=str(self.project), op="status"))
        self.assertEqual(json.loads(out.getvalue())["inbox_pending"], 1)

    def _down_setup(self):
        self.init()
        self.make_profiles()
        self.git_commit()
        doc = config.load_project(self.project)
        wt = runtime.ensure_worktree(self.project, config.resolve_role(doc, "backend-worker"))
        calls = []
        original = runtime.run_process

        def fake_run(argv, **kw):
            if argv[0] == "hc":
                calls.append(argv)
                return subprocess.CompletedProcess(argv, 0, stdout="{}", stderr="")
            return original(argv, **kw)

        return doc, wt, calls, fake_run

    def test_team_down_dry_run_touches_nothing(self):
        _, wt, calls, fake_run = self._down_setup()
        with patch("agentorg.runtime.existing_terminal", return_value={"state": "live"}), \
             patch("agentorg.runtime.run_process", side_effect=fake_run):
            items = runtime.stop_team(self.project, apply=False, remove_worktrees=True)
        self.assertEqual(calls, [])
        self.assertTrue(wt.exists())
        self.assertEqual({x["action"] for x in items}, {"would_stop"})
        self.assertFalse((self.project / ".ai" / "RUNTIME.json").exists())

    def test_team_down_apply_order_skip_and_worktrees(self):
        doc, wt, calls, fake_run = self._down_setup()
        names = {r["id"]: runtime.terminal_name(self.project, r["id"]) for r in doc["roles"]}

        def existing(name, labels=None):
            if name == names["design-reviewer"]:
                raise config.OrgError("label cfg differs")
            return {"state": "live"} if name != names["frontend-worker"] else None

        (wt / "dirty.txt").write_text("uncommitted", encoding="utf-8")
        with patch("agentorg.runtime.existing_terminal", side_effect=existing), \
             patch("agentorg.runtime.run_process", side_effect=fake_run):
            items = runtime.stop_team(self.project, apply=True, remove_worktrees=True)
        rows = {x["role"]: x for x in items}
        self.assertEqual([c[2] for c in calls if c[1] == "kill"], [names["backend-worker"], names["technical-reviewer"]])  # workers first
        self.assertEqual([c[1] for c in calls], ["kill", "rm", "kill", "rm"])
        self.assertEqual(rows["design-reviewer"]["action"], "skipped")
        self.assertEqual(rows["frontend-worker"]["action"], "not_running")
        self.assertTrue(rows["backend-worker"]["worktree"].startswith("kept"))  # dirty: removed without --force fails
        self.assertTrue(wt.exists())
        saved = json.loads((self.project / ".ai" / "RUNTIME.json").read_text(encoding="utf-8"))["terminals"]
        self.assertIs(saved["backend-worker"]["live"], False)
        self.assertNotIn("design-reviewer", saved)
        (wt / "dirty.txt").unlink()
        with patch("agentorg.runtime.existing_terminal", return_value=None), patch("agentorg.runtime.run_process", side_effect=fake_run):
            items = runtime.stop_team(self.project, apply=True, remove_worktrees=True)
        self.assertEqual({x["role"]: x.get("worktree") for x in items}["backend-worker"], "removed")
        self.assertFalse(wt.exists())
        branch = runtime.worktree_info(self.project, config.resolve_role(doc, "backend-worker"))[1]
        self.assertEqual(runtime.run_process(["git", "show-ref", "--verify", "--quiet", "refs/heads/" + branch], cwd=self.project).returncode, 0)

    def test_team_down_cli_dry_run_message(self):
        self.init()
        self.make_profiles()
        out = io.StringIO()
        with patch("agentorg.cli.hc_ready"), patch("agentorg.cli.stop_team", return_value=[]) as stop, contextlib.redirect_stdout(out):
            cli.main(["team", "down", "--path", str(self.project)])
        stop.assert_called_once_with(self.project.resolve(), apply=False, remove_worktrees=False)
        self.assertIn("Add --apply", out.getvalue())


class SmokeTest(Fixture):
    def test_fake_agent_echoes_stdin(self):
        env = dict(os.environ, HC_TERMINAL_ID="t9", AGENTORG_FAKE_DIR=str(self.root),
                   PYTHONPATH=str(Path(__file__).resolve().parent.parent / "src"))
        r = subprocess.run([sys.executable, "-m", "agentorg._fake_agent", "--model", "m", "PROMPT TEXT"], input="hello\nworld\n",
                           text=True, capture_output=True, env=env, timeout=30)
        self.assertIn("FAKE AGENT START", r.stdout)
        self.assertIn("GOT: hello", r.stdout)
        self.assertIn("GOT: world", r.stdout)
        self.assertEqual(json.loads((self.root / "t9.json").read_text())["prompt"], "PROMPT TEXT")

    def test_cleanup_always_runs_when_setup_raises(self):
        calls = []

        def fake_run(argv, **kw):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, stdout="{}", stderr="")

        def setup(ctx):
            ctx["names"] += ["ao-smoke-pm-x", "ao-smoke-rev"]
            (ctx["tmp"] / "marker").write_text("x")
            raise RuntimeError("boom")

        made = {}
        real_mkdtemp = smoke.tempfile.mkdtemp

        def mkdtemp(**kw):
            made["dir"] = real_mkdtemp(**kw)
            return made["dir"]

        with patch.object(smoke, "hc_ready"), patch.object(smoke, "_require_installed_package"), \
             patch.object(smoke, "_setup", side_effect=setup), patch.object(smoke.tempfile, "mkdtemp", side_effect=mkdtemp), \
             patch("agentorg.runtime.run_process", side_effect=fake_run), patch.object(smoke, "run_process", side_effect=fake_run):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                smoke.run_smoke()
        self.assertEqual([c[2] for c in calls if c[:2] == ["hc", "kill"]], ["ao-smoke-pm-x", "ao-smoke-rev"])
        self.assertFalse(Path(made["dir"]).exists())

    def test_failed_check_is_reported_and_exit_code_nonzero(self):
        def checks(ctx, report, keep):
            smoke._check(report, "good", lambda: "ok")
            smoke._check(report, "bad", lambda: smoke._need(False, "nope"))

        with patch.object(smoke, "hc_ready"), patch.object(smoke, "_require_installed_package"), \
             patch.object(smoke, "_setup"), patch.object(smoke, "_run_checks", side_effect=checks), \
             patch.object(smoke.tempfile, "mkdtemp", return_value=str(self.root)), \
             patch.object(smoke, "_cleanup", return_value={"ok": True, "problems": []}):
            report = smoke.run_smoke()
        self.assertFalse(report["ok"])
        self.assertEqual((report["checks"]["good"]["pass"], report["checks"]["bad"]["pass"]), (True, False))
        with patch("agentorg.smoke.run_smoke", return_value=report), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                cli.team_cmd(SimpleNamespace(op="smoke", keep=False))
        self.assertEqual(cm.exception.code, 1)

    def test_keep_skips_cleanup(self):
        with patch.object(smoke, "hc_ready"), patch.object(smoke, "_require_installed_package"), patch.object(smoke, "_setup"), \
             patch.object(smoke, "_run_checks"), patch.object(smoke.tempfile, "mkdtemp", return_value=str(self.root)), \
             patch.object(smoke, "_cleanup") as cleanup:
            report = smoke.run_smoke(keep=True)
        cleanup.assert_not_called()
        self.assertIn("kept", report)

    def test_script_shim_carries_env(self):
        path = Path(smoke._script(self.root / "shim", [smoke._set("A_B", "c"), "echo hi"]))
        self.assertIn("A_B", path.read_text(encoding="utf-8"))
        self.assertEqual(path.suffix, ".cmd" if os.name == "nt" else ".sh")
        if os.name != "nt":
            self.assertTrue(os.access(path, os.X_OK))


if __name__ == "__main__":
    unittest.main()
