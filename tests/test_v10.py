"""v1.0.0: concurrency warnings, watcher event wakes, cleanup, project registration. hc is mocked; git is a real temp repo."""
import contextlib
import io
import json
import os
import subprocess
import time
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agentorg import cli, config, runtime
from test_v03 import Fixture
from test_v08 import WatchTest

GIT = ["git", "-c", "user.email=example@example.invalid", "-c", "user.name=Test"]


class TaskMixin:
    def task(self, tid, state="started", worker=None, paths=None, extra=""):
        d = self.project / ".ai" / "tasks" / tid
        d.mkdir(parents=True, exist_ok=True)
        lines = [f"TASK {tid}"] + ([f"Worker: {worker}"] if worker else []) + ([f"Paths: {paths}"] if paths else [])
        (d / "packet.md").write_text("\n".join(lines) + "\n" + extra, encoding="utf-8")
        (d / "progress.md").write_text(f"State: {state}\n", encoding="utf-8")


class WarningsTest(TaskMixin, Fixture):
    def flags(self):
        return {t["id"]: t["flags"] for t in runtime.task_states(self.project)}

    def test_worker_busy_and_overlap_flags(self):
        self.init()
        self.task("a", worker="w1", paths="src/api, docs\\x.md")
        self.task("b", worker="w1", paths="./src/api/routes.py")
        self.task("c", worker="w2", paths="src/*.py")
        self.task("d", worker="w2", paths="lib")
        self.task("e", state="done", worker="w1", paths="src/api")
        got = self.flags()
        self.assertEqual(got["a"], ["worker_busy", "overlap:b"])
        self.assertEqual(got["b"], ["worker_busy", "overlap:a", "overlap:c"])  # fnmatch: src/*.py matches src/api/routes.py
        self.assertEqual(got["c"], ["worker_busy", "overlap:b"])  # but not the directory src/api
        self.assertEqual(got["e"], [])  # finished tasks are never flagged

    def test_glob_overlap_and_old_packet_without_fields(self):
        self.init()
        self.task("a", paths="src/*.py")
        self.task("b", paths="src/main.py")
        self.task("old")  # no Worker/Paths: still parses, no flags
        got = self.flags()
        self.assertEqual((got["a"], got["b"], got["old"]), (["overlap:b"], ["overlap:a"], []))

    def test_reassign_worker_overrides_packet(self):
        self.init()
        self.task("a", worker="w1")
        self.task("b", worker="w2")
        (self.project / ".ai" / "tasks" / "b" / "reassign.md").write_text("Revision: 1\nWorker: w1\n", encoding="utf-8")
        self.assertIn("worker_busy", self.flags()["a"])

    def test_max_parallel_warning_in_status_and_send_warning(self):
        self.init()
        self.make_profiles()
        limit = config.load_project(self.project)["policies"]["max_parallel_workers"]
        for i in range(limit + 1):
            self.task(f"t{i}", worker="backend-worker", paths=f"p{i}")
        out = io.StringIO()
        with patch("agentorg.cli.hc_ready"), patch("agentorg.cli.existing_terminal", return_value=None), patch("agentorg.cli.role_labels", return_value={}), \
             contextlib.redirect_stdout(out):
            cli.team_cmd(SimpleNamespace(path=str(self.project), op="status", stale_minutes=20))
        data = json.loads(out.getvalue())
        self.assertIn(f"active tasks {limit + 1} exceed policies.max_parallel_workers {limit}", data["warnings"])
        self.assertIsNone(data["watcher_last_wake"])
        err, sent = io.StringIO(), []
        ns = SimpleNamespace(path=str(self.project), op="send", role="backend-worker", message="path .ai/tasks/t0/packet.md", wait=False)
        with patch("agentorg.cli.hc_ready"), patch("agentorg.cli.existing_terminal", return_value={"name": "x"}), patch("agentorg.cli.role_labels", return_value={}), \
             patch("agentorg.cli.run_process", side_effect=lambda a, **k: sent.append(a) or SimpleNamespace(returncode=0, stdout="ok", stderr="")), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            cli.team_cmd(ns)
        self.assertIn("t1", err.getvalue())
        self.assertNotIn("t0,", err.getvalue())
        self.assertEqual(len(sent), 1)  # warned, not refused


