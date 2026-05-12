from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Set, Tuple


def _parse_csv_languages(csv_path: Path, *, default_language: str = "vn") -> List[str]:
    """Extract a sorted list of unique languages from a split CSV.

    Priority:
    - explicit `language` column
    - infer from `label_key` (format: <lang>/<dialect>/<slug> or <lang>/<slug>)
    - fallback to default_language
    """

    langs: Set[str] = set()
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            lang = (r.get("language") or "").strip()
            if not lang:
                lk = (r.get("label_key") or "").strip()
                if lk:
                    parts = [p for p in lk.split("/") if p]
                    if parts and parts[0] not in {"class_idx", "unknown"}:
                        lang = (parts[0] or "").strip()
            if not lang:
                lang = default_language
            langs.add(lang)

    return sorted(langs)


def _infer_lang_dialect_from_row(row: Dict[str, str], *, default_language: str = "vn") -> Tuple[str, str]:
    lang = (row.get("language") or "").strip()
    dialect = (row.get("dialect") or "").strip()

    lk = (row.get("label_key") or "").strip()
    if lk:
        parts = [p for p in lk.split("/") if p]
        if parts and parts[0] not in {"class_idx", "unknown"}:
            if not lang:
                lang = (parts[0] or "").strip()
            # label_key format: <lang>/<dialect>/<slug> (or <lang>/<slug>)
            if not dialect and len(parts) >= 3:
                dialect = (parts[1] or "").strip()

    if not lang:
        lang = default_language
    return (lang, dialect)


def _parse_csv_language_dialects(
    csv_path: Path,
    *,
    default_language: str = "vn",
    include_blank_dialect: bool = False,
) -> Dict[str, List[str]]:
    """Return mapping language -> sorted unique dialects seen in CSV.

    Dialect is read from `dialect` column or inferred from `label_key`.
    Blank dialects are ignored by default.
    """

    by_lang: Dict[str, Set[str]] = {}
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            lang, dialect = _infer_lang_dialect_from_row(r, default_language=default_language)
            if not include_blank_dialect and not dialect:
                continue
            by_lang.setdefault(lang, set()).add(dialect)

    return {lang: sorted(list(dialects)) for lang, dialects in sorted(by_lang.items(), key=lambda kv: kv[0])}


def _parse_comma_list(s: str) -> List[str]:
    if not s:
        return []
    out: List[str] = []
    for part in str(s).split(","):
        p = part.strip()
        if p:
            out.append(p)
    # dedupe keep order
    seen = set()
    deduped: List[str] = []
    for x in out:
        if x in seen:
            continue
        seen.add(x)
        deduped.append(x)
    return deduped


