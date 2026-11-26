"""v0.9.0: kept terminals, session ids, PM registration, agentorg resume. All hc and provider calls are mocked."""
import contextlib
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from agentorg import cli, config, runtime
from test_v03 import Fixture

UUID = "11111111-2222-4333-8444-555555555555"


def shell(name="powershell.exe"):
    """A kept terminal whose program was lost: hc replaced it with a shell (argv) and sees no agent (status null)."""
    return {"name": "x", "state": "live", "argv": [name], "status": None, "foreground": {"name": name, "argv": [name]}}


class ResumeTest(Fixture):
    def setUp(self):
        super().setUp()
        self.init(autonomy="full")
        self.make_profiles()
        self.git_commit()
        self.sent = []
        self.team = [r for r in config.load_project(self.project)["roles"] if r.get("enabled", True)]

    def write_runtime(self, **extra):
        doc = {"schema_version": 2, "terminals": {r["id"]: {"cwd": str(self.project), "provider": "claude", "profile": r["profile"], "session_id": UUID}
                                                 for r in self.team}, **extra}
        config.write_json(self.project / ".ai" / "RUNTIME.json", doc)

    def run_resume(self, terminals, apply=True, runtime_extra=None):
        """terminals: terminal name -> record or None (gone)."""
        self.write_runtime(**(runtime_extra or {}))

        def existing(name, expected_labels=None):
            return terminals.get(name)

        def proc(argv, **kw):
            self.sent.append(argv)
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

        with patch("agentorg.runtime.hc_ready"), patch("agentorg.runtime.existing_terminal", side_effect=existing), \
             patch("agentorg.runtime.run_process", side_effect=proc), patch("agentorg.runtime.arrange_panes") as panes, \
             patch("agentorg.runtime.ensure_worktree", side_effect=lambda p, r: self.project):
            return runtime.resume_team(self.project, apply=apply), panes

    def names(self):
        return [runtime.terminal_name(self.project, r["id"]) for r in self.team]

    def test_dry_run_sends_nothing(self):
        items, _ = self.run_resume({n: shell() for n in self.names()}, apply=False)
        self.assertEqual({i["action"] for i in items if i["role"] != "pm"}, {"resume_in_shell"})
        self.assertEqual(self.sent, [])

    def test_shell_in_place_gets_launch_line_with_session(self):
        items, panes = self.run_resume({n: shell() for n in self.names()})
        role_sends = [s for s in self.sent if s[:2] == ["hc", "send"]]
        self.assertEqual(len(role_sends), len(self.team))
        line = role_sends[0][3]
        self.assertTrue(line.startswith("& '"), line)
        self.assertIn("'_launch'", line)
        self.assertIn(f"'--resume' '{UUID}'", line)
        panes.assert_not_called()

    def test_running_agent_is_left_alone(self):
        # an agent running a tool: the foreground is a shell, the terminal's own program is not
        running = {"name": "x", "state": "live", "argv": ["python.exe", "-m", "agentorg", "_launch"], "status": {"state": "working"},
                   "foreground": {"name": "powershell.exe", "argv": ["powershell.exe"]}}
        items, _ = self.run_resume({n: running for n in self.names()})
        self.assertEqual({i["action"] for i in items if i["role"] != "pm"}, {"running"})
        self.assertEqual(self.sent, [])

    def test_missing_terminal_is_recreated_with_keep_resume_and_panes(self):
        items, panes = self.run_resume({})
        runs = [s for s in self.sent if s[:2] == ["hc", "run"]]
        self.assertEqual(len(runs), len(self.team))
        for argv in runs:
            self.assertIn("--keep", argv)
            self.assertEqual(argv[argv.index("--resume") + 1], UUID)
        panes.assert_called_once()

    def test_no_session_in_project_root_is_skipped_but_worktree_uses_last(self):
        self.write_runtime()
        rt = config.read_json(self.project / ".ai" / "RUNTIME.json")
        for rec in rt["terminals"].values():
            rec["session_id"] = None
        worker = next(r for r in self.team if r["mode"] == "worker")
        rt["terminals"][worker["id"]]["cwd"] = str(self.project / "wt")
        config.write_json(self.project / ".ai" / "RUNTIME.json", rt)
        with patch("agentorg.runtime.hc_ready"), patch("agentorg.runtime.existing_terminal", return_value=None), \
             patch("agentorg.runtime.run_process", return_value=subprocess.CompletedProcess([], 0, "", "")) as rp, \
             patch("agentorg.runtime.arrange_panes"), patch("agentorg.runtime.discover_sessions", return_value=False):
            items = runtime.resume_team(self.project, apply=False)
        by = {i["role"]: i for i in items}
        self.assertEqual(by[worker["id"]]["action"], "recreate")
        self.assertEqual(by[worker["id"]]["command"][by[worker["id"]]["command"].index("--resume") + 1], "last")
        self.assertEqual({v["action"] for k, v in by.items() if k not in (worker["id"], "pm")}, {"no_session"})
        rp.assert_not_called()

    def test_pm_resumed_in_shell_else_woken_when_team_changed(self):
        extra = {"pm_terminal": "t9", "pm": {"provider": "claude", "session_id": UUID}}
        terminals = {n: shell() for n in self.names()}
        terminals["t9"] = shell("bash")
        items, _ = self.run_resume(terminals, runtime_extra=extra)
        pm_send = [s for s in self.sent if s[:3] == ["hc", "send", "t9"]]
        self.assertIn("_resume_pm", pm_send[0][3])
        self.assertEqual(items[-1]["action"], "resume_in_shell")
        self.sent.clear()
        # the owner's PM pane: its program is always a shell; hc sees an agent there, so it is running
        terminals["t9"] = {"name": "t9", "state": "live", "argv": ["powershell.exe", "-NoExit"], "status": {"state": "idle"},
                           "foreground": {"name": "powershell.exe", "argv": ["powershell.exe"]}}
        items, _ = self.run_resume(terminals, runtime_extra=extra)
        self.assertEqual(items[-1]["action"], "wake_pm")
        self.assertEqual([s for s in self.sent if s[:3] == ["hc", "send", "t9"]][0][3], runtime.PM_WAKE)
        for ch in '"%&|<>^':  # the wake text may reach a Windows .cmd shim
            self.assertNotIn(ch, runtime.PM_WAKE)

    def test_resume_run_inside_the_pm_pane_resumes_the_pm(self):
        # live: `agentorg resume` typed in the PM pane is that shell's foreground, so the pane did not look idle
        extra = {"pm_terminal": "t9", "pm": {"provider": "claude", "session_id": UUID}}
        terminals = {n: shell() for n in self.names()}
        terminals["t9"] = {"name": "t9", "state": "live", "argv": ["powershell.exe", "-NoExit"], "status": None,
                           "foreground": {"name": "agentorg.exe", "argv": ["agentorg.exe", "resume", "--apply"]}}
        with patch.dict(os.environ, {"HC_TERMINAL_ID": "t9"}):
            items, _ = self.run_resume(terminals, runtime_extra=extra)
        self.assertEqual(items[-1]["action"], "resume_in_shell")
        self.sent.clear()
        with patch.dict(os.environ, {"HC_TERMINAL_ID": "t3"}):  # elsewhere: something else runs there, no agent, leave it
            items, _ = self.run_resume(terminals, runtime_extra=extra)
        self.assertEqual(items[-1]["action"], "running")
        self.assertEqual([s for s in self.sent if s[:3] == ["hc", "send", "t9"]], [])

    def test_unregistered_pm_in_shell_is_reported(self):
        items, _ = self.run_resume({"t9": shell()}, runtime_extra={"pm_terminal": "t9"})
        self.assertEqual(items[-1]["action"], "no_session")


