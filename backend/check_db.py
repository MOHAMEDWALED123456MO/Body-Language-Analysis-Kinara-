"""Check the database connection: python check_db.py   (uses KINARA_DB, or SQLite when it is not set)."""
import os
from sqlalchemy import func, select

from engine import db

url = os.environ.get("KINARA_DB", "(not set: using data/kinara.db with SQLite)")
print("Database:", url.split("@")[-1] if "@" in url else url)
try:
    eng = db.engine()
    with eng.connect() as c:
        print("Connected. Engine:", eng.dialect.name)
        for t in (db.UserRole, db.User, db.Session, db.Report, db.Feedback, db.SignalResult, db.CoachingNote, db.AIModel):
            print(f"  {t.name:14} rows: {c.execute(select(func.count()).select_from(t)).scalar()}")
except Exception as e:
    print("FAILED:", e)
