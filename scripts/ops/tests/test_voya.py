import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import voya  # noqa: E402

_TMP = None


def setUpModule():
    """Nhật ký thao tác / trạng thái của test không được ghi vào .voya/ thật."""
    import os
    import tempfile

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


class VoyaLauncherTests(unittest.TestCase):
    def test_error_filter_ignores_uvicorn_error_logger_at_info(self):
        text = "\n".join([
            '{"event": "Application startup complete.", "level": "info", "logger": "uvicorn.error"}',
            '{"event": "Exception in ASGI application", "level": "error", "logger": "uvicorn.error"}',
            '{"event": "pool ok", "level": "warning", "logger": "app"}',
            "2026-10-16 ERROR:  new row violates row-level security policy",
            'level=error caller=ring.go msg="x"',
            "Traceback (most recent call last):",
            "all good",
        ])
        found = voya.error_lines(text)
        self.assertEqual(len(found), 4)
        self.assertFalse(any("startup complete" in l for l in found))

    def test_every_command_has_a_group_and_a_description(self):
        keys = [k for k, _, _ in voya.COMMANDS]
        self.assertEqual(len(keys), len(set(keys)))
        for key, label, fn in voya.COMMANDS:
            self.assertIn(" | ", label, key)
            self.assertTrue((fn.__doc__ or "").strip(), key)

    def test_help_lists_every_command(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            voya.main(["help"])
        for key, _, _ in voya.COMMANDS:
            self.assertIn(f"voya {key}", buf.getvalue())

    def test_unknown_command_exits_with_help(self):
        with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            voya.main(["khong-co-lenh-nay"])

    def test_dangerous_commands_do_nothing_without_confirmation(self):
        for key in ("stop", "restart", "update-code", "goi-tao"):
            with self.subTest(key=key), patch("builtins.input", return_value=""), \
                    patch.object(voya, "sh") as sh, patch.object(voya, "compose") as compose, \
                    redirect_stdout(io.StringIO()):
                voya.main([key, "F:/"] if key == "goi-tao" else [key])
                sh.assert_not_called()
                compose.assert_not_called()

    def test_stop_runs_only_after_typed_confirmation(self):
        with patch("builtins.input", return_value="co"), patch.object(voya, "compose") as compose, \
                redirect_stdout(io.StringIO()):
            voya.main(["stop"])
        compose.assert_called_once_with("stop", "--timeout", "300")

    def test_host_on_phone_hotspot_laptop_that_slept_is_flagged(self):
        lines, warn = voya.describe_host({
            "interface": "Wi-Fi", "wired": False, "ssid": "MaiMinh", "gateway": "172.20.10.1",
            "battery": 2, "boot": "2026-10-15T23:24:00", "sleeps": 2, "last_sleep": "2026-10-16T23:17:53",
            "drops": 3, "last_drop": "2026-10-17T00:11:40"})
        text = " ".join(warn)
        self.assertIn("Wi-Fi", text)
        self.assertIn("DIEN THOAI", text)
        self.assertIn("NGU", text)
        self.assertNotIn("chay pin", text.lower())  # Plugged in: no battery warning.

    def test_wired_desktop_that_never_slept_has_no_warnings(self):
        lines, warn = voya.describe_host({
            "interface": "Ethernet", "wired": True, "ssid": None, "gateway": "10.10.0.1",
            "battery": None, "boot": "2026-10-01T08:00:00", "sleeps": 0, "drops": 0})
        self.assertEqual(warn, [])
        self.assertIn("day mang", lines[0])

    def test_compose_is_always_bare_so_env_compose_file_applies(self):
        with patch.object(voya, "sh") as sh:
            voya.compose("ps")
        args = sh.call_args.args[0]
        self.assertEqual(args[:3], ["docker", "compose", "ps"])
        self.assertNotIn("-f", args)


if __name__ == "__main__":
    unittest.main()