class LaunchTest(Fixture):
    def argv_for(self, provider, command, **kw):
        profiles = {"p": {"provider": provider, "command": command, "config_dir": None, "native_profile": None}}
        doc = config.load_project(self.project)
        doc["roles"][0]["profile"] = "p"
        config.write_json(config.project_file(self.project), doc)
        seen = {}

        def capture(argv, **k):
            seen["cmd"] = argv
            return 0

        with patch("agentorg.runtime.load_profiles", return_value=profiles), patch("agentorg.runtime.which", return_value="/mock/" + command), \
             patch("agentorg.runtime.subprocess.run", side_effect=lambda a, **k: capture(a) or subprocess.CompletedProcess(a, 0)), \
             patch("agentorg.runtime.os.execvpe", side_effect=lambda b, a, e: capture(a)):
            runtime.launch_agent_process(self.project, doc["roles"][0]["id"], "t7", **kw)
        return seen["cmd"]

    def test_resume_argv_per_provider_keeps_autonomy_flags_and_has_no_prompt(self):
        self.init(autonomy="full")
        c = self.argv_for("claude", "claude", resume=UUID)
        self.assertEqual(c[1:], ["--dangerously-skip-permissions", "--resume", UUID])
        c = self.argv_for("codex", "codex", resume=UUID)
        self.assertEqual(c[1:8], ["resume", "--no-daemon", "-c", "check_for_update_on_startup=false", "-c", "disable_paste_burst=true", "--dangerously-bypass-approvals-and-sandbox"])
        self.assertEqual(c[-1], UUID)
        c = self.argv_for("antigravity", "agy", resume=UUID)
        self.assertEqual(c[-2:], ["--conversation", UUID])
        self.assertEqual(self.argv_for("antigravity", "agy", resume="last")[-1], "--continue")
        self.assertEqual(self.argv_for("codex", "codex", resume="last")[-1], "--last")
        self.assertEqual(self.argv_for("claude", "claude", resume="last")[-1], "--continue")

    def test_fresh_claude_launch_sets_session_id(self):
        self.init(autonomy="supervised")
        c = self.argv_for("claude", "claude", session=UUID)
        self.assertEqual(c[1:3], ["--session-id", UUID])

    def test_team_up_records_session_and_keep(self):
        self.init()
        self.make_profiles()
        self.git_commit()
        calls, original = [], runtime.run_process

        def proc(argv, **kw):
            if argv[0] != "hc":
                return original(argv, **kw)
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

        with patch("agentorg.runtime.which", return_value="/mock/bin"), patch("agentorg.runtime.hc_ready"), \
             patch("agentorg.runtime.existing_terminal", return_value=None), patch("agentorg.runtime.run_process", side_effect=proc):
            runtime.start_team(self.project, apply=True, panes=False)
        runs = [c for c in calls if c[:2] == ["hc", "run"] and "--session-id" in c]
        self.assertTrue(runs)
        self.assertTrue(all("--keep" in c for c in calls if c[:2] == ["hc", "run"]))
        rt = config.read_json(self.project / ".ai" / "RUNTIME.json")
        self.assertEqual(len([r for r in rt["terminals"].values() if r["provider"] == "claude" and r["session_id"]]), len(runs))
        codex = [r for r in rt["terminals"].values() if r["provider"] == "codex"]
        self.assertTrue(all(r["session_id"] is None for r in codex))
        self.assertEqual(config.known_projects(), [str(self.project.resolve())])


