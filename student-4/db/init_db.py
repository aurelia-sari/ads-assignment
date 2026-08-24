"""Create and seed the Account & Dashboard database (student-4, Aurelia Sari).

TODO (Aurelia Sari): replace `records` with the real schema for Account & Dashboard.
The project specification requires at least ten records per table, so keep the
seed at ten or more when you change it.
"""

import os
import sqlite3

DATA_DIR = "/app/data"
DATABASE_NAME = os.path.join(DATA_DIR, "student4.db")

os.makedirs(DATA_DIR, exist_ok=True)

conn = sqlite3.connect(DATABASE_NAME)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS records (
    record_id   INTEGER PRIMARY KEY,
    title       TEXT NOT NULL,
    category    TEXT NOT NULL,
    detail      TEXT NOT NULL DEFAULT '',
    created_on  TEXT NOT NULL
)
""")

cursor.execute("DELETE FROM records")

records = [
    (i, "profile {}".format(i), "profile", "Placeholder Account & Dashboard record {}".format(i),
     "2026-08-{:02d}".format(i))
    for i in range(1, 13)
]

cursor.executemany(
    """
    INSERT INTO records (record_id, title, category, detail, created_on)
    VALUES (?, ?, ?, ?, ?)
    """,
    records,
)

conn.commit()
conn.close()

print(f"student-4-db initialised with {len(records)} records.")
