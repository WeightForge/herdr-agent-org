"""v0.5 features: PROTOCOL.md copy, prompt pointer, per-task state derivation, status output, experimental templates."""
import contextlib
import io
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agentorg import cli, config, runtime
from test_v03 import Fixture

PACKAGED = Path(runtime.__file__).parent / "data" / "PROTOCOL.md"


class ProtocolCopyTest(Fixture):
    def dest(self):
        return self.project / ".ai" / "PROTOCOL.md"

    def test_init_copies_and_is_idempotent(self):
        self.init()
        self.assertEqual(self.dest().read_text(encoding="utf-8"), PACKAGED.read_text(encoding="utf-8"))
        self.assertTrue(PACKAGED.read_text(encoding="utf-8").startswith("# Agent organization protocol\n\nProtocol version: 2\n"))
        before = self.dest().stat().st_mtime_ns
        self.assertEqual(runtime.install_protocol(self.project), "unchanged")
        self.assertEqual(self.dest().stat().st_mtime_ns, before)

    def test_older_version_is_replaced(self):
        self.init()
        self.dest().write_text("# old\n\nProtocol version: 0\n", encoding="utf-8")
        self.assertEqual(runtime.install_protocol(self.project), "updated")
        self.assertIn("Protocol version: 2", self.dest().read_text(encoding="utf-8"))

    def test_same_version_text_change_is_refreshed(self):
        self.init()
        self.dest().write_text(PACKAGED.read_text(encoding="utf-8") + "\nstale or edited\n", encoding="utf-8")
        self.assertEqual(runtime.install_protocol(self.project), "updated")
        self.assertEqual(self.dest().read_text(encoding="utf-8"), PACKAGED.read_text(encoding="utf-8"))

    def test_newer_version_is_kept_with_warning(self):
        self.init()
        text = "# mine\n\nProtocol version: 9\n"
        self.dest().write_text(text, encoding="utf-8")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(runtime.install_protocol(self.project), "kept")
        self.assertEqual(self.dest().read_text(encoding="utf-8"), text)
        self.assertIn("WARNING", err.getvalue())

    def test_team_up_apply_installs_protocol_but_plan_does_not(self):
        self.init()
        self.make_profiles()
        self.git_commit()
        self.dest().unlink()
        with patch("agentorg.runtime.which", return_value="/mock/bin"):
            runtime.start_team(self.project, apply=False)
            self.assertFalse(self.dest().exists())
            with patch("agentorg.runtime.hc_ready"), patch("agentorg.runtime.existing_terminal", return_value=object()):
                runtime.start_team(self.project, apply=True)
        self.assertTrue(self.dest().exists())

    def test_prompt_points_to_absolute_protocol_for_every_role(self):
        self.init()
        doc = config.load_project(self.project)
        want = str((self.project / ".ai" / "PROTOCOL.md").resolve())
        for role in doc["roles"]:
            prompt = runtime.make_agent_prompt(self.project, role, "t7")
            self.assertIn(f"Read {want} before acting; it is authoritative", prompt)

    def test_protocol_defines_every_state_and_code(self):
        text = PACKAGED.read_text(encoding="utf-8")
        for word in ("dispatched", "acknowledged", "started", "in_review", "done", "blocked", "cancelled", "reassigned", "Unknown delivery") + runtime.ESCALATION_CODES:
            self.assertIn(word, text)


