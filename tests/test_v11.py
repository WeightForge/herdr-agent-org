"""v1.1.0: per-role skills (discovery, validation, prompt, plan warning) and pane names. Fake folder trees, mocked herdr-app."""
import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentorg import cli, config, runtime
from agentorg.skills import discover_skills
from test_panes import RESULTS, FakeHerdr
from test_v03 import Fixture


def skill(folder: Path, name: str, desc: str, key_name=True):
    folder.mkdir(parents=True, exist_ok=True)
    head = f"name: {name}\n" if key_name else ""
    (folder / "SKILL.md").write_text(f"---\n{head}description: {desc}\n---\nbody\n", encoding="utf-8")


class DiscoveryTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)

    def names(self, provider, cfg=None):
        return {s["name"]: s for s in discover_skills(provider, cfg, home=self.home)}

    def test_claude_user_and_plugin_skills_use_installed_version(self):
        base = self.home / ".claude"
        skill(base / "skills" / "grilling", "grilling", "Stress-test a plan. Second sentence is dropped.")
        cache = base / "plugins" / "cache" / "mk" / "ponytail"
        skill(cache / "4.0.0" / "skills" / "ponytail-review", "ponytail-review", "old")
        skill(cache / "5.0.0" / "skills" / "ponytail-review", "ponytail-review", "Review for bloat.")
        skill(cache / "5.0.0" / "skills" / "ponytail-gain", "ponytail-gain", "x")
        skill(base / "plugins" / "cache" / "mk" / "humanizer" / "3.1.0", "humanizer", "Rewrite prose.")  # root SKILL.md
        skill(base / "plugins" / "cache" / "mk" / "agent-org" / "1.0.0" / "skills" / "agent-org-manager", "agent-org-manager", "ours")
        (base / "plugins" / "installed_plugins.json").write_text(
            json.dumps({"plugins": {"ponytail@mk": [{"version": "4.0.0"}]}}), encoding="utf-8")
        got = self.names("claude")
        self.assertEqual(got["grilling"]["description"], "Stress-test a plan.")
        self.assertEqual(got["grilling"]["source"], "user")
        self.assertEqual(got["ponytail:ponytail-review"]["description"], "old")  # installed_plugins.json wins over newest
        self.assertEqual(got["ponytail:ponytail-review"]["source"], "ponytail")
        self.assertIn("humanizer:humanizer", got)
        self.assertTrue(got["agent-org:agent-org-manager"]["builtin"])
        self.assertFalse(got["grilling"]["builtin"])

    def test_claude_config_dir_overrides_home_and_description_is_truncated(self):
        cfg = self.home / "work-claude"
        skill(cfg / "skills" / "long", "long", "word " * 60 + ".")
        skill(self.home / ".claude" / "skills" / "other", "other", "not read")
        got = self.names("claude", cfg)
        self.assertEqual(list(got), ["long"])
        self.assertLessEqual(len(got["long"]["description"]), 120)
        self.assertTrue(got["long"]["description"].endswith("..."))

    def test_codex_user_shared_and_plugin_skills_dedupe(self):
        skill(self.home / ".codex" / "skills" / "a", "a", "codex a")
        skill(self.home / ".agents" / "skills" / "a", "a", "shared a")  # duplicate: first wins
        skill(self.home / ".agents" / "skills" / "folder-only", "x", "unused", key_name=False)
        skill(self.home / ".codex" / "plugins" / "cache" / "mk" / "pdf" / "1.0" / "skills" / "pdf", "pdf", "Read PDFs.")
        got = self.names("codex")
        self.assertEqual(got["a"]["description"], "codex a")
        self.assertEqual(got["pdf"]["source"], "pdf")
        self.assertIn("folder-only", got)  # folder name when frontmatter has no name
        self.assertEqual(len(discover_skills("codex", None, home=self.home)), 3)

    def test_antigravity_user_and_plugin_skills(self):
        base = self.home / ".gemini" / "config"
        skill(base / "skills" / "debug", "debug", "Debug things.")
        skill(base / "plugins" / "agent-org" / "skills" / "agent-org-recovery", "agent-org-recovery", "ours")
        got = self.names("antigravity")
        self.assertEqual(set(got), {"debug", "agent-org-recovery"})
        self.assertTrue(got["agent-org-recovery"]["builtin"])

    def test_block_scalar_description_and_missing_dirs(self):
        d = self.home / ".claude" / "skills" / "blocky"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("---\nname: blocky\ndescription: >\n  First line\n  continues. Next.\n---\n", encoding="utf-8")
        self.assertEqual(self.names("claude")["blocky"]["description"], "First line continues.")
        self.assertEqual(discover_skills("codex", None, home=self.home / "nothing"), [])

    def test_unsafe_names_are_dropped(self):
        skill(self.home / ".claude" / "skills" / "bad", 'bad"name & more', "x")
        self.assertEqual(self.names("claude"), {})


