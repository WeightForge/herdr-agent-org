"""v0.7.0: profile detect, role add/remove, role titles. A temp HOME is used; the real home is never read."""
import contextlib
import io
import json
import re
import unittest
from pathlib import Path
from unittest.mock import patch

from test_v03 import Fixture
from agentorg import cli, config

ROOT = Path(__file__).resolve().parents[1]


class DetectTest(Fixture):
    def setUp(self):
        super().setUp()
        self.home = self.root / "home"
        self.home.mkdir()
        self.addCleanup(patch.stopall)
        patch("pathlib.Path.home", return_value=self.home).start()
        self.which = {"claude": "/m/claude", "codex": "/m/codex", "agy": "/m/agy"}
        patch("agentorg.cli.which", side_effect=lambda c: self.which.get(c)).start()

    def mk(self, name, *files):
        d = self.home / name
        d.mkdir()
        for f in files:
            if f.endswith("/"):
                (d / f).mkdir()
            else:
                (d / f).write_text("junk {{ not json or toml", encoding="utf-8")
        return d

    def run_cli(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.main(list(args))
        return json.loads(buf.getvalue())

    def test_detect_rules(self):
        self.mk(".claude", ".credentials.json")
        work = self.mk(".claude-work", "projects/")
        self.mk(".claude-empty")  # no marker: skipped
        self.mk(".codex", "config.toml")
        self.mk(".codex-two", "auth.json")
        self.mk(".codexnope", "config.toml")  # not .codex-*: skipped
        (self.home / ".claude.json").write_text("{}", encoding="utf-8")  # a file: skipped
        (self.home / ".claude-file").write_text("x", encoding="utf-8")
        out = self.run_cli("profile", "detect")["profiles"]
        by = {p["alias"]: p for p in out}
        self.assertEqual(set(by), {"claude", "claude-work", "codex", "codex-two", "antigravity"})
        self.assertIsNone(by["claude"]["config_dir"])
        self.assertIsNone(by["codex"]["config_dir"])
        self.assertIsNone(by["antigravity"]["config_dir"])
        self.assertEqual(Path(by["claude-work"]["config_dir"]), work.resolve())
        self.assertTrue(all(p["command_found"] and p["registered_as"] is None for p in out))
        self.assertEqual(set(by["claude"]), {"alias", "provider", "config_dir", "command_found", "registered_as"})

    def test_detect_never_opens_files(self):
        self.mk(".claude", "settings.json")
        with patch("builtins.open", side_effect=AssertionError("opened")), patch("pathlib.Path.read_text", side_effect=AssertionError("read")), \
                patch("pathlib.Path.read_bytes", side_effect=AssertionError("read")):
            self.assertEqual(len(self.run_cli("profile", "detect")["profiles"]), 2)

    def test_command_missing_and_agy_absent(self):
        self.mk(".codex", "config.toml")
        self.which.pop("codex")
        self.which.pop("agy")
        out = self.run_cli("profile", "detect", "--add")
        self.assertEqual([(p["alias"], p["command_found"]) for p in out["profiles"]], [("codex", False)])
        self.assertEqual(out["added"], [])
        self.assertFalse(config.profiles_path().exists())

    def test_add_registers_default_dirs_as_null_and_marks_registered(self):
        self.mk(".claude", "settings.json")
        work = self.mk(".claude-work", "settings.json")
        out = self.run_cli("profile", "detect", "--add")
        self.assertEqual(out["added"], ["claude", "claude-work", "antigravity"])
        profiles = config.load_profiles()
        self.assertIsNone(profiles["claude"]["config_dir"])
        self.assertEqual(Path(profiles["claude-work"]["config_dir"]), work.resolve())
        self.assertIsNone(profiles["claude"]["model"])
        again = self.run_cli("profile", "detect", "--add")
        self.assertEqual(again["added"], [])
        self.assertEqual({p["alias"]: p["registered_as"] for p in again["profiles"]},
                         {"claude": "claude", "claude-work": "claude-work", "antigravity": "antigravity"})

    def test_already_registered_under_other_alias_is_not_added(self):
        d = self.mk(".claude-work", "settings.json")
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(["profile", "add", "mine", "--provider", "claude", "--config-dir", str(d)])
        out = self.run_cli("profile", "detect", "--add")
        item = [p for p in out["profiles"] if p["alias"] == "claude-work"][0]
        self.assertEqual(item["registered_as"], "mine")
        self.assertNotIn("claude-work", config.load_profiles())

    def test_alias_taken_by_different_profile_is_skipped(self):
        self.mk(".codex-two", "auth.json")
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(["profile", "add", "codex-two", "--provider", "claude"])
        out = self.run_cli("profile", "detect", "--add")
        self.assertEqual([s["alias"] for s in out["skipped"]], ["codex-two"])
        self.assertEqual(config.load_profiles()["codex-two"]["provider"], "claude")

    def test_invalid_alias_is_skipped_not_fatal(self):
        self.mk(".claude-My.Work", "settings.json")
        out = self.run_cli("profile", "detect", "--add")
        self.assertEqual([s["alias"] for s in out["skipped"]], ["claude-My.Work"])
        self.assertEqual(out["added"], ["antigravity"])


class RoleTitleTest(Fixture):
    def add(self, *extra, rid="ai-scientist"):
        args = ["role", "add", rid, "--path", str(self.project), "--mode", "reviewer", "--title", "Senior AI Scientist",
                "--focus", "Model evaluation and research method", "--profile", "reviewer"] + list(extra)
        with contextlib.redirect_stdout(io.StringIO()):
            cli.role_cmd(cli.add_parser().parse_args(args))

    def test_add_and_set_title_focus(self):
        self.init()
        self.add()
        role = config.resolve_role(config.load_project(self.project), "ai-scientist")
        self.assertEqual((role["title"], role["mode"], role["enabled"]), ("Senior AI Scientist", "reviewer", True))
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(["role", "add", "ai-eng", "--path", str(self.project), "--mode", "worker", "--title", "Senior AI Engineer",
                      "--focus", "Training pipelines", "--profile", "implementer", "--reviewer-role", "ai-scientist", "--model", "m1"])
            cli.main(["role", "set", "ai-eng", "--path", str(self.project), "--title", "Staff AI Engineer", "--focus", "Serving"])
        role = config.resolve_role(config.load_project(self.project), "ai-eng")
        self.assertEqual((role["title"], role["focus"], role["reviewer_role"], role["model"]), ("Staff AI Engineer", "Serving", "ai-scientist", "m1"))

    def test_add_rejects_duplicates_bad_routes_and_unsafe_text_without_writing(self):
        self.init()
        before = config.project_file(self.project).read_bytes()
        for fn in (lambda: self.add(rid="technical-reviewer"),
                   lambda: self.add("--reviewer-role", "technical-reviewer"),  # reviewer cannot have a reviewer_role
                   lambda: self.add(rid="Bad Id")):
            with self.assertRaises(config.OrgError):
                fn()
        with self.assertRaises(config.OrgError):
            cli.role_cmd(cli.add_parser().parse_args(["role", "add", "x1", "--path", str(self.project), "--mode", "worker",
                                                      "--title", "A & B", "--focus", "f", "--profile", "reviewer"]))
        with self.assertRaises(config.OrgError):
            cli.role_cmd(cli.add_parser().parse_args(["role", "set", "backend-worker", "--path", str(self.project), "--title", "50%"]))
        self.assertEqual(config.project_file(self.project).read_bytes(), before)

    def test_remove(self):
        self.init()
        before = config.project_file(self.project).read_bytes()
        with self.assertRaisesRegex(config.OrgError, "enabled worker.*backend-worker.*route"):
            cli.role_cmd(cli.add_parser().parse_args(["role", "remove", "technical-reviewer", "--path", str(self.project)]))
        self.assertEqual(config.project_file(self.project).read_bytes(), before)
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(["role", "remove", "frontend-worker", "--path", str(self.project)])
            cli.main(["role", "remove", "design-reviewer", "--path", str(self.project)])
        self.assertEqual([r["id"] for r in config.load_project(self.project)["roles"]], ["technical-reviewer", "backend-worker"])
        with self.assertRaises(config.OrgError):
            cli.role_cmd(cli.add_parser().parse_args(["role", "remove", "nope", "--path", str(self.project)]))


class SkillTest(unittest.TestCase):
    def test_bootstrap_skill_is_one_question_flow(self):
        text = (ROOT / "src" / "agentorg" / "data" / "skills" / "agent-org-bootstrap" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("profile detect", text)
        self.assertIn("Start this team, or tell me what to change?", text)
        self.assertFalse(any(0xE00 <= ord(c) <= 0xE7F for c in text))


if __name__ == "__main__":
    unittest.main()
