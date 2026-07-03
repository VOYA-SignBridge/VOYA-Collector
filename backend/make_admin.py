import sys
sys.path.insert(0, '/app')
from app.storage.metadata_db import _get_conn
conn = _get_conn()
cur = conn.cursor()
cur.execute("UPDATE users SET is_admin = True WHERE username = 'Minh'")
conn.commit()
print("Minh is now admin")