class SkillsFieldTest(Fixture):
    def role_set(self, *args):
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(["role", "set", "backend-worker", "--path", str(self.project), *args])

    def test_validation(self):
        good = {"schema_version": 2, "project_id": "p", "kind": "software",
                "roles": [{"id": "w", "mode": "worker", "profile": "p", "skills": ["code-review", "ponytail:ponytail"]}]}
        config.validate_project(good)
        for bad in (["bad name"], ["a"] * 2, [f"s{i}" for i in range(9)], "code-review", [""], ['x"y'], [1]):
            good["roles"][0]["skills"] = bad
            with self.assertRaises(config.OrgError, msg=str(bad)):
                config.validate_project(good)
        del good["roles"][0]["skills"]
        config.validate_project(good)  # old TEAM.json without skills stays valid

    def test_role_set_skills_and_clear(self):
        self.init()
        self.role_set("--skills", "code-review, ponytail:ponytail")
        role = config.resolve_role(config.load_project(self.project), "backend-worker")
        self.assertEqual(role["skills"], ["code-review", "ponytail:ponytail"])
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            self.role_set("--skills", "bad name")
        self.role_set("--skills", "")
        self.assertNotIn("skills", config.resolve_role(config.load_project(self.project), "backend-worker"))

    def test_prompt_sentence_only_with_skills(self):
        self.init()
        doc = config.load_project(self.project)
        role = config.resolve_role(doc, "backend-worker")
        self.assertNotIn("Skills for this role", runtime.make_agent_prompt(self.project, role))
        role["skills"] = ["code-review", "scrutinize"]
        self.assertIn("Skills for this role (use them when they apply): code-review, scrutinize.", runtime.make_agent_prompt(self.project, role))

    def test_plan_warns_for_missing_skill_only(self):
        self.init()
        self.make_profiles()
        self.git_commit()
        self.role_set("--skills", "code-review,nope")
        found = [{"name": "code-review", "description": "", "source": "user", "builtin": False}]
        err, report = io.StringIO(), {}
        with patch("agentorg.runtime.which", return_value="/mock/bin"), patch("agentorg.runtime.discover_skills", return_value=found), \
             contextlib.redirect_stderr(err):
            items = runtime.start_team(self.project, apply=False, report=report)
        self.assertEqual(len(items), 4)  # warning, not failure
        self.assertEqual(report["warnings"], ["Role backend-worker: skill nope not installed for profile implementer"])
        self.assertIn("skill nope not installed for profile implementer", err.getvalue())

    def test_profile_skills_cli_json(self):
        self.make_profiles()
        out = io.StringIO()
        found = [{"name": "a", "description": "d", "source": "user", "builtin": False}]
        with patch("agentorg.cli.discover_skills", return_value=found) as disc, contextlib.redirect_stdout(out):
            cli.main(["profile", "skills", "frontend", "--json"])
        self.assertEqual(json.loads(out.getvalue()), {"frontend": {"provider": "codex", "skills": found}})
        disc.assert_called_once_with("codex", None)
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            cli.main(["profile", "skills", "ghost"])


