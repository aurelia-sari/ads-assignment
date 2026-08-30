"""Create the Account & Dashboard database (student-4, Aurelia Sari).

No domain tables yet: user accounts and access logs now live in shared-db
(see shared/db/init_db.py) since a user's id and sign-in state are
shared data every feature may need. This file creates the (currently empty)
student4.db so the service has a database file to open, ready for
whatever Account & Dashboard-specific data (e.g. saved
preferences, dashboard widgets) comes next.
"""

import os
import sqlite3

DATA_DIR = "/app/data"
DATABASE_NAME = os.path.join(DATA_DIR, "student4.db")

os.makedirs(DATA_DIR, exist_ok=True)

conn = sqlite3.connect(DATABASE_NAME)
conn.close()

print("student-4-db initialised (no domain tables yet).")
