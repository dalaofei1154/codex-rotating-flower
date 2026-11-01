import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("flower_workbuddy_bridge",
                                            Path(__file__).with_name("global_bridge.py"))
bridge = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bridge
spec.loader.exec_module(bridge)


class WorkBuddyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "sessions").mkdir()
        self.db = self.root / "workbuddy.db"
        self.connection = sqlite3.connect(self.db)
        self.addCleanup(self.connection.close)
        self.connection.execute("""CREATE TABLE sessions (
            id TEXT PRIMARY KEY, status TEXT, updated_at INTEGER,
            transport TEXT, deleted_at INTEGER, title TEXT, prompt TEXT)""")
        self.connection.commit()
        self.now = time.time()
        self.adapter = bridge.WorkBuddyDatabaseAdapter(self.root)
        self.addCleanup(self.adapter.close)

    def task(self, task_id="one", status="working", age=0, transport="local", deleted=None):
        self.connection.execute("""INSERT OR REPLACE INTO sessions
                                (id, status, updated_at, transport, deleted_at, title, prompt)
                                VALUES (?,?,?,?,?,?,?)""",
                                (task_id, status, int((self.now - age) * 1000),
                                 transport, deleted, "private title", "private prompt"))
        self.connection.commit()

    def worker(self, task_id="one", kind="worker", pid=None):
        pid = os.getpid() if pid is None else pid
        path = self.root / "sessions" / f"{pid}.json"
        path.write_text(json.dumps({"pid": pid, "sessionId": task_id, "kind": kind}))
        return path

    def enable_models(self):
        self.connection.execute("ALTER TABLE sessions ADD COLUMN model TEXT")
        self.connection.commit()

    def model(self, value, task_id="one"):
        self.connection.execute("UPDATE sessions SET model = ? WHERE id = ?", (value, task_id))
        self.connection.commit()

    def test_start_wait_resume_complete_cancel_and_error(self):
        self.worker()
        for status, expected in [("working", "RUN LOW"), ("pending", "STOP"), ("waiting_permission", "STOP"),
                                 ("working", "RUN LOW"), ("completed", "STOP"),
                                 ("planning", "RUN LOW"), ("cancelled", "STOP"),
                                 ("error", "STOP"), ("unknown-future-status", "STOP")]:
            self.task(status=status)
            self.adapter.poll(self.now)
            self.assertEqual(self.adapter.selected(self.now)[0], expected, status)

    def test_missing_dead_prewarm_or_mismatched_worker_does_not_run(self):
        self.task()
        self.adapter.poll(self.now)
        self.assertEqual(self.adapter.selected(self.now)[0], "STOP")
        self.worker(kind="prewarm")
        self.adapter.poll(self.now)
        self.assertEqual(self.adapter.selected(self.now)[0], "STOP")
        self.worker("different")
        self.adapter.poll(self.now)
        self.assertEqual(self.adapter.selected(self.now)[0], "STOP")
        self.worker()
        with patch.object(bridge.os, "kill", side_effect=ProcessLookupError):
            self.adapter.poll(self.now)
        self.assertEqual(self.adapter.selected(self.now)[0], "STOP")
        with patch.object(bridge.os, "kill", side_effect=PermissionError):
            self.adapter.poll(self.now)
        self.assertEqual(self.adapter.selected(self.now)[0], "STOP")

    def test_exit_of_worker_stops_even_if_database_still_says_working(self):
        self.task()
        worker = self.worker()
        self.adapter.poll(self.now)
        self.assertEqual(self.adapter.selected(self.now), ("RUN LOW", "one", 1))
        worker.unlink()
        self.adapter.poll(self.now)
        self.assertEqual(self.adapter.selected(self.now), ("STOP", None, 0))

    def test_stale_cloud_deleted_and_future_rows_do_not_run(self):
        self.worker()
        for values in [{"age": 601}, {"transport": "cloud"}, {"deleted": 1}, {"age": -3600}]:
            self.task(**values)
            self.adapter.poll(self.now)
            self.assertEqual(self.adapter.selected(self.now)[0], "STOP", values)

    def test_state_reads_are_readonly_and_do_not_expose_conversations(self):
        self.task()
        self.worker()
        before = self.db.read_bytes()
        self.adapter.poll(self.now)
        self.assertEqual(self.db.read_bytes(), before)
        self.assertNotIn("private", repr(vars(self.adapter)))
        self.assertEqual(self.adapter.status_counts, {"working": 1})

    def test_database_failure_clears_previously_running_state_and_recovers(self):
        self.task()
        self.worker()
        self.adapter.poll(self.now)
        self.assertEqual(self.adapter.selected(self.now)[0], "RUN LOW")
        self.connection.execute("ALTER TABLE sessions RENAME TO old_sessions")
        self.connection.commit()
        self.adapter.poll(self.now)
        self.assertEqual(self.adapter.selected(self.now)[0], "STOP")
        self.assertEqual(self.adapter.mapping_counts, {})
        self.assertEqual(self.adapter._latched, {})
        self.assertIsNotNone(self.adapter.last_error)
        self.connection.execute("ALTER TABLE old_sessions RENAME TO sessions")
        self.connection.commit()
        self.adapter.poll(self.now)
        self.assertEqual(self.adapter.selected(self.now)[0], "RUN LOW")

    def test_product_tiers_and_independent_models_across_turns(self):
        self.enable_models()
        self.worker()
        for model, expected in [
            ("fast-model", "LOW"), ("balanced-model", "HIGH"), ("deep-model", "ULTRA"),
            ("DeepSeek-V4.1-Flash", "HIGH"), ("future-unknown-model", "HIGH"),
            (None, "LOW"), ("", "LOW"), ("  ", "LOW"),
        ]:
            with self.subTest(model=model):
                self.task()
                self.model(model)
                self.adapter.poll(self.now)
                self.assertEqual(self.adapter.selected(self.now), ("RUN " + expected, "one", 1))
                self.assertEqual(sum(self.adapter.mapping_counts.values()), 1)
                self.task(status="completed")
                self.adapter.poll(self.now)
                self.assertEqual(self.adapter.selected(self.now), ("STOP", None, 0))
                self.assertEqual(self.adapter.mapping_counts, {})

    def test_legacy_schema_keeps_low_and_reports_its_basis(self):
        self.task()
        self.worker()
        self.adapter.poll(self.now)
        self.assertEqual(self.adapter.selected(self.now)[0], "RUN LOW")
        self.assertEqual(self.adapter.mapping_counts, {"missing model (legacy) -> LOW": 1})
        self.assertIsNone(self.adapter.last_error)

    def test_parallel_workbuddy_tasks_choose_highest_then_fall_back(self):
        self.enable_models()
        self.task("fast")
        self.model("fast-model", "fast")
        self.task("deep", age=10)
        self.model("deep-model", "deep")
        self.worker("fast")
        self.worker("deep", pid=os.getpid() + 10000)
        with patch.object(bridge.os, "kill", return_value=None):
            self.adapter.poll(self.now)
            self.assertEqual(self.adapter.selected(self.now), ("RUN ULTRA", "deep", 2))
            self.task("deep", status="completed")
            self.adapter.poll(self.now)
            self.assertEqual(self.adapter.selected(self.now), ("RUN LOW", "fast", 1))
            self.task("fast", status="pending")
            self.adapter.poll(self.now)
            self.assertEqual(self.adapter.selected(self.now), ("STOP", None, 0))

    def test_next_prompt_model_change_does_not_change_active_or_waiting_turn(self):
        self.enable_models()
        self.worker()
        self.task()
        self.model("fast-model")
        self.adapter.poll(self.now)
        for status in ("working", "planning", "pending", "waiting_permission", "working"):
            with self.subTest(status=status):
                self.task(status=status)
                self.model("deep-model")
                self.adapter.poll(self.now)
                expected = "STOP" if status in ("pending", "waiting_permission") else "RUN LOW"
                self.assertEqual(self.adapter.selected(self.now)[0], expected)
        self.task(status="completed")
        self.adapter.poll(self.now)
        self.task()
        self.model("deep-model")
        self.adapter.poll(self.now)
        self.assertEqual(self.adapter.selected(self.now)[0], "RUN ULTRA")

    def test_worker_replacement_starts_new_mapping_without_observed_completion(self):
        self.enable_models()
        old_worker = self.worker()
        self.task()
        self.model("fast-model")
        self.adapter.poll(self.now)
        self.model("deep-model")
        old_worker.unlink()
        self.worker(pid=os.getpid() + 10000)
        with patch.object(bridge.os, "kill", return_value=None):
            self.adapter.poll(self.now)
        self.assertEqual(self.adapter.selected(self.now)[0], "RUN ULTRA")

    def test_stale_or_dead_worker_discards_latched_mapping(self):
        self.enable_models()
        for dead in (False, True):
            with self.subTest(dead=dead):
                worker = self.worker()
                self.task()
                self.model("fast-model")
                self.adapter.poll(self.now)
                if dead:
                    worker.unlink()
                else:
                    self.task(age=601)
                self.adapter.poll(self.now)
                self.assertEqual(self.adapter.selected(self.now)[0], "STOP")
                self.assertEqual(self.adapter._latched, {})
                self.task()
                self.model("deep-model")
                self.worker()
                self.adapter.poll(self.now)
                self.assertEqual(self.adapter.selected(self.now)[0], "RUN ULTRA")
                self.task(status="completed")
                self.adapter.poll(self.now)

    def test_cold_start_wait_does_not_latch_until_work_resumes(self):
        self.enable_models()
        self.worker()
        self.task(status="pending")
        self.model("fast-model")
        self.adapter.poll(self.now)
        self.assertEqual(self.adapter.selected(self.now)[0], "STOP")
        self.assertEqual(self.adapter._latched, {})
        self.task()
        self.model("balanced-model")
        self.adapter.poll(self.now)
        self.assertEqual(self.adapter.selected(self.now)[0], "RUN HIGH")

    def test_mapping_metadata_is_readonly_and_does_not_retain_raw_model(self):
        self.enable_models()
        self.worker()
        self.task()
        self.model("private-provider-model-name")
        before = self.db.read_bytes()
        self.adapter.poll(self.now)
        self.assertEqual(self.db.read_bytes(), before)
        self.assertNotIn("private", repr(vars(self.adapter)))
        self.assertEqual(self.adapter.mapping_counts,
                         {"independent/unknown model (neutral) -> HIGH": 1})


class CombinedTests(unittest.TestCase):
    def test_other_app_keeps_running_when_one_finishes(self):
        codex = unittest.mock.Mock()
        workbuddy = unittest.mock.Mock()
        adapter = bridge.CombinedAdapter({"Codex": codex, "WorkBuddy": workbuddy})
        codex.selected.return_value = ("RUN HIGH", "codex", 1)
        workbuddy.selected.return_value = ("RUN LOW", "workbuddy", 1)
        self.assertEqual(adapter.selected(), ("RUN HIGH", "codex", 2))
        codex.selected.return_value = ("STOP", None, 0)
        self.assertEqual(adapter.selected(), ("RUN LOW", "workbuddy", 1))
        workbuddy.selected.return_value = ("STOP", None, 0)
        self.assertEqual(adapter.selected(), ("STOP", None, 0))


if __name__ == "__main__":
    unittest.main()