@patch("agentorg.runtime.time.sleep", lambda s: None)
class PaneNameTest(unittest.TestCase):
    def test_pane_rename_after_placement_and_failure_only_warns(self):
        roles = [{"id": "r1", "mode": "reviewer", "title": "Tech Lead", "profile": "a"},
                 {"id": "r2", "mode": "reviewer", "profile": "b"},
                 {"id": "w1", "mode": "worker", "reviewer_role": "r1", "title": "Dev", "profile": "a"},
                 {"id": "w2", "mode": "worker", "reviewer_role": "r2", "title": "QA", "profile": "b"}]
        profiles = {"a": {"provider": "claude"}, "b": {"provider": "codex"}}
        fake = FakeHerdr()

        def flaky(argv, **kw):
            if argv[:3] == ["herdr-app", "do", "pane.rename"] and argv[4] == "pt4":
                fake.calls.append(argv[1:])
                import subprocess
                return subprocess.CompletedProcess(argv, 1, stdout="", stderr="nope")
            return fake(argv, **kw)
        err = io.StringIO()
        with patch("agentorg.runtime.load_project", lambda p: {"roles": roles}), patch("agentorg.runtime.load_profiles", return_value=profiles), \
             patch("agentorg.runtime.run_process", side_effect=flaky), patch("agentorg.runtime.which", return_value="/mock/herdr-app"), \
             patch("agentorg.runtime.pm_terminal", return_value="tPM"), contextlib.redirect_stderr(err):
            out = runtime.arrange_panes(Path("."), RESULTS)
        self.assertEqual(out, {"arranged": ["r1", "r2", "w1", "w2"]})
        renames = [c[2:] for c in fake.calls if c[:2] == ["do", "pane.rename"]]
        self.assertEqual(renames, [["--pane", "pt1", "--name", "Tech Lead · claude"], ["--pane", "pt2", "--name", "r2 · codex"],
                                   ["--pane", "pt3", "--name", "Dev · claude"], ["--pane", "pt4", "--name", "QA · codex"]])
        self.assertIn("could not name pane for w2", err.getvalue())


if __name__ == "__main__":
    unittest.main()


class ManifestSkillPathTest(unittest.TestCase):
    def test_plugin_manifest_skills_path_is_followed(self):
        # live: ui-ux-pro-max declares "skills": "./.claude/skills/" and was missed
        import tempfile
        from agentorg.skills import discover_skills
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".claude" / "plugins" / "cache" / "m" / "uiux" / "2.0"
            (root / ".claude-plugin").mkdir(parents=True)
            (root / ".claude-plugin" / "plugin.json").write_text('{"skills": "./.claude/skills/"}', encoding="utf-8")
            s = root / ".claude" / "skills" / "design-system"
            s.mkdir(parents=True)
            (s / "SKILL.md").write_text("---\nname: design-system\ndescription: Tokens.\n---\n", encoding="utf-8")
            (root / ".claude-plugin" / "evil").mkdir()
            names = [x["name"] for x in discover_skills("claude", home=tmp)]
            self.assertIn("uiux:design-system", names)
            (root / ".claude-plugin" / "plugin.json").write_text('{"skills": "../../../../../../outside"}', encoding="utf-8")
            self.assertNotIn("uiux:design-system", [x["name"] for x in discover_skills("claude", home=tmp)])


class TrustPromptTest(unittest.TestCase):
    def test_answers_each_provider_prompt_once_then_waits_for_ready(self):
        # live: a dispatch typed into Codex's trust prompt opened its Agent Command Center and forked an old session
        screens = {"cx": ["loading", "Trust this folder?\n1. Trust and continue", "Trust this folder?", "Ask Codex to do anything"],
                   "ag": ["Do you trust the contents of this project?", "Running..."],
                   "cl": ["Yes, I trust this folder", "bypass permissions on"],
                   "ready": ["Ask Codex to do anything"]}
        sent = []

        def proc(argv, **kw):
            if argv[1] == "read":
                seq = screens[argv[2]]
                out = seq.pop(0) if len(seq) > 1 else seq[0]
                return subprocess.CompletedProcess(argv, 0, stdout=out, stderr="")
            sent.append(argv[2:])
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
        with patch("agentorg.runtime.run_process", side_effect=proc), patch("agentorg.runtime.time.sleep"):
            left = runtime.accept_trust_prompts([("cx", "codex"), ("ag", "antigravity"), ("cl", "claude"), ("ready", "codex")], timeout=30)
        self.assertEqual(left, [])
        self.assertEqual(sorted(sent), [["ag", "enter"], ["cl", "down", "enter"], ["cx", "enter"]])

    def test_timeout_warns_and_returns_stuck_terminals(self):
        proc = lambda argv, **kw: subprocess.CompletedProcess(argv, 0, stdout="still loading", stderr="")
        err = io.StringIO()
        with patch("agentorg.runtime.run_process", side_effect=proc), patch("agentorg.runtime.time.sleep"), \
             patch("agentorg.runtime.time.time", side_effect=[0, 0, 100, 100]), contextlib.redirect_stderr(err):
            self.assertEqual(runtime.accept_trust_prompts([("cx", "codex")], timeout=5), ["cx"])
        self.assertIn("WARNING", err.getvalue())
