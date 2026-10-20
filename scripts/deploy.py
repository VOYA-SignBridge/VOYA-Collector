"""Preflight, restore or deploy using the same verified host-backup contract."""
import argparse
import sys
from pathlib import Path

from ops.deployment import deploy, restore
from ops.transfer import Failure, Stack, complete_role_passwords, preflight


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--check", action="store_true", help="Read-only configuration and live data audit")
    parser.add_argument("--restore", type=Path, help="Trusted backup bundle; --root must not exist")
    parser.add_argument("--restore-only", action="store_true", help="Restore without starting application")
    parser.add_argument("--project")
    parser.add_argument("--public-url")
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--prepared-backup", type=Path, help="Verified snapshot with writers still stopped")
    parser.add_argument("--allow-downtime", action="store_true")
    parser.add_argument("--accept-external-storage", action="store_true")
    parser.add_argument("--gpu", action="store_true", help="Require NVIDIA Docker support; otherwise use CPU")
    parser.add_argument("--image-tag")
    parser.add_argument("--use-local-images", action="store_true",
                        help="Use images already on this host (e.g. loaded from a migration pack); build only missing ones")
    args = parser.parse_args()
    if args.check:
        if args.restore:
            parser.error("--check cannot be combined with --restore; use backup.py --verify-only")
        stack = Stack(args.root, gpu=args.gpu)
        preflight(stack)
        stack.audit()
        return
    if not args.allow_downtime:
        parser.error("Deployment changes services; pass --allow-downtime during maintenance.")
    if args.restore_only and not args.restore:
        parser.error("--restore-only requires --restore")
    if args.restore:
        if not args.project or not args.public_url:
            parser.error("Restore requires --project and --public-url for the destination.")
        if args.image_tag:
            parser.error("Restore builds backed-up source; --image-tag is for a Git checkout update.")
        restore(args.restore, args.root, project=args.project, public_url=args.public_url,
                accept_external=args.accept_external_storage)
        if args.restore_only:
            return
    stack = Stack(args.root, gpu=args.gpu, image_tag=args.image_tag)
    if complete_role_passwords(stack):
        stack = Stack(args.root, gpu=args.gpu, image_tag=args.image_tag)
    deploy(stack, backup_dir=args.backup_dir, restored=bool(args.restore),
           prepared_backup=args.prepared_backup,
           image_tag=args.image_tag, accept_external=args.accept_external_storage,
           use_local_images=args.use_local_images)


if __name__ == "__main__":
    try:
        main()
    except (Failure, OSError, ValueError, KeyError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
