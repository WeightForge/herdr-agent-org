"""v0.8.0: autonomy field, no-prompt launch flags, protocol v2 prompts, stale tasks and the PM watchdog. All mocked."""
import contextlib
import io
import json
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agentorg import cli, config, runtime
from test_v03 import Fixture


class AutonomyTest(Fixture):
    def set_autonomy(self, value):
        p = config.project_file(self.project)
        doc = json.loads(p.read_text(encoding="utf-8"))
        if value is None:
            doc.pop("autonomy", None)
        else:
            doc["autonomy"] = value
        config.write_json(p, doc)

    def test_templates_and_example_default_to_full(self):
        for name in ("engineering", "research", "content"):
            self.assertEqual(config.template_document(name)["autonomy"], "full")
        self.assertEqual(json.loads((config.Path(__file__).resolve().parents[1] / "examples/web-app/.ai/TEAM.json").read_text(encoding="utf-8"))["autonomy"], "full")

    def test_validation_and_missing_means_supervised(self):
        self.init(autonomy="full")
        self.set_autonomy("sometimes")
        with self.assertRaisesRegex(config.OrgError, "autonomy"):
            config.load_project(self.project)
        self.set_autonomy(None)
        self.assertEqual(config.autonomy(config.load_project(self.project)), "supervised")

    def test_launch_argv_for_all_providers_in_both_modes(self):
        flags = {"claude": "--dangerously-skip-permissions", "antigravity": "--dangerously-skip-permissions",
                 "codex": "--dangerously-bypass-approvals-and-sandbox"}
        for mode in ("full", "supervised"):
            self.init(autonomy=mode) if not config.project_file(self.project).exists() else self.set_autonomy(mode)
            for provider, command in (("claude", "claude"), ("codex", "codex"), ("antigravity", "agy")):
                profiles = {"p": {"provider": provider, "command": command, "config_dir": None, "native_profile": None}}
                doc = config.load_project(self.project)
                doc["roles"][0]["profile"] = "p"
                config.write_json(config.project_file(self.project), doc)
                seen = {}

                def capture(argv, **kw):
                    seen["cmd"] = argv
                    raise RuntimeError("capture")

                with patch("agentorg.runtime.load_profiles", return_value=profiles), patch("agentorg.runtime.which", return_value="/mock/" + command), \
                     patch("agentorg.runtime.subprocess.run", side_effect=capture), patch("agentorg.runtime.os.execvpe", side_effect=lambda b, a, e: capture(a)):
                    with self.assertRaisesRegex(RuntimeError, "capture"):
                        runtime.launch_agent_process(self.project, doc["roles"][0]["id"], "t7")
                cmd = seen["cmd"]
                self.assertEqual(cmd[0], "/mock/" + command)
                if mode == "full":
                    self.assertEqual(cmd[1] if provider != "codex" else cmd[4], flags[provider], (provider, cmd[:5]))
                    self.assertEqual(sum(a.startswith("--dangerously") for a in cmd), 1)
                else:
                    self.assertFalse(any(a.startswith("--dangerously") for a in cmd), (provider, cmd[:4]))

    def test_prompts_follow_the_mode(self):
        self.init(autonomy="full")
        doc = config.load_project(self.project)
        bad_chars = set('"%&|<>^\n')
        for role in doc["roles"]:
            prompt = runtime.make_agent_prompt(self.project, role, "t7")
            self.assertIn("Autonomy is full", prompt)
            self.assertIn("QUESTION.md", prompt)
            self.assertIn("escalate blocked", prompt)
            self.assertNotIn("forbidden", prompt)
            self.assertFalse(set(prompt) & bad_chars, set(prompt) & bad_chars)
        self.set_autonomy("supervised")
        prompt = runtime.make_agent_prompt(self.project, doc["roles"][0])
        self.assertIn("hc keys to a blocked agent is forbidden", prompt)
        self.assertNotIn("Autonomy is full", prompt)

    def test_protocol_is_version_2_and_describes_both_modes(self):
        text = (config.Path(runtime.__file__).parent / "data" / "PROTOCOL.md").read_text(encoding="utf-8")
        self.assertEqual(runtime._protocol_version(text), 2)
        for needle in ("## Autonomy", "`supervised`", "`full`", "QUESTION.md", "Hard lines", "team watch"):
            self.assertIn(needle, text)


