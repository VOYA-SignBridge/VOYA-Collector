import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ops.transfer import (Failure, backup, complete_role_passwords, configure, digest, env_read, extract,
                          snapshot_workspace, validate_configuration, validate_tar, verify)
from ops.deployment import destination_settings, restore


def archive(path, entries):
    with tarfile.open(path, "w:gz") as output:
        for name, kind in entries:
            member = tarfile.TarInfo(name)
            member.type = kind
            if kind == tarfile.REGTYPE:
                member.size = 4
                output.addfile(member, io.BytesIO(b"data"))
            else:
                member.linkname = "../escape"
                output.addfile(member)


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def bundle(self):
        bundle = self.root / "bundle"
        bundle.mkdir()
        archive(bundle / "workspace.tar.gz", [(".env", tarfile.REGTYPE)])
        (bundle / "database.dump").write_bytes(b"PGDMP example")
        (bundle / "roles.sql").write_text("-- roles", encoding="utf-8")
        manifest = {"format": 1, "volumes": {}, "database": "signdb",
                    "databases": {"signdb": {"artifact": "database.dump", "counts": {}}}, "files": {
            p.name: {"size": p.stat().st_size, "sha256": digest(p)} for p in bundle.iterdir()}}
        (bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return bundle

    def test_valid_bundle(self):
        self.assertEqual(verify(self.bundle())["format"], 1)

    def test_corrupted_dump(self):
        bundle = self.bundle()
        (bundle / "database.dump").write_bytes(b"broken")
        with self.assertRaisesRegex(Failure, "Checksum"):
            verify(bundle)

    def test_missing_artifact(self):
        bundle = self.bundle()
        (bundle / "roles.sql").unlink()
        with self.assertRaises(Failure):
            verify(bundle)

    def test_extra_artifact(self):
        bundle = self.bundle()
        (bundle / "partial.dump").touch()
        with self.assertRaises(Failure):
            verify(bundle)

    def test_missing_volume(self):
        bundle = self.bundle()
        path = bundle / "manifest.json"
        data = json.loads(path.read_text())
        data["volumes"] = {"redis_data": "source_redis"}
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(Failure, "volume"):
            verify(bundle)

    def test_archive_unsafe_entries(self):
        for name, kind in [("../escape", tarfile.REGTYPE), ("/etc/passwd", tarfile.REGTYPE),
                           ("C:/escape", tarfile.REGTYPE), ("dir\\escape", tarfile.REGTYPE),
                           ("CON.txt", tarfile.REGTYPE), ("data.", tarfile.REGTYPE),
                           ("link", tarfile.SYMTYPE), ("link", tarfile.LNKTYPE),
                           ("device", tarfile.CHRTYPE)]:
            with self.subTest(name=name, kind=kind):
                path = self.root / "archive.tar.gz"
                archive(path, [("valid", tarfile.REGTYPE), (name, kind)])
                target = self.root / "output"
                with self.assertRaises(Failure):
                    extract(path, target)
                self.assertFalse(target.exists())

    def test_archive_case_collision(self):
        path = self.root / "archive.tar.gz"
        archive(path, [("Data", tarfile.REGTYPE), ("data", tarfile.REGTYPE)])
        with self.assertRaises(Failure):
            validate_tar(path)

    def test_snapshot_keeps_ignored_data_and_secrets(self):
        source = self.root / "source"
        source.mkdir()
        for name in ("dataset/raw", "processed/models", "gdrive", "node_modules", ".venv", "backups", ".git"):
            path = source / name
            path.mkdir(parents=True)
            (path / "payload").write_bytes(b"payload")
        (source / ".env").write_text("SECRET_KEY=keep-this")
        dest = self.root / "source.tar.gz"
        snapshot_workspace(source, dest, [])
        output = self.root / "output"
        extract(dest, output)
        self.assertEqual((output / ".env").read_text(), "SECRET_KEY=keep-this")
        for name in ("dataset/raw", "processed/models", "gdrive"):
            self.assertEqual((output / name / "payload").read_bytes(), b"payload")
        for name in ("node_modules", ".venv", ".git", "backups"):
            self.assertFalse((output / name).exists())

    def test_source_host_state_stays_behind_but_action_history_travels(self):
        """Cờ 'dừng có chủ ý' do CHÍNH lượt tạo gói đặt ra không được sang máy mới,
        nếu không máy mới không bao giờ tự bật stack và tắt luôn báo động."""
        source = self.root / "src"
        (source / ".voya").mkdir(parents=True)
        (source / "nginx.conf.d").mkdir()
        for name in ("stopped_intentionally.json", "deploy_state.json", "watch_state.json",
                     "deploy.lock", "task.log", "actions.jsonl"):
            (source / ".voya" / name).write_text("{}")
        (source / "nginx.conf.d" / "maintenance.on").write_text("x")
        (source / "nginx.conf.d" / "maintenance.html").write_text("page")
        dest = self.root / "state.tar.gz"
        snapshot_workspace(source, dest, [])
        output = self.root / "state-out"
        extract(dest, output)
        self.assertEqual(sorted(p.name for p in (output / ".voya").iterdir()), ["actions.jsonl"])
        self.assertEqual(sorted(p.name for p in (output / "nginx.conf.d").iterdir()), ["maintenance.html"])

    def test_config_preserves_secret_and_removes_duplicate_overrides(self):
        (self.root / ".env").write_text("SECRET_KEY=retain\nFOO=old\nFOO=duplicate\n")
        configure(self.root, {"FOO": "new"})
        self.assertEqual(env_read(self.root / ".env"), {"SECRET_KEY": "retain", "FOO": "new"})
        self.assertEqual((self.root / ".env").read_text().count("FOO="), 1)

    def test_config_writes_plain_values_unquoted_for_shell_readers(self):
        (self.root / ".env").write_text("A=1\n")
        configure(self.root, {"MIGRATION_DATABASE_URL": "postgresql://admin:ab12@postgres:5432/signdb",
                              "NOTE": "has space $HOME"})
        lines = (self.root / ".env").read_text().splitlines()
        self.assertIn("MIGRATION_DATABASE_URL=postgresql://admin:ab12@postgres:5432/signdb", lines)
        self.assertIn('NOTE="has space $$HOME"', lines)

    def test_config_rejects_newline(self):
        (self.root / ".env").touch()
        with self.assertRaises(Failure):
            configure(self.root, {"FOO": "a\nINJECT=b"})

    def test_restore_never_overwrites_directory(self):
        with self.assertRaisesRegex(Failure, "must not exist"):
            restore(self.bundle(), self.root, project="test-host", public_url="https://example.test")

    def test_destination_keeps_signing_keys_and_updates_origin(self):
        (self.root / ".env").write_text("SECRET_KEY=retain\nAUTH_TOKEN_SECRET_KEY=retain-too\n")
        (self.root / "deploy").mkdir()
        destination_settings(self.root, "new-host", "https://example.test")
        env = env_read(self.root / ".env")
        self.assertEqual(env["SECRET_KEY"], "retain")
        self.assertEqual(env["AUTH_TOKEN_SECRET_KEY"], "retain-too")
        self.assertEqual(env["COOKIE_SECURE"], "1")
        self.assertEqual(env["CORS_ALLOWED_ORIGINS"], "https://example.test")

    def test_backup_rejects_destination_inside_workspace(self):
        stack = SimpleNamespace(root=self.root)
        with self.assertRaisesRegex(Failure, "OUTSIDE"):
            backup(stack, self.root / "bundle")

    def test_backup_failure_resumes_writers_no_manifest(self):
        source = self.root / "source"
        source.mkdir()
        stack = Mock(root=source, config={"services": {"backend": {"environment": {}}}})
        stack.db = {"POSTGRES_DB": "signdb"}
        stack.running.return_value = ["postgres", "backend"]
        stack.call.side_effect = [None, "id", None]
        stack.counts.side_effect = Failure("database unavailable")
        stack.sql.side_effect = ["0", "t", "0", '["signdb"]']
        destination = self.root / "failed"
        def fake_run(args, **kw):  # `docker ps` (one-off containers) -> none; `docker inspect` -> clean exit
            return "" if args[:2] == ["docker", "ps"] else '[{"State":{"ExitCode":0}}]'
        with patch("ops.transfer.preflight", return_value=[]), patch("ops.transfer.run", side_effect=fake_run):
            with self.assertRaisesRegex(Failure, "database unavailable"):
                backup(stack, destination, resume=False)
        stack.call.assert_any_call("start", "backend")
        self.assertFalse((destination / "manifest.json").exists())

    def test_backup_refuses_before_stopping_when_one_off_containers_run(self):
        """Một `docker compose run` còn sống giữ kết nối DB: phải từ chối TRƯỚC khi
        dừng site, không phải sau (17/10/2026: lượt chép Drive bị ngắt)."""
        source = self.root / "src-oneoff"
        source.mkdir()
        stack = Mock(root=source, config={"name": "voya", "services": {"backend": {"environment": {}}}})
        stack.running.return_value = ["postgres", "backend"]
        with patch("ops.transfer.preflight", return_value=[]),                 patch("ops.transfer.run", return_value="voya-backend-run-1234"):
            with self.assertRaisesRegex(Failure, "voya-backend-run-1234"):
                backup(stack, self.root / "oneoff-out", resume=False)
        stack.call.assert_not_called()

    def valid_stack(self):
        (self.root / "deploy").mkdir(exist_ok=True)
        (self.root / "deploy/public_hosts.txt").write_text("example.test\n")
        env = {"SECRET_KEY": "s" * 32, "AUTH_TOKEN_SECRET_KEY": "t" * 32,
               "VOYA_APP_DB_PASSWORD": "a" * 20, "VOYA_CONTROL_DB_PASSWORD": "c" * 20,
               "DB_STRICT_ISOLATION": "1", "FRONTEND_BASE_URL": "https://example.test",
               "COOKIE_SECURE": "1", "CORS_ALLOWED_ORIGINS": "https://example.test"}
        for key, user, password in (("DATABASE_URL", "voya_app", "a" * 20),
                                   ("CONTROL_DATABASE_URL", "voya_control", "c" * 20),
                                   ("MIGRATION_DATABASE_URL", "admin", "p" * 20)):
            env[key] = f"postgresql://{user}:{password}@postgres:5432/signdb"
        return SimpleNamespace(root=self.root, config={"services": {"backend": {"environment": env}}},
                               db={"POSTGRES_USER": "admin", "POSTGRES_PASSWORD": "p" * 20, "POSTGRES_DB": "signdb"})

    def test_configuration_valid(self):
        validate_configuration(self.valid_stack())

    def test_configuration_rejects_dsn_drift(self):
        stack = self.valid_stack()
        stack.config["services"]["backend"]["environment"]["CONTROL_DATABASE_URL"] = "postgresql://admin:bad@elsewhere/other"
        with self.assertRaisesRegex(Failure, "CONTROL_DATABASE_URL"):
            validate_configuration(stack)

    def test_configuration_rejects_insecure_cookie(self):
        stack = self.valid_stack()
        stack.config["services"]["backend"]["environment"]["COOKIE_SECURE"] = "0"
        with self.assertRaisesRegex(Failure, "COOKIE_SECURE"):
            validate_configuration(stack)

    def test_configuration_does_not_match_host_substrings(self):
        stack = self.valid_stack()
        (self.root / "deploy/public_hosts.txt").write_text("other.example.test\n")
        with self.assertRaisesRegex(Failure, "host"):
            validate_configuration(stack)

    def test_configuration_rejects_wildcard_cors(self):
        stack = self.valid_stack()
        stack.config["services"]["backend"]["environment"]["CORS_ALLOWED_ORIGINS"] = "*"
        with self.assertRaisesRegex(Failure, "CORS"):
            validate_configuration(stack)

    def test_missing_password_derived_without_rotation(self):
        stack = self.valid_stack()
        (self.root / ".env").write_text("SECRET_KEY=keep\n")
        del stack.config["services"]["backend"]["environment"]["VOYA_CONTROL_DB_PASSWORD"]
        self.assertTrue(complete_role_passwords(stack))
        self.assertEqual(env_read(self.root / ".env")["VOYA_CONTROL_DB_PASSWORD"], "c" * 20)
        self.assertFalse(complete_role_passwords(self.valid_stack()))

    def test_snapshot_refuses_exclusion_of_entire_workspace(self):
        with self.assertRaises(Failure):
            snapshot_workspace(self.root, self.root.parent / "unused.tar.gz", [self.root.parent])


if __name__ == "__main__":
    unittest.main()