class SessionDiscoveryTest(Fixture):
    def test_codex_matches_cwd_and_skips_claimed(self):
        home = self.root / "codexhome"
        for sid, cwd in (("a-1", "/proj"), ("b-2", "/proj"), ("c-3", "/other")):
            d = home / "sessions" / "2026" / "01" / "01"
            d.mkdir(parents=True, exist_ok=True)
            (d / f"rollout-{sid}.jsonl").write_text(json.dumps({"payload": {"id": sid, "cwd": cwd}}) + "\n{broken", encoding="utf-8")
            os.utime(d / f"rollout-{sid}.jsonl", (100 + ord(sid[0]), 100 + ord(sid[0])))
        self.assertEqual(runtime.find_session("codex", "/proj", str(home), 0, set()), "b-2")
        self.assertEqual(runtime.find_session("codex", "/proj", str(home), 0, {"b-2"}), "a-1")
        self.assertIsNone(runtime.find_session("codex", "/nowhere", str(home), 0, set()))

    def test_agy_takes_earliest_unclaimed_since_launch(self):
        conv = self.root / "home" / ".gemini" / "antigravity-cli" / "conversations"
        conv.mkdir(parents=True)
        for name, t in (("old", 50), ("first", 200), ("second", 300)):
            (conv / f"{name}.db").write_bytes(b"")
            os.utime(conv / f"{name}.db", (t, t))
        with patch.object(Path, "home", return_value=self.root / "home"), patch("agentorg.runtime._birth", side_effect=lambda st: st.st_mtime):
            self.assertEqual(runtime.find_session("antigravity", "/x", None, 100, set()), "first")
            self.assertEqual(runtime.find_session("antigravity", "/x", None, 100, {"first"}), "second")
            self.assertEqual(runtime.find_session("antigravity", "/x", None, 100, set(), newest=True), "second")

    def test_register_pm_uses_env_session_and_terminal(self):
        self.init()
        env = {"CLAUDE_CODE_SESSION_ID": UUID, "HC_TERMINAL_ID": "t5", "CLAUDE_CONFIG_DIR": str(self.root)}
        with patch.dict(os.environ, env):
            out = runtime.register_pm(self.project)
        rt = config.read_json(self.project / ".ai" / "RUNTIME.json")
        self.assertEqual(rt["pm_terminal"], "t5")
        self.assertEqual(rt["pm"]["session_id"], UUID)
        self.assertEqual(rt["pm"]["config_dir"], str(self.root))
        self.assertEqual(out["provider"], "claude")

    def test_pm_resumes_on_its_registered_model(self):
        # live: a PM registered without a model came back on the provider default model
        self.init()
        with patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": UUID, "HC_TERMINAL_ID": "t5"}):
            runtime.register_pm(self.project, model="opus", effort="high")
            with self.assertRaises(config.OrgError):
                runtime.register_pm(self.project, model="bad model;")
        with patch("agentorg.runtime._run_provider", side_effect=lambda cmd, env: cmd):
            cmd = runtime.resume_pm_process(self.project)
        self.assertEqual(cmd[1:7], ["--model", "opus", "--effort", "high", "--resume", UUID])

    def test_pm_resumes_with_full_autonomy_flag(self):
        # live: a full-autonomy PM came back in plain permission mode
        self.init(autonomy="full")
        with patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": UUID, "HC_TERMINAL_ID": "t5"}):
            runtime.register_pm(self.project)
        with patch("agentorg.runtime._run_provider", side_effect=lambda cmd, env: cmd):
            cmd = runtime.resume_pm_process(self.project)
        self.assertEqual(cmd[1:4], ["--dangerously-skip-permissions", "--resume", UUID])

    def test_register_pm_without_provider_hint_fails(self):
        self.init()
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(config.OrgError, "--provider"):
            runtime.register_pm(self.project)


