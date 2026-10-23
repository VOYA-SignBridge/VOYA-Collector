"""Cập nhật tự quay lui, canh gác, nhật ký thao tác, và bảng điều khiển web."""
import io
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import voya  # noqa: E402
import voya_ui  # noqa: E402

_TMP = None


def setUpModule():
    global _TMP
    _TMP = tempfile.TemporaryDirectory()
    state = Path(_TMP.name)
    voya.STATE_DIR, voya.ACTIONS_LOG = state, state / "actions.jsonl"
    voya.DEPLOY_STATE, voya.WATCH_STATE = state / "deploy.json", state / "watch.json"
    voya.MAINT_FLAG = state / "maintenance.on"
    voya.STOPPED_FLAG, voya.DEPLOY_LOCK = state / "stopped.json", state / "deploy.lock"
    os.environ.pop("VOYA_CONFIRMED", None)


def tearDownModule():
    _TMP.cleanup()


def quiet():
    return redirect_stdout(io.StringIO())


class UpdatePlanTests(unittest.TestCase):
    def test_requirements_change_needs_a_full_build(self):
        plan = voya.plan_from_changes(["backend/requirements.txt"])
        self.assertTrue(plan["backend"] and plan["full"])

    def test_app_code_only_needs_a_code_refresh(self):
        plan = voya.plan_from_changes(["backend/app/routers/x.py"])
        self.assertEqual(plan, {"backend": True, "full": False, "frontend": False, "nginx": False})

    def test_mounted_files_and_frontend_tests_need_no_image(self):
        plan = voya.plan_from_changes(["processed/splits/make_splits.py", "scripts/voya.py",
                                       "frontend/src/pages/__tests__/A.test.tsx"])
        self.assertFalse(any(plan.values()))

    def test_frontend_and_nginx(self):
        plan = voya.plan_from_changes(["frontend/src/App.tsx", "nginx.conf"])
        self.assertTrue(plan["frontend"] and plan["nginx"])


class DeployRollbackTests(unittest.TestCase):
    def _run(self, problems_sequence):
        calls = {"restore": [], "notify": [], "record": []}
        seq = iter(problems_sequence)
        with patch.object(voya, "tag_rollback_point", return_value="rollback-auto-x"), \
                patch.object(voya, "do_backup", return_value=(Path("b.dump"), True)), \
                patch.object(voya, "sh"), patch.object(voya, "compose"), \
                patch.object(voya, "image_tags", return_value=["latest", "base"]), \
                patch.object(voya, "problems_after_deploy", side_effect=lambda *a: next(seq)), \
                patch.object(voya, "restore_rollback_point", side_effect=calls["restore"].append), \
                patch.object(voya, "notify", side_effect=lambda t, m: calls["notify"].append(t)), \
                patch.object(voya, "record_deploy", side_effect=calls["record"].append), quiet():
            ok = voya.build_and_deploy(backend=True, full=False, frontend=False, nginx=False, label="t")
        return ok, calls

    def test_failed_checks_roll_back_and_alert(self):
        ok, calls = self._run([["API khong tra 200"], []])
        self.assertFalse(ok)
        self.assertEqual(calls["restore"], ["rollback-auto-x"])
        self.assertEqual(len(calls["notify"]), 1)
        self.assertEqual(calls["record"], [])            # lần hỏng không được ghi là "đã triển khai"
        self.assertFalse(voya.MAINT_FLAG.exists())       # bảo trì luôn tắt

    def test_success_records_the_deploy_and_turns_maintenance_off(self):
        ok, calls = self._run([[]])
        self.assertTrue(ok)
        self.assertEqual(calls["restore"], [])
        self.assertEqual(calls["record"], ["t"])
        self.assertFalse(voya.MAINT_FLAG.exists())

    def test_backup_failure_stops_before_touching_anything(self):
        with patch.object(voya, "tag_rollback_point", return_value="x"), \
                patch.object(voya, "do_backup", return_value=(Path("b"), False)), \
                patch.object(voya, "compose") as compose, quiet(), self.assertRaises(SystemExit):
            voya.build_and_deploy(backend=True, full=False, frontend=False, nginx=False, label="t")
        compose.assert_not_called()
        self.assertFalse(voya.MAINT_FLAG.exists())

    def test_update_git_refuses_to_pull_over_local_edits(self):
        dirty = type("R", (), {"stdout": " M backend/app/x.py\n", "returncode": 0})()
        with patch.object(voya, "sh", return_value=dirty) as sh, quiet(), self.assertRaises(SystemExit):
            voya.cmd_update_git([])
        self.assertEqual(sh.call_count, 1)               # không fetch, không pull