class EventWakeTest(TaskMixin, Fixture):
    watch = WatchTest.watch  # reuse the mocked-hc helper without re-collecting WatchTest's tests

    def setUp(self):
        super().setUp()
        self.init()
        self.inbox = self.project / ".ai" / "inbox"
        self.inbox.mkdir(parents=True)

    def test_inbox_wakes_once_across_restart_even_without_open_tasks(self):
        (self.inbox / "20260101T000000Z-t1-milestone_ready-ab12.md").write_text("x", encoding="utf-8")
        result, sent = self.watch(None)
        self.assertEqual(result["action"], "woke_pm")
        self.assertIn("WATCHDOG: new escalation .ai/inbox/20260101T000000Z-t1-milestone_ready-ab12.md", sent[0][3])
        again, sent = self.watch(None)  # a restarted watcher reads only RUNTIME.json
        self.assertEqual((again["action"], sent), ("none", []))
        (self.inbox / "20260101T000100Z-t2-blocked-cd34.md").write_text("x", encoding="utf-8")
        result, sent = self.watch(None)  # a new file wakes again, no stale throttle
        self.assertEqual(result["action"], "woke_pm")
        self.assertIn("t2-blocked", sent[0][3])
        runtime_doc = config.read_json(self.project / ".ai" / "RUNTIME.json")
        self.assertEqual(len(runtime_doc["announced"]), 2)
        self.assertIn("escalation", runtime_doc["watch_last_wake"]["reason"])

    def test_handled_inbox_file_does_not_wake(self):
        (self.inbox / "20260101T000000Z-t1-blocked-ab12.md").write_text("x", encoding="utf-8")
        (self.project / ".ai" / "STATE.md").write_text("## Handled escalations\n20260101T000000Z-t1-blocked-ab12\n", encoding="utf-8")
        self.assertEqual(self.watch(None)[0]["action"], "none")

    def test_busy_pm_skips_and_does_not_mark_announced(self):
        (self.inbox / "20260101T000000Z-t1-blocked-ab12.md").write_text("x", encoding="utf-8")
        result, sent = self.watch({"status": {"state": "working"}})
        self.assertEqual((result["action"], sent), ("send_skipped", []))
        self.assertEqual(self.watch(None)[0]["action"], "woke_pm")

    def test_question_answer_wakes_once_per_answer(self):
        q = self.project / "QUESTION.md"
        q.write_text("# Q\n\n## Use Postgres?\nOptions: A, B\nAnswer:\n", encoding="utf-8")
        self.assertEqual(self.watch(None)[0]["action"], "none")  # unanswered
        q.write_text("# Q\n\n## Use Postgres?\nOptions: A, B\nAnswer: B\n", encoding="utf-8")
        result, sent = self.watch(None)
        self.assertEqual(result["action"], "woke_pm")
        self.assertIn("WATCHDOG: owner answered QUESTION.md", sent[0][3])
        self.assertEqual(self.watch(None)[0]["action"], "none")
        q.write_text("# Q\n\n## Use Postgres?\nOptions: A, B\nAnswer: B\n\nResolved: merged.\n", encoding="utf-8")  # PM edits, keeps Answer:
        self.assertEqual(self.watch(None)[0]["action"], "none")
        q.write_text("# Q\n\n## Use Postgres?\nAnswered: B\n\n## Ship it?\nAnswer: B\n", encoding="utf-8")  # same text, new question
        self.assertEqual(self.watch(None)[0]["action"], "woke_pm")

    def test_event_wake_carries_warnings(self):
        self.task("a", worker="w1", paths="src")
        self.task("b", worker="w1", paths="src/x")
        (self.inbox / "20260101T000000Z-t1-blocked-ab12.md").write_text("x", encoding="utf-8")
        _, sent = self.watch(None)
        self.assertIn("overlapping Paths", sent[0][3])
        self.assertIn("more than one active task", sent[0][3])


class GuessWorkerTest(TaskMixin, Fixture):
    def test_packet_without_worker_field(self):
        # live: a 0.9 PM wrote no Worker line, so cleanup could not map the task to a worktree
        self.init()
        self.task("a", extra="Scope / worktree+branch: D:\\wt\\backend-worker only\nReviewer: technical-reviewer\n")
        self.task("b", extra="Reviewer: technical-reviewer\n")
        self.task("c", extra="Reviewer: nobody\n")
        workers = {t["id"]: t["worker"] for t in runtime.task_states(self.project, full=True)}
        self.assertEqual(workers, {"a": "backend-worker", "b": "backend-worker", "c": None})


