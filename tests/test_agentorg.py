import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentorg import cli, config, runtime


class TempOrgTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / "demo"
        self.project.mkdir()
        self._home = patch.dict(os.environ, {"AGENTORG_HOME": str(self.root / "local-profiles")})
        self._home.start()
        self.addCleanup(self._home.stop)

    def init(self, template="engineering"):
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(["init", "--path", str(self.project), "--name", "demo", "--template", template])

    def make_profiles(self):
        for alias, provider in (("reviewer", "claude"), ("implementer", "claude"), ("designer", "claude"), ("frontend", "codex")):
            with patch("agentorg.cli.which", return_value=f"/mock/{provider}"), contextlib.redirect_stdout(io.StringIO()):
                cli.main(["profile", "add", alias, "--provider", provider, "--command", provider, "--model", "test-model", "--effort", "medium"])

    def git_commit(self):
        subprocess.run(["git", "init", "-q"], cwd=self.project, check=True)
        subprocess.run(["git", "-c", "user.email=example@example.invalid", "-c", "user.name=Test", "add", ".ai", "QUESTION.md"], cwd=self.project, check=True)
        subprocess.run(["git", "-c", "user.email=example@example.invalid", "-c", "user.name=Test", "commit", "-qm", "init"], cwd=self.project, check=True)

    def test_init_no_overwrite(self):
        self.init()
        target = self.project / ".ai" / "PROJECT.md"
        target.write_text("OWN DATA", encoding="utf-8")
        self.init()
        self.assertEqual(target.read_text(encoding="utf-8"), "OWN DATA")
        self.assertEqual(config.load_project(self.project)["project_id"], "demo")
        self.assertIn("RUNTIME.json", (self.project / ".ai" / ".gitignore").read_text())

    def test_init_three_domains(self):
        for name in ("engineering", "research", "content"):
            path = self.root / name
            path.mkdir()
            with contextlib.redirect_stdout(io.StringIO()):
                cli.main(["init", "--path", str(path), "--template", name])
            doc = config.load_project(path)
            self.assertEqual(doc["kind"], "software" if name == "engineering" else name)

    def test_profile_local_only_and_no_tokens(self):
        self.init()
        local_cfg = self.root / "separate-claude"
        local_cfg.mkdir()
        with patch("agentorg.cli.which", return_value="/mock/claude"), contextlib.redirect_stdout(io.StringIO()):
            cli.main(["profile", "add", "reviewer", "--provider", "claude", "--config-dir", str(local_cfg), "--model", "opus"])
        profile_text = config.profiles_path().read_text(encoding="utf-8")
        self.assertIn(str(local_cfg), profile_text)
        self.assertNotIn("ANTHROPIC_API_KEY", profile_text)
        self.assertNotIn("reviewer", (self.project / ".ai" / "TEAM.json").read_text()[:120])
        if os.name != "nt":
            self.assertEqual(config.profiles_path().stat().st_mode & 0o777, 0o600)

    def test_profile_duplicate_requires_replace(self):
        self.make_profiles()
        with patch("agentorg.cli.which", return_value="/mock/claude"):
            ns = cli.add_parser().parse_args(["profile", "add", "reviewer", "--provider", "claude"])
            with self.assertRaises(config.OrgError):
                cli.profile_cmd(ns)

    def test_project_role_settings(self):
        self.init()
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(["role", "set", "backend-worker", "--path", str(self.project), "--profile", "my-pro", "--model", "sonnet", "--effort", "high"])
        doc = config.load_project(self.project)
        role = config.resolve_role(doc, "backend-worker")
        self.assertEqual((role["profile"], role["model"], role["effort"]), ("my-pro", "sonnet", "high"))

    def test_reject_invalid_manifest(self):
        self.init()
        p = config.project_file(self.project)
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["roles"][0]["id"] = "../../danger"
        config.write_json(p, doc)
        with self.assertRaises(config.OrgError):
            config.load_project(self.project)

    def test_software_plan_is_preview_only(self):
        self.init()
        self.make_profiles()
        self.git_commit()
        with patch("agentorg.runtime.which", return_value="/mock/bin"):
            items = runtime.start_team(self.project, apply=False)
        self.assertEqual(len(items), 4)
        self.assertFalse((self.project / ".ai" / "RUNTIME.json").exists())
        self.assertFalse((self.project.parent / ".agentorg-worktrees").exists())
        workers = [x for x in items if x["role"] in ("backend-worker", "frontend-worker")]
        self.assertEqual(len({x["cwd"] for x in workers}), 2)
        self.assertTrue(all("--outlive-parent" in x["command"] for x in items))

    def test_missing_git_commit_blocks_software_apply(self):
        self.init()
        self.make_profiles()
        subprocess.run(["git", "init", "-q"], cwd=self.project, check=True)
        with patch("agentorg.runtime.which", return_value="/mock/bin"):
            with self.assertRaises(config.OrgError):
                runtime.start_team(self.project, apply=True)

    def test_apply_reuses_existing_terminals(self):
        self.init()
        self.make_profiles()
        self.git_commit()
        seen = set()
        original = runtime.run_process
        calls = []

        def fake_run(argv, **kw):
            if argv[0] == "hc":
                calls.append(argv)
                return subprocess.CompletedProcess(argv, 0, stdout="{}", stderr="")
            return original(argv, **kw)

        def active(name, expected_labels=None):
            if name not in seen:
                return None
            role = next(x for x in config.load_project(self.project)["roles"] if runtime.terminal_name(self.project, x["id"]) == name)
            return {"name": name, "labels": runtime.role_labels(self.project, role), "state": "live"}

        def capture_run(argv, **kw):
            if argv[0] == "hc" and "run" in argv:
                seen.add(argv[argv.index("--name") + 1])
            return fake_run(argv, **kw)

        with patch("agentorg.runtime.which", return_value="/mock/bin"), \
             patch("agentorg.runtime.hc_ready"), \
             patch("agentorg.runtime.existing_terminal", side_effect=active), \
             patch("agentorg.runtime.run_process", side_effect=capture_run):
            first = runtime.start_team(self.project, apply=True)
            second = runtime.start_team(self.project, apply=True)
        self.assertEqual([x["action"] for x in first], ["launched"] * 4)
        self.assertEqual([x["action"] for x in second], ["reused"] * 4)
        self.assertEqual(len([c for c in calls if "run" in c]), 4)
        self.assertTrue((self.project / ".ai" / "RUNTIME.json").exists())
        self.assertEqual(len(list((self.project.parent / ".agentorg-worktrees").rglob(".git"))), 2)

    def test_ambiguous_get_failure_must_not_create_duplicate(self):
        response = subprocess.CompletedProcess(["hc"], 3, stdout="", stderr="permission denied")
        with patch("agentorg.runtime.run_process", return_value=response):
            with self.assertRaises(config.OrgError):
                runtime.existing_terminal("ao-x")

    def test_finished_terminal_is_not_reused(self):
        response = subprocess.CompletedProcess(["hc"], 0, stdout=json.dumps({"name": "ao-x", "state": "finished"}), stderr="")
        with patch("agentorg.runtime.run_process", return_value=response):
            self.assertIsNone(runtime.existing_terminal("ao-x"))

    def test_mismatched_existing_profile_is_blocked(self):
        response = subprocess.CompletedProcess(["hc"], 0, stdout=json.dumps({"name": "ao-x", "state": "live", "labels": {"profile": "wrong"}}), stderr="")
        with patch("agentorg.runtime.run_process", return_value=response):
            with self.assertRaises(config.OrgError):
                runtime.existing_terminal("ao-x", {"profile": "right"})

    def test_explicit_claude_config_clears_inherited_token(self):
        self.init()
        local_cfg = self.root / "claude-work"
        local_cfg.mkdir()
        profiles = {"reviewer": {"provider": "claude", "command": "claude", "config_dir": str(local_cfg), "model": "opus", "effort": "medium"}}
        config.save_profiles(profiles)
        doc = config.load_project(self.project)
        doc["roles"] = [doc["roles"][0]]
        config.write_json(config.project_file(self.project), doc)
        seen = {}

        def fake_exec(binary, argv, env):
            seen["cmd"], seen["env"] = argv, env
            raise RuntimeError("capture")

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "not-for-this-profile", "CLAUDE_CONFIG_DIR": "/wrong"}), \
             patch("agentorg.runtime.os.execvpe", side_effect=fake_exec):
            with self.assertRaisesRegex(RuntimeError, "capture"):
                runtime.launch_agent_process(self.project, "technical-reviewer")
        self.assertNotIn("ANTHROPIC_API_KEY", seen["env"])
        self.assertEqual(seen["env"]["CLAUDE_CONFIG_DIR"], str(local_cfg))
        self.assertIn("--effort", seen["cmd"])

    def test_skill_package_contents(self):
        source = cli.skill_sources()
        for skill in ("agent-org-manager", "agent-org-engineering", "agent-org-bootstrap", "agent-org-recovery"):
            txt = source.joinpath(skill, "SKILL.md").read_text(encoding="utf-8")
            self.assertTrue(txt.startswith("---\n"))
            self.assertIn("description:", txt)

    def test_role_set_reviewer_routing_cli(self):
        self.init()
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(["role", "set", "backend-worker", "--path", str(self.project), "--reviewer-role", "design-reviewer"])
        doc = config.load_project(self.project)
        self.assertEqual(config.resolve_role(doc, "backend-worker")["reviewer_role"], "design-reviewer")
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(["role", "set", "backend-worker", "--path", str(self.project), "--clear-reviewer-role"])
        doc = config.load_project(self.project)
        self.assertNotIn("reviewer_role", config.resolve_role(doc, "backend-worker"))

    def test_reviewer_route_prompt_targets_existing_terminal(self):
        self.init()
        doc = config.load_project(self.project)
        worker = config.resolve_role(doc, "backend-worker")
        reviewer = config.resolve_role(doc, "technical-reviewer")
        reviewer_term = runtime.terminal_name(self.project, reviewer["id"])
        worker_prompt = runtime.make_agent_prompt(self.project, worker)
        reviewer_prompt = runtime.make_agent_prompt(self.project, reviewer)
        self.assertIn(reviewer_term, worker_prompt)
        self.assertIn("without routing routine turns through PM", worker_prompt)
        self.assertIn("Do not wake PM for normal review rounds", reviewer_prompt)

    def test_reviewer_route_must_reference_enabled_reviewer(self):
        self.init()
        doc = config.load_project(self.project)
        worker = config.resolve_role(doc, "backend-worker")
        worker["reviewer_role"] = "missing"
        config.write_json(config.project_file(self.project), doc)
        with self.assertRaises(config.OrgError):
            config.load_project(self.project)
        worker["reviewer_role"] = "frontend-worker"
        config.write_json(config.project_file(self.project), doc)
        with self.assertRaises(config.OrgError):
            config.load_project(self.project)

    def test_antigravity_and_all_skill_install_targets(self):
        from types import SimpleNamespace
        fake_home = self.root / "fake-home"
        fake_home.mkdir()
        with patch("agentorg.cli.Path.home", return_value=fake_home), \
             patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(fake_home / "claude")}, clear=False), \
             contextlib.redirect_stdout(io.StringIO()):
            cli.install_skills(SimpleNamespace(target="antigravity", force=False))
            self.assertTrue((fake_home / ".gemini/config/skills/agent-org-manager/SKILL.md").exists())
            self.assertFalse((fake_home / ".agents/skills/agent-org-manager").exists())
            cli.install_skills(SimpleNamespace(target="all", force=False))
            self.assertTrue((fake_home / ".agents/skills/agent-org-manager/SKILL.md").exists())
            self.assertTrue((fake_home / "claude/skills/agent-org-manager/SKILL.md").exists())

    def test_terminal_name_deterministic_safe(self):
        a = runtime.terminal_name(self.project, "backend-worker")
        self.assertEqual(a, runtime.terminal_name(self.project, "backend-worker"))
        self.assertLessEqual(len(a), 32)
        self.assertNotEqual(a, runtime.terminal_name(self.project, "frontend-worker"))


if __name__ == "__main__":
    unittest.main()