class WatchTests(unittest.TestCase):
    def setUp(self):
        voya.WATCH_STATE.unlink(missing_ok=True)

    def _watch(self, problems):
        sent = []
        with patch.object(voya, "watch_problems", return_value=problems), \
                patch.object(voya, "notify", side_effect=lambda t, m: sent.append(t)), quiet():
            voya.cmd_watch([])
        return sent

    def test_alerts_only_when_the_situation_changes(self):
        self.assertEqual(len(self._watch(["API khong tra 200"])), 1)
        self.assertEqual(self._watch(["API khong tra 200"]), [])     # cùng lỗi: không báo lại
        self.assertEqual(len(self._watch([])), 1)                    # hết lỗi: báo "đã ổn"
        self.assertEqual(self._watch([]), [])

    def test_image_drift_is_reported(self):
        voya._write_json(voya.DEPLOY_STATE, {"images": {"backend": "sha:new"}})
        with patch.object(voya, "compose") as compose, \
                patch.object(voya, "unhealthy_services", return_value=[]), \
                patch.object(voya, "http_status", return_value="200"), \
                patch.object(voya, "running_images", return_value={"backend": "sha:OLD"}):
            compose.return_value.stdout = "abc\n"
            problems = voya.watch_problems()
        self.assertTrue(any("KHAC lan trien khai" in p for p in problems))


class IntentionalStopAndLockTests(unittest.TestCase):
    def tearDown(self):
        voya.STOPPED_FLAG.unlink(missing_ok=True)
        voya.DEPLOY_LOCK.unlink(missing_ok=True)

    def test_watch_fix_never_revives_a_stack_stopped_on_purpose(self):
        voya.mark_stopped("tao goi chuyen server")
        with patch.object(voya, "compose") as compose, patch.object(voya, "notify") as notify, quiet():
            compose.return_value.stdout = ""          # không container nào chạy
            voya.cmd_watch(["--fix"])
        self.assertFalse(any(c.args[:1] == ("up",) for c in compose.call_args_list))
        notify.assert_not_called()

    def test_an_unexpected_stop_is_revived_and_reported(self):
        with patch.object(voya, "watch_problems", side_effect=[["stack dang TAT (x)"], []]),                 patch.object(voya, "compose") as compose, patch.object(voya, "wait_healthy"),                 patch.object(voya, "notify"), quiet():
            voya.cmd_watch(["--fix"])
        self.assertTrue(any(c.args[:1] == ("up",) for c in compose.call_args_list))

    def test_boot_respects_an_intentional_stop(self):
        voya.mark_stopped("voya stop")
        with patch.object(voya, "docker_ready", return_value=True),                 patch.object(voya, "compose") as compose, quiet():
            voya.cmd_boot([])
        compose.assert_not_called()

    def test_stop_marks_and_start_clears(self):
        with patch.dict(os.environ, {"VOYA_CONFIRMED": "co"}), patch.object(voya, "compose"),                 patch.object(voya, "wait_healthy", return_value=True), quiet():
            voya.cmd_stop([])
            self.assertTrue(voya.STOPPED_FLAG.exists())
            voya.cmd_start([])
            self.assertFalse(voya.STOPPED_FLAG.exists())

    def test_second_deploy_is_refused_while_one_is_running(self):
        voya._write_json(voya.DEPLOY_LOCK, {"pid": os.getpid(), "what": "update-git", "time": "t"})
        with self.assertRaises(SystemExit) as err, quiet():
            with voya.deploy_lock():
                pass
        self.assertIn("update-git", str(err.exception))

    def test_lock_of_a_dead_process_is_taken_over(self):
        voya._write_json(voya.DEPLOY_LOCK, {"pid": 999999, "what": "x", "time": "t"})
        with voya.deploy_lock():
            self.assertEqual(voya._read_json(voya.DEPLOY_LOCK, {})["pid"], os.getpid())
        self.assertFalse(voya.DEPLOY_LOCK.exists())


class StaleContainerTests(unittest.TestCase):
    def test_container_running_an_older_image_than_its_tag_is_stale(self):
        def fake_sh(args, **kw):
            r = type("R", (), {"returncode": 0})()
            if args[:2] == ["docker", "inspect"]:
                r.stdout = "\n".join(["backend voya_backend:latest sha:OLD",
                                      "worker voya_backend:latest sha:NEW",
                                      "redis redis:7-alpine sha:R"])
            else:                                     # docker image inspect <tag>
                r.stdout = "sha:NEW"
            return r

        with patch.object(voya, "compose") as compose, patch.object(voya, "sh", side_effect=fake_sh):
            compose.return_value.stdout = "id1 id2 id3"
            self.assertEqual(voya.stale_services(), ["backend"])

    def test_update_git_explains_a_branch_without_upstream(self):
        clean = type("R", (), {"stdout": "", "returncode": 0})()
        none = type("R", (), {"stdout": "", "returncode": 128})()
        branch = type("R", (), {"stdout": "deploy_x\n", "returncode": 0})()
        with patch.object(voya, "sh", side_effect=[clean, none, branch]), quiet(),                 self.assertRaises(SystemExit) as err:
            voya.cmd_update_git([])
        self.assertIn("set-upstream-to=origin/deploy_x", str(err.exception))


