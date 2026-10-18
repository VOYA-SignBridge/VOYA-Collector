import io
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ops import drive_export
from ops.pack import (APP, DRIVE, GIT, HISTORY, HOST, MANIFEST, README, RELATED_DIR, REPORTS,
                      audit_file_refs, create, history_sources, migration_home, pack_container_layers,
                      pack_name, pack_tools, resolve_ref, restore_extras, unzip_pack, verify_pack, zip_pack)
from ops.transfer import Failure, digest, env_read, rotate_bootstrap_password

HAS_GIT = shutil.which("git") is not None


def write_app_bundle(stack, destination, **_):
    """Stand-in for transfer.backup(): a minimal bundle that passes verify()."""
    destination.mkdir()
    with tarfile.open(destination / "workspace.tar.gz", "w:gz") as archive:
        member = tarfile.TarInfo(".env")
        member.size = 4
        archive.addfile(member, io.BytesIO(b"A=1\n"))
    (destination / "database.dump").write_bytes(b"PGDMP example")
    (destination / "roles.sql").write_text("-- roles", encoding="utf-8")
    manifest = {"format": 1, "volumes": {}, "database": "signdb",
                "databases": {"signdb": {"artifact": "database.dump", "counts": {}}},
                "files": {p.name: {"size": p.stat().st_size, "sha256": digest(p)} for p in destination.iterdir()}}
    (destination / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def fake_drive(stack, target):
    target.mkdir(parents=True, exist_ok=True)
    (target / "files").mkdir(exist_ok=True)
    (target / "files/abc.mp4").write_bytes(b"video")
    inventory = {"format": 1, "root": {"id": "r", "name": "VOYA"}, "folders": [], "errors": [], "bytes": 5,
                 "files": [{"id": "abc", "name": "clip.mp4", "path": "clip.mp4", "stored": "files/abc.mp4"}]}
    (target / "inventory.json").write_text(json.dumps(inventory), encoding="utf-8")
    return {"status": "ok", "files": 1, "bytes": 5, "root": inventory["root"]}


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


class PackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "VOYA-Collector"
        (self.root / "backups").mkdir(parents=True)
        (self.root / "backups/signdb_1.dump").write_bytes(b"old dump")
        (self.root / ".env").write_text("USE_GOOGLE_DRIVE=1\n", encoding="utf-8")
        (self.base / "voya_backups").mkdir()
        (self.base / "voya_backups/env_pre.bak").write_text("X=1", encoding="utf-8")
        (self.base / "qipedc_mau").mkdir()
        (self.base / "qipedc_mau/D0001B.mp4").write_bytes(b"reference video")
        (self.base / "Unrelated_Project").mkdir()
        (self.base / "voya_test_clips/sub").mkdir(parents=True)
        (self.base / "voya_test_clips/D0001B.mp4").write_bytes(b"reference video")      # duplicate
        (self.base / "voya_test_clips/sub/D0001B.mp4").write_bytes(b"reference video")  # duplicate, other path
        (self.base / "voya_test_clips/D0002.mp4").write_bytes(b"only here")             # unique

    def stack(self):
        stack = Mock(root=self.root.resolve())
        stack.config = {"services": {"backend": {"environment": {
            "USE_GOOGLE_DRIVE": "1", "FRONTEND_BASE_URL": "https://example.test"}}}}
        stack.running.return_value = ["postgres", "backend", "worker"]
        return stack

    def make_pack(self, volumes=None, **kwargs):
        destination = self.base / "pack"
        volumes = volumes or Mock(return_value={"status": "absent"})
        with patch("ops.pack.backup", side_effect=write_app_bundle), \
                patch("ops.pack.pack_images", return_value={"status": "ok", "images": 0}), \
                patch("ops.pack.pack_host", return_value={"status": "ok", "found": [], "warnings": []}), \
                patch("ops.pack.pack_anonymous_volumes", volumes), \
                patch("ops.pack.drive_sync", side_effect=fake_drive), \
                patch("ops.pack.pack_container_layers", return_value={"status": "absent"}), \
                patch("ops.pack.pack_tools", return_value={"status": "ok"}), \
                patch("ops.pack.audit_file_refs", return_value={"status": "ok"}), \
                patch("ops.pack.pack_git", return_value={"status": "absent"}):
            manifest = create(kwargs.pop("stack", None) or self.stack(), destination, **kwargs)
        return destination, manifest

    def test_pack_contains_every_section_and_verifies(self):
        pack, manifest = self.make_pack()
        self.assertTrue((pack / f"{HISTORY}/backups/signdb_1.dump").is_file())
        self.assertTrue((pack / f"{RELATED_DIR}/voya_backups/env_pre.bak").is_file())
        self.assertEqual((pack / f"{RELATED_DIR}/qipedc_mau/D0001B.mp4").read_bytes(), b"reference video")
        self.assertFalse((pack / f"{RELATED_DIR}/Unrelated_Project").exists())
        self.assertTrue((pack / f"{DRIVE}/files/abc.mp4").is_file())
        self.assertTrue((pack / f"{APP}/manifest.json").is_file())
        self.assertIn(README, manifest["files"])
        self.assertEqual(verify_pack(pack)["sections"]["drive"]["files"], 1)

    def test_writers_restarted_after_success(self):
        stack = self.stack()
        self.make_pack(stack=stack)
        stack.call.assert_any_call("start", "backend", "worker")

    def test_keep_stopped_leaves_writers_down(self):
        stack = self.stack()
        self.make_pack(stack=stack, keep_stopped=True)
        self.assertNotIn("start", [c.args[0] for c in stack.call.call_args_list if c.args])

    def test_failure_after_snapshot_restarts_writers_and_leaves_no_manifest(self):
        stack = self.stack()
        with self.assertRaisesRegex(Failure, "docker gone"):
            self.make_pack(stack=stack, keep_stopped=True, volumes=Mock(side_effect=Failure("docker gone")))
        stack.call.assert_any_call("start", "backend", "worker")
        self.assertFalse((self.base / "pack" / MANIFEST).exists())

    def test_tampered_or_extra_file_rejected(self):
        pack, _ = self.make_pack()
        (pack / f"{DRIVE}/files/abc.mp4").write_bytes(b"VIDEO")
        with self.assertRaisesRegex(Failure, "Checksum"):
            verify_pack(pack)
        (pack / f"{DRIVE}/files/abc.mp4").write_bytes(b"video")
        (pack / f"{HISTORY}/stray.txt").write_text("x")
        with self.assertRaisesRegex(Failure, "differ"):
            verify_pack(pack)

    def test_drive_inventory_must_match_pack(self):
        pack, _ = self.make_pack()
        inventory = json.loads((pack / f"{DRIVE}/inventory.json").read_text())
        inventory["files"].append({"id": "zzz", "stored": "files/zzz.mp4"})
        (pack / f"{DRIVE}/inventory.json").write_text(json.dumps(inventory))
        manifest = json.loads((pack / MANIFEST).read_text())
        path = pack / f"{DRIVE}/inventory.json"
        manifest["files"][f"{DRIVE}/inventory.json"] = {"size": path.stat().st_size, "sha256": digest(path)}
        (pack / MANIFEST).write_text(json.dumps(manifest))
        with self.assertRaisesRegex(Failure, "Drive"):
            verify_pack(pack)

    def test_unfinished_pack_rejected(self):
        (self.base / "half").mkdir()
        with self.assertRaisesRegex(Failure, "incomplete"):
            verify_pack(self.base / "half")

    def test_destination_inside_workspace_or_history_refused(self):
        with self.assertRaisesRegex(Failure, "OUTSIDE"):
            create(self.stack(), self.root / "pack")
        with self.assertRaisesRegex(Failure, "overlaps"):
            create(self.stack(), self.base / "voya_backups" / "pack")

    def test_missing_configured_mirror_is_an_error(self):
        with self.assertRaisesRegex(Failure, "not found"):
            history_sources(self.root, {"BACKUP_MIRROR_HOST_DIR": str(self.base / "nowhere")})

    @unittest.skipUnless(HAS_GIT, "git not installed")
    def test_git_history_round_trip_keeps_uncommitted_work(self):
        git(self.root, "init", "-q", "-b", "deploy")
        git(self.root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "one")
        git(self.root, "remote", "add", "origin", "https://example.test/repo.git")
        pack, manifest = self.make_pack()
        shutil.rmtree(pack)
        with patch("ops.pack.backup", side_effect=write_app_bundle), \
                patch("ops.pack.pack_images", return_value={"status": "skipped"}), \
                patch("ops.pack.pack_host", return_value={"status": "ok"}), \
                patch("ops.pack.pack_anonymous_volumes", return_value={"status": "absent"}), \
                patch("ops.pack.pack_container_layers", return_value={"status": "absent"}), \
                patch("ops.pack.pack_tools", return_value={"status": "ok"}), \
                patch("ops.pack.audit_file_refs", return_value={"status": "ok"}), \
                patch("ops.pack.drive_sync", side_effect=fake_drive):
            create(self.stack(), pack)
        self.assertEqual(json.loads((pack / f"{GIT}/state.json").read_text())["branch"], "deploy")
        target = self.base / "restored"
        target.mkdir()
        (target / ".env").write_text("A=1\n")
        (target / "backups").mkdir()
        restore_extras(pack, target, history_root=self.base / "hist", load_images=False)
        self.assertEqual(git(target, "branch", "--show-current").strip(), "deploy")
        self.assertIn("origin", git(target, "remote"))
        self.assertIn("?? .env", git(target, "status", "--porcelain"))
        self.assertTrue((target / "backups/signdb_1.dump").is_file())
        self.assertTrue((self.base / "voya_backups/env_pre.bak").is_file())

    def test_duplicates_stored_once_and_restored_everywhere(self):
        pack, manifest = self.make_pack()
        self.assertFalse((pack / f"{RELATED_DIR}/voya_test_clips/D0001B.mp4").exists())
        self.assertFalse((pack / f"{RELATED_DIR}/voya_test_clips/sub/D0001B.mp4").exists())
        self.assertTrue((pack / f"{RELATED_DIR}/voya_test_clips/D0002.mp4").is_file())
        self.assertEqual(manifest["dedup"][f"{RELATED_DIR}/voya_test_clips/D0001B.mp4"], f"{RELATED_DIR}/qipedc_mau/D0001B.mp4")
        self.assertEqual(manifest["sections"]["dedup"]["duplicates"], 2)
        shutil.rmtree(pack / f"{RELATED_DIR}/voya_test_clips/sub")  # Empty dirs may not survive a copy to USB.
        target = self.base / "newdisk" / "app"
        (target / "backups").mkdir(parents=True)
        (target / ".env").write_text("A=1\n")
        restore_extras(pack, target, history_root=self.base / "hist", load_images=False)
        for rel in ("voya_test_clips/D0001B.mp4", "voya_test_clips/sub/D0001B.mp4", "qipedc_mau/D0001B.mp4"):
            self.assertEqual((self.base / "newdisk" / rel).read_bytes(), b"reference video")
        self.assertEqual((self.base / "newdisk/voya_test_clips/D0002.mp4").read_bytes(), b"only here")

    def test_losing_the_kept_copy_is_detected(self):
        pack, _ = self.make_pack()
        manifest = json.loads((pack / MANIFEST).read_text())
        del manifest["files"][f"{RELATED_DIR}/qipedc_mau/D0001B.mp4"]
        (pack / f"{RELATED_DIR}/qipedc_mau/D0001B.mp4").unlink()
        (pack / MANIFEST).write_text(json.dumps(manifest))
        with self.assertRaisesRegex(Failure, "duplicate"):
            verify_pack(pack)

    def test_related_folders_restored_as_siblings_of_new_app(self):
        pack, _ = self.make_pack()
        target = self.base / "newdisk" / "app"
        (target / "backups").mkdir(parents=True)
        (target / ".env").write_text("A=1\n")
        restore_extras(pack, target, history_root=self.base / "hist", load_images=False)
        self.assertEqual((self.base / "newdisk/qipedc_mau/D0001B.mp4").read_bytes(), b"reference video")
        self.assertTrue((self.base / "newdisk/voya_backups/env_pre.bak").is_file())

    def test_restore_extras_never_overwrites_different_history(self):
        pack, _ = self.make_pack()
        target = self.base / "restored"
        (target / "backups").mkdir(parents=True)
        (target / ".env").write_text("A=1\n")
        (target / "backups/signdb_1.dump").write_bytes(b"newer, different")
        with self.assertRaisesRegex(Failure, "overwrite"):
            restore_extras(pack, target, history_root=self.base / "hist", load_images=False)

    def test_zip_round_trip_with_checksum(self):
        pack, _ = self.make_pack()
        archive = zip_pack(pack)
        self.assertEqual(archive.name, pack.name + ".zip")
        checksum = archive.with_name(archive.name + ".sha256")
        self.assertEqual(checksum.read_text().split(), [digest(archive), archive.name])
        with zipfile.ZipFile(archive) as z:
            self.assertEqual({n.split("/", 1)[0] for n in z.namelist()}, {pack.name})
        with self.assertRaisesRegex(Failure, "exists"):
            zip_pack(pack)
        target, manifest = unzip_pack(archive, self.base / "D")
        self.assertEqual(target, self.base / "D" / "SignBridge_ChuyenServer" / pack.name)
        self.assertEqual(manifest["files"], json.loads((pack / MANIFEST).read_text())["files"])

    def test_unzip_rejects_damaged_copy(self):
        pack, _ = self.make_pack()
        archive = zip_pack(pack)
        with archive.open("r+b") as stream:
            stream.seek(-30, 2)
            stream.write(b"X")
        with self.assertRaisesRegex(Failure, "mismatch"):
            unzip_pack(archive, self.base / "D")

    def test_names_are_memorable_and_grouped(self):
        from datetime import datetime
        self.assertEqual(pack_name(datetime(2026, 10, 16, 14, 30)), "SignBridge_ChuyenServer_2026-10-16_14h30")
        self.assertEqual(migration_home(self.base), self.base / "SignBridge_ChuyenServer")
        home = self.base / "SignBridge_ChuyenServer"
        self.assertEqual(migration_home(home), home)


class NewHostTests(unittest.TestCase):
    SCRIPTS = Path(__file__).resolve().parents[2]

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def test_pack_carries_tools_and_numbered_launchers(self):
        pack = self.base / "pack"
        pack.mkdir()
        pack_tools(self.SCRIPTS, pack)
        for rel in ("00_cong-cu/migration_pack.py", "00_cong-cu/deploy.py", "00_cong-cu/backup.py",
                    "00_cong-cu/ops/pack.py", "00_cong-cu/ops/transfer.py", "00_cong-cu/ops/drive_export.py",
                    "1_KHOI_PHUC_MAY_MOI.bat", "KHOI_PHUC_MAY_MOI.ps1",
                    "2_BAT_DOMAIN_MAY_MOI.bat", "BAT_DOMAIN_MAY_MOI.ps1"):
            self.assertTrue((pack / rel).is_file(), rel)
        self.assertFalse((pack / "00_cong-cu/ops/tests").exists())
        self.assertIn(b"\r\n", (pack / "1_KHOI_PHUC_MAY_MOI.bat").read_bytes())
        # The copied CLI must run from the pack alone, without the repo.
        result = subprocess.run([sys.executable, str(pack / "00_cong-cu/migration_pack.py"), "--help"],
                                capture_output=True, text=True, cwd=self.base)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell not available")
    def test_powershell_scripts_parse(self):
        for path in sorted((self.SCRIPTS / "chuyen_server").glob("*.ps1")):
            command = ("$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile("
                       f"'{path}', [ref]$null, [ref]$e); if ($e.Count) {{ $e | % {{ $_.Message }}; exit 1 }}")
            result = subprocess.run(["powershell", "-NoProfile", "-Command", command],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, f"{path.name}: {result.stdout}{result.stderr}")

    def test_rotate_db_password_changes_database_before_env(self):
        root = self.base / "app"
        root.mkdir()
        (root / ".env").write_text("POSTGRES_PASSWORD=admin\nMIGRATION_DATABASE_URL="
                                   "postgresql://admin:admin@postgres:5432/signdb\nSECRET_KEY=keep\n")
        sent = []
        stack = Mock(root=root, db={"POSTGRES_USER": "admin", "POSTGRES_PASSWORD": "admin",
                                    "POSTGRES_DB": "signdb"})
        stack.config = {"services": {"backend": {"environment": {
            "MIGRATION_DATABASE_URL": "postgresql://admin:admin@postgres:5432/signdb"}}}}
        stack.running.return_value = ["postgres", "backend"]
        stack.pg.side_effect = lambda *a, input_file=None, **k: sent.append(input_file.read().decode())
        self.assertTrue(rotate_bootstrap_password(stack))
        env = env_read(root / ".env")
        self.assertEqual(len(env["POSTGRES_PASSWORD"]), 48)
        self.assertEqual(sent, [f"ALTER ROLE \"admin\" PASSWORD '{env['POSTGRES_PASSWORD']}';\n"])
        self.assertEqual(env["MIGRATION_DATABASE_URL"],
                         f"postgresql://admin:{env['POSTGRES_PASSWORD']}@postgres:5432/signdb")
        self.assertEqual(env["SECRET_KEY"], "keep")
        self.assertNotIn(env["POSTGRES_PASSWORD"], " ".join(map(str, stack.pg.call_args.args)))
        stack.db["POSTGRES_PASSWORD"] = env["POSTGRES_PASSWORD"]
        self.assertFalse(rotate_bootstrap_password(stack))  # Already strong: no second rotation.


class SotKeyTests(PackTests):
    def test_sot_key_restored_without_overwrite(self):
        pack, _ = self.make_pack()
        # Add host/voya-home to the pack and re-seal the manifest.
        key = pack / f"{HOST}/voya-home/sot_private.key"
        key.parent.mkdir(parents=True)
        key.write_text("KEY")
        manifest = json.loads((pack / MANIFEST).read_text())
        manifest["files"][f"{HOST}/voya-home/sot_private.key"] = {"size": key.stat().st_size, "sha256": digest(key)}
        (pack / MANIFEST).write_text(json.dumps(manifest))
        target = self.base / "restored"
        (target / "backups").mkdir(parents=True)
        (target / ".env").write_text("A=1\n")
        home = self.base / "newhome"
        with patch("ops.pack.Path.home", return_value=home):
            restore_extras(pack, target, history_root=self.base / "hist", load_images=False)
            self.assertEqual((home / ".voya/sot_private.key").read_text(), "KEY")
            (home / ".voya/sot_private.key").write_text("OTHER")
            with self.assertRaisesRegex(Failure, "SOT"):
                restore_extras(pack, target, history_root=self.base / "hist2", load_images=False)


class FileRefTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "app"
        for rel in ("dataset/features/a.npz", "dataset/raw_videos/v.mp4", "dataset/legal/doc.pdf",
                    "processed/ckpt/best.pt"):
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.root / rel).write_bytes(b"x")
        (self.base / "outside.mp4").write_bytes(b"external")

    def test_resolves_container_relative_and_windows_paths(self):
        cases = [("/dataset/features/a.npz", "samples", "dataset/features/a.npz"),
                 ("/app/dataset/raw_videos/v.mp4", "raw_uploads", "dataset/raw_videos/v.mp4"),
                 ("features/a.npz", "samples", "dataset/features/a.npz"),
                 ("doc.pdf", "legal_documents", "dataset/legal/doc.pdf"),
                 ("/workspace/processed/ckpt/best.pt", "training_jobs", "processed/ckpt/best.pt")]
        for value, table, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(resolve_ref(value, self.root, table), self.root / expected)

    def test_audit_counts_local_drive_missing_and_copies_external(self):
        values = {
            "samples.file_path": ["features/a.npz", "features/gone.npz"],
            "samples.storage_url": ["https://drive.google.com/file/d/ABCDEFGHIJKLMNOPQRSTUV/view",
                                    "https://drive.google.com/file/d/ZZZZZZZZZZZZZZZZZZZZZZ/view"],
            "raw_uploads.local_path": ["/dataset/raw_videos/v.mp4", str(self.base / "outside.mp4")],
            "training_jobs.checkpoint_path": ["/workspace/processed/ckpt/best.pt"],
        }

        def sql(query, database=None):
            if "information_schema" in query:
                return json.dumps(list(values))
            for key, rows in values.items():
                table, column = key.split(".")
                if f'"{column}"' in query and f'"{table}"' in query:
                    return json.dumps(rows)
            raise AssertionError(query)

        drive = {"files": [{"id": "ABCDEFGHIJKLMNOPQRSTUV", "path": "x"}], "folders": []}
        pack = self.base / "pack"
        pack.mkdir()
        result = audit_file_refs(Mock(root=self.root, sql=sql), pack, drive)
        report = json.loads((pack / f"{REPORTS}/db_file_refs.json").read_text(encoding="utf-8"))
        columns = report["columns"]
        self.assertEqual(result["missing"], 2)
        self.assertEqual(columns["samples.file_path"]["missing"], ["features/gone.npz"])
        self.assertEqual(columns["samples.storage_url"]["drive"], 1)
        self.assertEqual(columns["raw_uploads.local_path"]["external"], 1)
        self.assertEqual(columns["training_jobs.checkpoint_path"]["local"], 1)
        self.assertEqual((pack / report["outside_workspace"][0]["stored"]).read_bytes(), b"external")
        self.assertTrue(result["warnings"])

    def test_container_layers_skip_mounts_noise_and_image_dirs(self):
        container = {"Id": "c1", "Name": "/voya_backend",
                     "Mounts": [{"Destination": "/workspace"}, {"Destination": "/dataset"}]}
        diff = "\n".join(["C /app", "A /app/uploads", "A /app/uploads/x.mp4", "C /tmp",
                          "A /tmp/celerybeat-schedule", "A /workspace/foo", "C /root",
                          "A /root/.cache/pip", "A /app/__pycache__/m.pyc", "D /etc/old", "C /etc/hosts"])
        copied = []

        def run(args, output=None, **_):
            if args[:2] == ["docker", "diff"]:
                return diff
            copied.append(args[2].split(":", 1)[1])
            output.write(b"tar")
            return ""

        with patch("ops.pack.compose_containers", return_value=[container]), patch("ops.pack.run", side_effect=run):
            result = pack_container_layers(Mock(), self.base / "layers")
        self.assertEqual(sorted(copied), ["/app/uploads", "/etc/hosts", "/tmp/celerybeat-schedule"])
        self.assertEqual(result["paths"], 3)


