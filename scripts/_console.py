"""Force UTF-8 stdout/stderr on Windows consoles (cp1252 default) so scripts
printing Vietnamese never crash with UnicodeEncodeError. Import for side effect:

    from _console import force_utf8  # noqa: F401  (or just `import _console`)
"""

import sys


def force_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream.encoding and stream.encoding.lower() not in ("utf-8", "utf8"):
                stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


force_utf8()