class ShellLineTest(unittest.TestCase):
    def test_quoting_per_shell(self):
        argv = [r"C:\Program Files\Python\python.exe", "-m", "agentorg", "--project", r"D:\My Proj\it's"]
        self.assertEqual(runtime.shell_line("powershell", argv),
                         "& 'C:\\Program Files\\Python\\python.exe' '-m' 'agentorg' '--project' 'D:\\My Proj\\it''s'")
        self.assertIn('"C:\\Program Files\\Python\\python.exe"', runtime.shell_line("cmd", argv))
        self.assertIn("'/p q'", runtime.shell_line("bash", ["/p q"]))

    def test_shell_kind(self):
        self.assertEqual(runtime.shell_kind({"terminal": shell("C:\\Windows\\powershell.exe")}), "powershell")
        self.assertEqual(runtime.shell_kind(shell("/bin/bash")), "bash")
        self.assertIsNone(runtime.shell_kind({"argv": ["agy"], "foreground": {"name": "bash", "argv": ["bash"]}}))  # agent running a tool
        self.assertIsNone(runtime.shell_kind({"argv": None}))
        self.assertIsNone(runtime.lost_shell_kind({"argv": ["pwsh"], "status": {"state": "done"}}))  # PM pane with an agent
        self.assertEqual(runtime.lost_shell_kind({"argv": ["pwsh"], "status": None}), "pwsh")
        # after a resume the agent runs inside the replacement shell (live): still running, never resumed twice
        resumed = {"argv": ["/bin/bash"], "status": {"state": "idle"}, "foreground": {"name": "agy", "argv": ["agy"]}}
        self.assertIsNone(runtime.lost_shell_kind(resumed))
        self.assertIsNone(runtime.lost_shell_kind({**resumed, "status": None}))  # agent starting, not yet detected
        self.assertEqual(runtime.lost_shell_kind({**resumed, "status": None, "foreground": {"name": "bash"}}), "bash")
        self.assertIsNone(runtime.shell_kind({}))


class CliTest(Fixture):
    def test_resume_all_skips_missing_projects_and_dry_run_default(self):
        self.init()
        config.register_project(self.project)
        config.write_json(config.org_home() / "projects.json", {"projects": [str(self.project), str(self.root / "gone")]})
        with patch("agentorg.cli.resume_team", return_value=[]) as rt, contextlib.redirect_stdout(io.StringIO()) as out:
            cli.main(["resume", "--all"])
        rt.assert_called_once()
        self.assertFalse(rt.call_args.kwargs["apply"])
        self.assertIn("Nothing restarted", out.getvalue())


if __name__ == "__main__":
    unittest.main()


class ExistingTerminalTest(unittest.TestCase):
    def test_pm_found_by_address_even_when_named(self):
        rec = {"address": "t8", "name": "pm-pane", "state": "live"}
        out = subprocess.CompletedProcess([], 0, stdout=json.dumps(rec), stderr="")
        with patch("agentorg.runtime.run_process", return_value=out):
            self.assertEqual(runtime.existing_terminal("t8")["name"], "pm-pane")
            with self.assertRaises(runtime.OrgError):
                runtime.existing_terminal("other-name")