def _build_cmd(
    train_tcn_path: Path,
    *,
    train_csv: Path,
    val_csv: Path,
    test_csv: Path,
    language: str,
    tag: str,
    passthrough: Sequence[str],
) -> List[str]:
    return [
        sys.executable,
        str(train_tcn_path),
        "--train_csv",
        str(train_csv),
        "--val_csv",
        str(val_csv),
        "--test_csv",
        str(test_csv),
        "--filter_language",
        str(language),
        "--tag",
        str(tag),
        *list(passthrough),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Train one TCN per language by repeatedly invoking train_tcn.py with --filter_language. "
            "Pass extra train_tcn args after '--'."
        )
    )

    default_splits_dir = Path(__file__).resolve().parents[1] / "processed" / "splits"
    parser.add_argument("--train_csv", type=Path, default=default_splits_dir / "train.csv")
    parser.add_argument("--val_csv", type=Path, default=default_splits_dir / "val.csv")
    parser.add_argument("--test_csv", type=Path, default=default_splits_dir / "test.csv")

    parser.add_argument(
        "--default_language",
        type=str,
        default="vn",
        help="Default language used when CSV rows lack language/label_key (only affects detection).",
    )
    parser.add_argument(
        "--languages",
        type=str,
        default="",
        help="Optional comma-separated list to train only these languages (in this order).",
    )
    parser.add_argument(
        "--by_dialect",
        action="store_true",
        help="Train one model per dialect within each language (invokes train_tcn.py with both --filter_language and --dialect).",
    )
    parser.add_argument(
        "--dialects",
        type=str,
        default="",
        help="Optional comma-separated list to train only these dialects (applies when --by_dialect).",
    )
    parser.add_argument(
        "--include_blank_dialect",
        action="store_true",
        help="Include blank dialect group when auto-detecting dialects (rare; usually dialect is populated).",
    )
    parser.add_argument(
        "--tag_prefix",
        type=str,
        default="",
        help="Optional prefix used for --tag passed into train_tcn.py.",
    )
    parser.add_argument(
        "--skip_failed",
        action="store_true",
        help="Skip languages that fail (e.g. too few classes) instead of stopping.",
    )
    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="Print the commands without executing them.",
    )

    # Everything after '--' is passed to train_tcn.py
    parser.add_argument("trainer_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    # Strip the leading '--' if present.
    passthrough = list(args.trainer_args)
    if passthrough and passthrough[0] == "--":
        passthrough = passthrough[1:]

    train_tcn_path = Path(__file__).with_name("train_tcn.py")
    if not train_tcn_path.exists():
        raise SystemExit(f"Could not find train_tcn.py at: {train_tcn_path}")

    if args.languages:
        languages = _parse_comma_list(args.languages)
    else:
        languages = _parse_csv_languages(Path(args.train_csv), default_language=str(args.default_language or "vn").strip() or "vn")

    if not languages:
        raise SystemExit("No languages found to train.")

    successes: List[str] = []
    failures: List[str] = []

    prefix = (str(args.tag_prefix or "").strip() + "-") if str(args.tag_prefix or "").strip() else ""

    if not args.by_dialect:
        for lang in languages:
            tag = f"{prefix}lang-{lang}"
            cmd = _build_cmd(
                train_tcn_path,
                train_csv=Path(args.train_csv),
                val_csv=Path(args.val_csv),
                test_csv=Path(args.test_csv),
                language=lang,
                tag=tag,
                passthrough=passthrough,
            )

            print(f"\n=== Training language: {lang} (tag={tag}) ===")
            if args.dry_run:
                print(" ".join(cmd))
                successes.append(lang)
                continue

            try:
                proc = subprocess.run(cmd, check=False)
                if proc.returncode == 0:
                    successes.append(lang)
                else:
                    failures.append(lang)
                    if not args.skip_failed:
                        raise SystemExit(proc.returncode)
            except KeyboardInterrupt:
                raise
            except SystemExit:
                raise
            except Exception as e:
                failures.append(lang)
                print(f"[ERROR] Language '{lang}' failed: {e}")
                if not args.skip_failed:
                    raise

        print("\nDone.")
        print(f"Succeeded: {len(successes)} -> {', '.join(successes) if successes else '(none)'}")
        print(f"Failed:    {len(failures)} -> {', '.join(failures) if failures else '(none)'}")
        return

    # by-dialect mode
    allowed_dialects = set(_parse_comma_list(args.dialects)) if str(args.dialects or "").strip() else set()
    default_lang = str(args.default_language or "vn").strip() or "vn"
    lang_to_dialects = _parse_csv_language_dialects(
        Path(args.train_csv),
        default_language=default_lang,
        include_blank_dialect=bool(args.include_blank_dialect),
    )

    combos: List[Tuple[str, str]] = []
    for lang in languages:
        dialects = lang_to_dialects.get(lang, [])
        for dia in dialects:
            if allowed_dialects and dia not in allowed_dialects:
                continue
            combos.append((lang, dia))

    if not combos:
        raise SystemExit("No (language,dialect) combinations found to train. Check split CSV has dialect/language columns or label_key.")

    for lang, dia in combos:
        tag = f"{prefix}lang-{lang}_dialect-{dia if dia else 'blank'}"
        cmd = _build_cmd(
            train_tcn_path,
            train_csv=Path(args.train_csv),
            val_csv=Path(args.val_csv),
            test_csv=Path(args.test_csv),
            language=lang,
            tag=tag,
            passthrough=["--dialect", dia, *list(passthrough)],
        )

        print(f"\n=== Training language: {lang} | dialect: {dia or '(blank)'} (tag={tag}) ===")
        if args.dry_run:
            print(" ".join(cmd))
            successes.append(f"{lang}/{dia}")
            continue

        try:
            proc = subprocess.run(cmd, check=False)
            if proc.returncode == 0:
                successes.append(f"{lang}/{dia}")
            else:
                failures.append(f"{lang}/{dia}")
                if not args.skip_failed:
                    raise SystemExit(proc.returncode)
        except KeyboardInterrupt:
            raise
        except SystemExit:
            raise
        except Exception as e:
            failures.append(f"{lang}/{dia}")
            print(f"[ERROR] Language '{lang}' dialect '{dia}' failed: {e}")
            if not args.skip_failed:
                raise

    print("\nDone.")
    print(f"Succeeded: {len(successes)} -> {', '.join(successes) if successes else '(none)'}")
    print(f"Failed:    {len(failures)} -> {', '.join(failures) if failures else '(none)'}")


if __name__ == "__main__":
    main()
