import sqlite3
import os

DB_NAME = 'opportunities.db'

if not os.path.exists(DB_NAME):
    print("No database found!")
else:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    print("--- Database Statistics ---")
    cursor.execute("SELECT status, COUNT(*) FROM opportunities GROUP BY status")
    for row in cursor.fetchall():
        print(f"Status '{row[0]}': {row[1]}")
        
    print("\n--- Check Content ---")
    # Check if content is empty for notified items
    cursor.execute("SELECT COUNT(*) FROM opportunities WHERE status='notified' AND (content IS NULL OR content='')")
    empty_content = cursor.fetchone()[0]
    print(f"Notified items with EMPTY content: {empty_content}")

    conn.close()