class WatchTest(Fixture):
    def task(self, tid, state):
        d = self.project / ".ai" / "tasks" / tid
        d.mkdir(parents=True, exist_ok=True)
        (d / "packet.md").write_text(f"TASK {tid}\n", encoding="utf-8")
        (d / "progress.md").write_text(f"State: {state}\n", encoding="utf-8")

    def watch(self, terminals, now=None, sent_rc=0, **kw):
        if not config.load_profiles():
            self.make_profiles()
        sent = []

        def run(argv, **k):
            sent.append(argv)
            return SimpleNamespace(returncode=sent_rc, stdout="", stderr="not idle")

        with patch("agentorg.runtime.existing_terminal", return_value=terminals), patch("agentorg.runtime.run_process", side_effect=run), \
             patch.dict("os.environ", {"HC_TERMINAL_ID": "t7"}):
            return runtime.watch_once(self.project, now=now, **kw), sent

    def test_stale_flag_only_on_open_tasks(self):
        self.init()
        self.task("t-old", "started")
        self.task("t-done", "done")
        self.task("t-blocked", "blocked")
        later = time.time() + 3600
        got = {t["id"]: t["flags"] for t in runtime.task_states(self.project, now=later)}
        self.assertEqual(got, {"t-old": ["stale"], "t-done": [], "t-blocked": []})
        self.assertEqual(runtime.task_states(self.project)[0]["flags"], [])  # fresh files are not stale

    def test_status_reports_stale_via_cli(self):
        self.init()
        self.task("t-old", "started")
        out = io.StringIO()
        ns = cli.add_parser().parse_args(["team", "status", "--path", str(self.project), "--stale-minutes", "0"])
        with patch("agentorg.cli.hc_ready"), patch("agentorg.cli.existing_terminal", return_value=None), contextlib.redirect_stdout(out):
            cli.team_cmd(ns)
        self.assertEqual(json.loads(out.getvalue())["tasks"][0]["flags"], ["stale"])

    def test_no_open_tasks_does_nothing(self):
        self.init()
        self.task("t1", "done")
        result, sent = self.watch(None, now=time.time() + 3600)
        self.assertEqual((result["action"], sent), ("none", []))

    def test_stale_task_wakes_pm_once(self):
        self.init()
        self.task("t1", "started")
        later = time.time() + 3600
        result, sent = self.watch({"status": "done"}, now=later)  # a PM that finished its turn is `done`, not `idle`
        self.assertEqual(result["action"], "woke_pm")
        self.assertEqual(result["stale"], ["t1"])
        self.assertEqual(sent[0][:3], ["hc", "send", "t7"])
        self.assertIn("agentorg team status", sent[0][3])
        again, sent2 = self.watch({"status": "done"}, now=later + 60)
        self.assertEqual((again["action"], again["reason"], sent2), ("none", "PM woken recently", []))

    def test_all_idle_wakes_but_fresh_or_working_does_not(self):
        self.init()
        self.task("t1", "started")
        soon = time.time() + 600  # not stale (20 min) but quiet for 10 min
        self.assertEqual(self.watch({"status": "working"}, now=soon)[0]["action"], "none")
        self.assertEqual(self.watch({"status": {"state": "idle"}}, now=time.time())[0]["action"], "none")  # just dispatched
        result, sent = self.watch({"status": "idle"}, now=soon)
        self.assertEqual(result["action"], "woke_pm")
        self.assertEqual(result["stale"], [])

    def test_send_refused_and_no_pm_are_reported_not_raised(self):
        self.init()
        self.task("t1", "started")
        later = time.time() + 3600
        result, _ = self.watch(None, now=later, sent_rc=1)
        self.assertEqual((result["action"], result["reason"]), ("send_skipped", "not idle"))
        for busy in ("working", "blocked"):  # never typed into a busy PM or a prompt
            result, sent = self.watch({"status": {"state": busy}}, now=later)
            self.assertEqual((result["action"], result["reason"], sent), ("send_skipped", f"PM is {busy}", []))
        with patch("agentorg.runtime.existing_terminal", return_value=None):
            with patch("agentorg.runtime.pm_terminal", return_value=None):
                self.assertEqual(runtime.watch_once(self.project, now=later)["reason"], "no PM terminal known")


if __name__ == "__main__":
    unittest.main()