class FakeDrive:
    """Just enough of the Drive v3 files() API for walk()."""
    def __init__(self, children, items):
        self.children, self.items = children, items

    def files(self):
        return self

    def list(self, q, **_):
        parent = q.split("'")[1]
        return Mock(execute=Mock(return_value={"files": [dict(c) for c in self.children.get(parent, [])]}))

    def get(self, fileId, **_):
        return Mock(execute=Mock(return_value=dict(self.items[fileId])))


class DriveExportTests(unittest.TestCase):
    def test_walk_recurses_and_follows_shortcuts_out_of_tree(self):
        folder = {"id": "f", "name": "videos", "mimeType": drive_export.FOLDER}
        clip = {"id": "c", "name": "a/b?.mp4", "mimeType": "video/mp4"}
        shortcut = {"id": "s", "name": "link", "mimeType": drive_export.SHORTCUT,
                    "shortcutDetails": {"targetId": "x"}}
        outside = {"id": "x", "name": "sheet", "mimeType": "application/vnd.google-apps.spreadsheet"}
        service = FakeDrive({"root": [folder, shortcut], "f": [clip]}, {"x": outside})
        folders, files = drive_export.walk(service, "root")
        self.assertEqual([f["id"] for f in folders], ["f"])
        self.assertEqual(sorted(f["id"] for f in files), ["c", "s", "x"])
        self.assertEqual(next(f for f in files if f["id"] == "c")["path"], "videos/a/b?.mp4")

    def test_stored_name_is_file_id_with_safe_extension(self):
        self.assertEqual(drive_export.stored_name({"id": "c", "name": "a/b?.mp4", "mimeType": "video/mp4"}),
                         "files/c.mp4")
        self.assertEqual(drive_export.stored_name(
            {"id": "x", "name": "sheet", "mimeType": "application/vnd.google-apps.spreadsheet"}), "files/x.xlsx")

    def test_configured_spreadsheets_outside_root_are_added(self):
        sheet = {"id": "S1", "name": "labels", "mimeType": "application/vnd.google-apps.spreadsheet"}
        files, errors = [], []
        env = {"GOOGLE_SHEETS_LABELS_SPREADSHEET_ID": "S1", "GOOGLE_SHEETS_SAMPLES_SPREADSHEET_ID": " "}
        with patch.dict("os.environ", env, clear=True):
            drive_export.add_configured(FakeDrive({}, {"S1": sheet}), files, errors)
        self.assertEqual([f["path"] for f in files], ["(GOOGLE_SHEETS_LABELS_SPREADSHEET_ID)/labels"])
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
