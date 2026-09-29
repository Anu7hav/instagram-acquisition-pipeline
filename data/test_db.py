import sqlite3

db = r"data\pipeline_ig.db"

print("Checking website database...")
print(db)

conn = sqlite3.connect(db)

tables = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
).fetchall()

print()
print("DATABASE TABLES")
print("---------------")

for table in tables:
    print("-", table[0])

conn.close()