class ConfirmAndActionLogTests(unittest.TestCase):
    def test_preconfirmed_word_from_the_ui(self):
        with patch.dict(os.environ, {"VOYA_CONFIRMED": "quay lui"}), quiet():
            self.assertTrue(voya.confirm("?", "quay lui"))
            self.assertFalse(voya.confirm("?", "co"))

    def test_only_important_actions_are_logged(self):
        voya.ACTIONS_LOG.unlink(missing_ok=True)
        with patch.object(voya, "cmd_status"), patch.object(voya, "cmd_backup"):
            table = [(k, l, voya.cmd_status if k == "status" else voya.cmd_backup if k == "backup" else f)
                     for k, l, f in voya.COMMANDS]
            with patch.object(voya, "COMMANDS", table):
                voya.main(["status"])
                voya.main(["backup"])
        entries = [json.loads(l) for l in voya.ACTIONS_LOG.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([e["command"] for e in entries], ["backup"])
        self.assertEqual(entries[0]["result"], "ok")

    def test_declined_dangerous_action_is_logged_as_cancelled(self):
        voya.ACTIONS_LOG.unlink(missing_ok=True)
        with patch("builtins.input", return_value=""), patch.object(voya, "compose"), quiet():
            voya.main(["stop"])
        entry = json.loads(voya.ACTIONS_LOG.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual((entry["command"], entry["result"]), ("stop", "huy"))


class ControlPanelTests(unittest.TestCase):
    def test_every_command_has_risk_metadata_that_matches_its_confirm_word(self):
        meta = {m["key"]: m for m in voya_ui.commands_meta()}
        self.assertEqual(set(meta), {k for k, _, _ in voya.COMMANDS})
        self.assertEqual(meta["rollback"]["word"], "quay lui")
        self.assertEqual(meta["stop"]["risk"], "danger")

    def test_validate_run(self):
        v = voya_ui.validate_run
        self.assertEqual(v({"key": "status"}), ("status", [], None))
        self.assertEqual(v({"key": "stop", "confirm": "co"}), ("stop", [], "co"))
        self.assertEqual(v({"key": "maintenance", "args": "off", "confirm": "co"}),
                         ("maintenance", ["off"], "co"))
        for bad in ({"key": "rm -rf"}, {"key": "stop"}, {"key": "rollback", "confirm": "co"},
                    {"key": "status", "args": "x"}, {"key": "goi-tao", "confirm": "tao goi"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                v(bad)

    def test_server_rejects_missing_token_and_foreign_host(self):
        job = voya_ui.Job()
        server = voya_ui.ThreadingHTTPServer(("127.0.0.1", 0), None)
        port = server.server_address[1]
        server.RequestHandlerClass = voya_ui.make_handler("tok", port, job)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            def get(path, headers):
                req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=5) as r:
                        return r.status
                except urllib.error.HTTPError as e:
                    return e.code

            self.assertEqual(get("/api/meta", {}), 403)
            self.assertEqual(get("/api/meta", {"X-VOYA-Token": "tok", "Host": "evil.example:80"}), 403)
            self.assertEqual(get("/api/meta", {"X-VOYA-Token": "tok"}), 200)
            self.assertEqual(get("/", {}), 403)
            self.assertEqual(get("/?t=tok", {}), 200)
        finally:
            server.shutdown()

    def test_doc_file_stays_inside_docs(self):
        self.assertEqual(voya_ui.doc_file(voya_ui.GUIDE).name, "HUONG_DAN_DEV.html")
        self.assertIsNotNone(voya_ui.doc_file("/docs/03-security/AUTHORIZATION.md"))
        for bad in ("/docs/../.env", "/docs/%2e%2e/.env", "/docs/../scripts/voya.py",
                    "/docs/khong-co.md", "/docs/02-data/db/gen_erd.py", "/etc/passwd"):
            with self.subTest(bad=bad):
                self.assertIsNone(voya_ui.doc_file(bad))

    def test_guide_is_served_without_token_but_not_to_a_foreign_host(self):
        server = voya_ui.ThreadingHTTPServer(("127.0.0.1", 0), None)
        port = server.server_address[1]
        server.RequestHandlerClass = voya_ui.make_handler("tok", port, voya_ui.Job())
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            def get(path, headers=None):
                req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers=headers or {})
                try:
                    with urllib.request.urlopen(req, timeout=5) as r:
                        return r.status, r.headers.get("Content-Type", "")
                except urllib.error.HTTPError as e:
                    return e.code, ""

            self.assertEqual(get(voya_ui.GUIDE), (200, "text/html; charset=utf-8"))
            self.assertEqual(get("/huong-dan")[0], 200)  # theo chuyển hướng tới GUIDE
            self.assertEqual(get("/docs/README.md")[1], "text/plain; charset=utf-8")
            self.assertEqual(get("/docs/../.env")[0], 404)
            self.assertEqual(get(voya_ui.GUIDE, {"Host": "evil.example:80"})[0], 403)
        finally:
            server.shutdown()


if __name__ == "__main__":
    unittest.main()