class CleanupTest(TaskMixin, Fixture):
    def setUp(self):
        super().setUp()
        self.init()
        self.make_profiles()
        self.git_commit()
        doc = config.load_project(self.project)
        self.role = config.resolve_role(doc, "backend-worker")
        self.loc = runtime.ensure_worktree(self.project, self.role)
        self.branch = runtime.worktree_info(self.project, self.role)[1]
        live = patch("agentorg.runtime.existing_terminal", return_value=None)
        self.live = live.start()
        self.addCleanup(live.stop)

    def branches(self):
        return subprocess.run(["git", "branch", "--format=%(refname:short)"], cwd=self.project, text=True, capture_output=True).stdout.split()

    def test_dry_run_changes_nothing_then_apply_removes_clean_merged(self):
        self.task("t1", "done", worker="backend-worker")
        rows = runtime.cleanup_report(self.project)
        self.assertEqual((rows[0]["action"], rows[0]["merged"], rows[0]["dirty"]), ("would_remove", True, False))
        self.assertTrue(self.loc.exists())
        rows = runtime.cleanup_report(self.project, apply=True)
        self.assertEqual((rows[0]["action"], rows[0]["branch_result"]), ("removed", "deleted"))
        self.assertFalse(self.loc.exists())
        self.assertNotIn(self.branch, self.branches())

    def test_dirty_unmerged_and_active_are_kept(self):
        self.task("t1", "done", worker="backend-worker")
        (self.loc / "scratch.txt").write_text("wip", encoding="utf-8")
        row = runtime.cleanup_report(self.project, apply=True)[0]
        self.assertEqual((row["action"], row["reason"]), ("kept", "uncommitted or untracked files"))
        self.assertTrue(self.loc.exists())
        subprocess.run([*GIT, "add", "scratch.txt"], cwd=self.loc, check=True)
        subprocess.run([*GIT, "commit", "-qm", "wip"], cwd=self.loc, check=True)
        row = runtime.cleanup_report(self.project, apply=True)[0]
        self.assertEqual((row["action"], row["merged"], row["reason"]), ("kept", False, "branch not merged"))
        self.assertIn(self.branch, self.branches())
        subprocess.run([*GIT, "merge", "-q", self.branch], cwd=self.project, check=True)
        self.task("t2", "started", worker="backend-worker")
        row = runtime.cleanup_report(self.project, apply=True)[0]
        self.assertEqual(row["action"], "kept")
        self.assertIn("t2", row["reason"])
        self.assertTrue(self.loc.exists())

    def test_live_worker_terminal_is_kept(self):
        self.task("t1", "done", worker="backend-worker")
        self.live.return_value = {"name": "worker"}
        row = runtime.cleanup_report(self.project, apply=True)[0]
        self.assertEqual((row["action"], row["reason"]), ("kept", "worker terminal is live; run team down first"))
        self.assertTrue(self.loc.exists())

    def test_unknown_worker_is_kept(self):
        self.task("t1", "cancelled")
        (self.project / ".ai" / "tasks" / "t1" / "cancel").write_text("no", encoding="utf-8")
        self.assertEqual(runtime.cleanup_report(self.project, apply=True)[0]["action"], "kept")

    def test_cli_dry_run_by_default(self):
        self.task("t1", "done", worker="backend-worker")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli.main(["team", "cleanup", "--path", str(self.project)])
        self.assertIn('"mode": "dry_run"', out.getvalue())
        self.assertTrue(self.loc.exists())


class RegistryTest(Fixture):
    def test_status_and_resume_register_the_project(self):
        self.init()
        self.make_profiles()
        self.assertEqual(config.known_projects(), [])
        with patch("agentorg.cli.hc_ready"), patch("agentorg.cli.existing_terminal", return_value=None), patch("agentorg.cli.role_labels", return_value={}), \
             contextlib.redirect_stdout(io.StringIO()):
            cli.team_cmd(SimpleNamespace(path=str(self.project), op="status", stale_minutes=20))
        self.assertEqual(config.known_projects(), [str(self.project.resolve())])
        os.remove(config.org_home() / "projects.json")
        with patch("agentorg.cli.resume_team", return_value=[]), contextlib.redirect_stdout(io.StringIO()):
            cli.resume_cmd(SimpleNamespace(path=str(self.project), all=False, apply=False, no_panes=True))
        self.assertEqual(config.known_projects(), [str(self.project.resolve())])

    def test_resume_all_with_nothing_registered_hints(self):
        err, out = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            cli.resume_cmd(SimpleNamespace(path=".", all=True, apply=False, no_panes=True))
        self.assertIn("agentorg resume once inside each project folder", err.getvalue())
        self.assertEqual(json.loads(out.getvalue().split("\n", 1)[0] if False else out.getvalue().rsplit("}", 1)[0] + "}")["projects"], [])


if __name__ == "__main__":
    unittest.main()


class RunProcessEncodingTest(unittest.TestCase):
    def test_utf8_output_decodes_on_windows(self):
        # live: team watch crashed decoding hc's UTF-8 status text with cp1252
        out = runtime.run_process([sys.executable, "-c", "import sys; sys.stdout.buffer.write('\u2726 \u00e9 \u0e01'.encode('utf-8'))"])
        self.assertEqual(out.stdout, "✦ é ก")
