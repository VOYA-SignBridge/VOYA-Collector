import re
from pathlib import Path

# Fix validators.ts
p = Path("frontend/src/api/validators.ts")
if p.exists():
    c = p.read_text("utf-8")
    c = c.replace("session_id:", "session_uid:")
    p.write_text(c, "utf-8")

# Fix TrashPage.tsx
p = Path("frontend/src/pages/TrashPage.tsx")
if p.exists():
    c = p.read_text("utf-8")
    # Remove icon prop from EmptyState
    c = re.sub(r'icon=\{<svg[^>]+>[^<]+</svg>\s*(<path[^>]+></path>\s*)*\s*(<polyline[^>]+></polyline>\s*)*\s*(<line[^>]+></line>\s*)*\s*</svg>\}', '', c)
    p.write_text(c, "utf-8")

print("Fixed remaining TS errors")