class TaskStateTest(Fixture):
    def task(self, tid, packet="TASK x\nblocked_by: none\n", **files):
        d = self.project / ".ai" / "tasks" / tid
        d.mkdir(parents=True, exist_ok=True)
        (d / "packet.md").write_text(packet, encoding="utf-8")
        for name, text in files.items():
            (d / name.replace("_md", ".md")).write_text(text, encoding="utf-8")

    def states(self):
        return {t["id"]: t for t in runtime.task_states(self.project)}

    def test_each_state_and_next_actor(self):
        self.init()
        self.task("t-dispatched")
        self.task("t-acked", progress_md="State: acknowledged\n")
        self.task("t-started", progress_md="State: started\n")
        self.task("t-review", progress_md="State: in_review\n")
        self.task("t-done", progress_md="State: done\n")
        self.task("t-blocked", progress_md="State: blocked\n")
        self.task("t-weird", progress_md="no state here\n")
        self.task("t-cancel", progress_md="State: started\n", cancel="no longer needed\n")
        self.task("t-reassign", progress_md="State: started\nReassign-ack: 1\n", reassign_md="Revision: 2\nWorker: other\n")
        self.task("t-reassign-acked", progress_md="State: acknowledged\nReassign-ack: 2\n", reassign_md="Revision: 2\n")
        got = {k: (v["state"], v["next_actor"]) for k, v in self.states().items()}
        self.assertEqual(got, {
            "t-dispatched": ("dispatched", "reviewer"), "t-acked": ("acknowledged", "worker"), "t-started": ("started", "worker"),
            "t-review": ("in_review", "reviewer"), "t-done": ("done", "pm"), "t-blocked": ("blocked", "pm"), "t-weird": ("unknown", "unknown"),
            "t-cancel": ("cancelled", "none"), "t-reassign": ("reassigned", "reviewer"), "t-reassign-acked": ("acknowledged", "worker")})

    def test_unknown_delivery_flag_only_when_acknowledged_without_worker_ack(self):
        self.init()
        self.task("a", progress_md="State: acknowledged\n")
        self.task("b", progress_md="State: started\n")
        self.task("c", progress_md="State: acknowledged\nWaiting-on: a\n")
        self.task("d", packet="TASK d\nblocked_by: e\n", progress_md="State: acknowledged\n")
        self.task("e", progress_md="State: in_review\n")
        s = self.states()
        self.assertEqual(s["a"]["flags"], ["unknown_delivery"])
        self.assertEqual(s["b"]["flags"], [])
        self.assertEqual(s["c"]["flags"], ["waiting_on_dependency"])
        self.assertEqual(s["d"]["flags"], ["waiting_on_dependency"])
        self.task("e", progress_md="State: done\n")
        self.assertEqual(self.states()["d"]["flags"], ["unknown_delivery"])  # dependency released, worker never acked

    def test_dependency_release_with_uppercase_ids(self):
        self.init()
        self.task("T1", progress_md="State: Done\n")
        self.task("T2", packet="TASK T2\nblocked_by: T1,\n", progress_md="State: acknowledged\n")
        self.assertEqual(self.states()["T2"]["flags"], ["unknown_delivery"])
        self.task("T1", progress_md="State: in_review\n")
        self.assertEqual(self.states()["T2"]["flags"], ["waiting_on_dependency"])

    def test_junk_in_agent_written_files_never_crashes_status(self):
        self.init()
        self.task("a", progress_md="State: started\nReassign-ack: many\n", reassign_md="Revision: two\n")
        self.task("b", progress_md="State: started\nReassign-ack: \x00??\n", reassign_md="Revision: 3x\n")
        s = self.states()
        self.assertEqual(s["a"]["state"], "started")
        self.assertEqual(s["b"]["state"], "reassigned")  # "3x" parses as 3 > 0

    def test_prompt_rejects_unsafe_project_path(self):
        self.init()
        role = config.load_project(self.project)["roles"][0]
        bad = self.project.parent / "100%demo"
        with patch.object(Path, "resolve", lambda self_: bad / self_.name if self_.name == "PROTOCOL.md" else self_):
            with self.assertRaisesRegex(config.OrgError, "Project path"):
                runtime.make_agent_prompt(self.project, role)

    def test_no_tasks_dir_is_empty(self):
        self.init()
        self.assertEqual(runtime.task_states(self.project), [])

    def test_owner_decisions_exclude_handled_and_other_codes(self):
        self.init()
        inbox = self.project / ".ai" / "inbox"
        (inbox / "done").mkdir(parents=True)
        for name in ("20260101T000000Z-t1-requires_owner_decision-aaaa", "20260101T000001Z-t2-safety_or_cost_risk-bbbb",
                     "20260101T000002Z-t3-blocked-cccc", "20260101T000003Z-t4-requires_owner_decision-dddd"):
            (inbox / (name + ".md")).write_text("x", encoding="utf-8")
        (inbox / "done" / "20260101T000004Z-t5-requires_owner_decision-eeee.md").write_text("x", encoding="utf-8")
        state = self.project / ".ai" / "STATE.md"
        state.write_text(state.read_text(encoding="utf-8") + "\n20260101T000003Z-t4-requires_owner_decision-dddd\n", encoding="utf-8")
        self.assertEqual(runtime.pending_owner_decisions(self.project),
                         ["20260101T000000Z-t1-requires_owner_decision-aaaa", "20260101T000001Z-t2-safety_or_cost_risk-bbbb"])

    def test_status_output_has_tasks_and_keeps_old_fields(self):
        self.init()
        self.task("a", progress_md="State: acknowledged\n")
        out = io.StringIO()
        with patch("agentorg.cli.hc_ready"), patch("agentorg.cli.existing_terminal", return_value=None), \
             patch("agentorg.cli.role_labels", return_value={}), contextlib.redirect_stdout(out):
            cli.team_cmd(SimpleNamespace(path=str(self.project), op="status"))
        data = json.loads(out.getvalue())
        for key in ("project", "inbox_pending", "blocked", "status"):
            self.assertIn(key, data)
        self.assertEqual(data["tasks"], [{"id": "a", "state": "acknowledged", "next_actor": "worker", "flags": ["unknown_delivery"]}])
        self.assertEqual(data["owner_decisions"], [])


class ExperimentalTemplateTest(Fixture):
    def test_research_and_content_are_experimental_engineering_is_not(self):
        self.assertTrue(config.template_document("research")["experimental"])
        self.assertTrue(config.template_document("content")["experimental"])
        self.assertNotIn("experimental", config.template_document("engineering"))

    def test_team_plan_shows_experimental(self):
        self.init("research")
        out = io.StringIO()
        with patch("agentorg.cli.start_team", return_value=[]), contextlib.redirect_stdout(out):
            cli.team_cmd(SimpleNamespace(path=str(self.project), op="plan", apply=False))
        self.assertTrue(json.loads(out.getvalue())["experimental"])


if __name__ == "__main__":
    unittest.main()
