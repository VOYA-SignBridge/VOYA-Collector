"""Create a verified host bundle, or verify an existing bundle without Docker."""
import argparse
import sys
from pathlib import Path

from ops.transfer import Failure, Stack, backup, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--allow-downtime", action="store_true")
    parser.add_argument("--accept-external-storage", action="store_true")
    parser.add_argument("--keep-stopped", action="store_true", help="Maintenance/CD: do not restart writers on success")
    args = parser.parse_args()
    if args.verify_only:
        verify(args.destination)
        print("Backup checksums and archive paths OK.")
    else:
        if not args.allow_downtime:
            parser.error("Backup stops writers temporarily; pass --allow-downtime during maintenance.")
        backup(Stack(args.root), args.destination, accept_external=args.accept_external_storage,
               resume=not args.keep_stopped)


if __name__ == "__main__":
    try:
        main()
    except (Failure, OSError, ValueError, KeyError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
