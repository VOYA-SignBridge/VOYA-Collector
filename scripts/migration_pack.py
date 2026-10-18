"""Full server-migration pack: app bundle + Git, backup history, Drive, videos, images, host config.

Everything goes under ONE folder, <noi-luu>/SignBridge_ChuyenServer/:

  drive-cache/                                     Drive pre-copy (drive-sync), reused by create
  SignBridge_ChuyenServer_2026-10-16_14h30/        the pack (create)
  SignBridge_ChuyenServer_2026-10-16_14h30.zip     one file to carry (create --zip, or zip)
  SignBridge_ChuyenServer_2026-10-16_14h30.zip.sha256

  rotate-db-password  old host, once: strong POSTGRES_PASSWORD (in PostgreSQL, then .env)
  plan            read-only size estimate (Docker may be stopped)
  drive-sync      pre-copy Drive while the site is live; repeatable, incremental
  create          the pack itself (stops writers during the snapshot)
  zip             zip an existing pack, with a SHA-256 file next to it
  unzip           new host: check SHA-256, extract, verify
  verify          checksums of EVERY file in a pack, plus the app bundle contract
  restore-extras  new host, after `deploy.py --restore`
"""
import argparse
import sys
from pathlib import Path

from ops.pack import (DRIVE_CACHE, create, describe, drive_sync, migration_home, pack_name, plan,
                      restore_extras, unzip_pack, verify_pack, zip_pack)
from ops.transfer import Failure, Stack, rotate_bootstrap_password, run

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("rotate-db-password")
    p.add_argument("--root", type=Path, default=ROOT)
    p = commands.add_parser("plan")
    p.add_argument("noi_luu", type=Path, nargs="?", help="Drive/folder that will hold the pack, e.g. F:/")
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--external", type=Path, action="append", default=[])
    p = commands.add_parser("drive-sync")
    p.add_argument("noi_luu", type=Path, help="e.g. F:/ -> F:/SignBridge_ChuyenServer/drive-cache")
    p.add_argument("--root", type=Path, default=ROOT)
    p = commands.add_parser("create")
    p.add_argument("noi_luu", type=Path, help="e.g. F:/ -> F:/SignBridge_ChuyenServer/SignBridge_ChuyenServer_<date>")
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--allow-downtime", action="store_true")
    p.add_argument("--zip", action="store_true", help="Also write <pack>.zip + .zip.sha256")
    p.add_argument("--drive-cache", type=Path, help=f"Default: <noi_luu>/SignBridge_ChuyenServer/{DRIVE_CACHE}")
    p.add_argument("--external", type=Path, action="append", default=[],
                   help="Extra folder outside the repo to carry along (repeatable)")
    p.add_argument("--skip-images", action="store_true", help="New host builds images from source (needs internet)")
    p.add_argument("--skip-drive", action="store_true", help="No Drive copy; new host keeps using the same Drive")
    p.add_argument("--skip-related", action="store_true", help="Leave the folders next to the repo on the old host")
    p.add_argument("--keep-stopped", action="store_true", help="Leave writers stopped (final cutover)")
    p = commands.add_parser("zip")
    p.add_argument("pack", type=Path)
    p = commands.add_parser("unzip")
    p.add_argument("archive", type=Path)
    p.add_argument("noi_luu", type=Path, help="e.g. D:/ -> D:/SignBridge_ChuyenServer/<pack>")
    p = commands.add_parser("verify")
    p.add_argument("pack", type=Path)
    p = commands.add_parser("restore-extras")
    p.add_argument("pack", type=Path)
    p.add_argument("--root", type=Path, required=True, help="Application restored by deploy.py --restore")
    p.add_argument("--history-root", type=Path)
    p.add_argument("--no-images", action="store_true")
    args = parser.parse_args()

    if args.command == "rotate-db-password":
        if rotate_bootstrap_password(Stack(args.root)):
            # Bare `docker compose` in the repo: COMPOSE_FILE in .env keeps the
            # prod + gpu overlays that a hand-picked -f list would silently drop.
            run(["docker", "compose", "up", "-d", "--no-build"], cwd=args.root, timeout=1800)
            print("Services recreated with the new password.")
    elif args.command == "plan":
        destination = migration_home(args.noi_luu) / pack_name() if args.noi_luu else None
        if destination:
            print(f"Pack would be: {destination}")
        plan(args.root, args.external, destination)
    elif args.command == "drive-sync":
        print(drive_sync(Stack(args.root), migration_home(args.noi_luu) / DRIVE_CACHE))
    elif args.command == "create":
        if not args.allow_downtime:
            parser.error("The snapshot stops writers; pass --allow-downtime during maintenance.")
        home = migration_home(args.noi_luu)
        cache = args.drive_cache or (home / DRIVE_CACHE)
        destination = home / pack_name()
        print(f"Pack: {destination}")
        create(Stack(args.root), destination, drive_cache=cache if cache.is_dir() else None,
               extra_history=args.external, skip_images=args.skip_images, keep_stopped=args.keep_stopped,
               skip_drive=args.skip_drive, skip_related=args.skip_related)
        if args.zip:
            zip_pack(destination)
    elif args.command == "zip":
        zip_pack(args.pack)
    elif args.command == "unzip":
        unzip_pack(args.archive, args.noi_luu)
    elif args.command == "verify":
        print(describe(verify_pack(args.pack)))
    else:
        restore_extras(args.pack, args.root, history_root=args.history_root, load_images=not args.no_images)


if __name__ == "__main__":
    try:
        main()
    except (Failure, OSError, ValueError, KeyError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
