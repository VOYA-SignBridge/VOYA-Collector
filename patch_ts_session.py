import re
from pathlib import Path

# Fix validators.ts
p = Path("frontend/src/api/validators.ts")
if p.exists():
    c = p.read_text("utf-8")
    c = c.replace("session_id:", "session_uid:")
    c = c.replace("session_id: any", "session_uid: any")
    p.write_text(c, "utf-8")

# Fix SessionList.tsx
p = Path("frontend/src/components/dashboard/SessionList.tsx")
if p.exists():
    c = p.read_text("utf-8")
    c = c.replace("session_id", "session_uid")
    p.write_text(c, "utf-8")

# Fix PublicUploadPage.tsx
p = Path("frontend/src/pages/PublicUploadPage.tsx")
if p.exists():
    c = p.read_text("utf-8")
    c = c.replace("session_id", "session_uid")
    p.write_text(c, "utf-8")

print("Fixed session_id TS errors")
