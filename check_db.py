import sqlite3
import os

DB_PATH = 'opportunities.db'

def check_db():
    if not os.path.exists(DB_PATH):
        print("Database not found.")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check total rows
        cursor.execute("SELECT count(*) FROM opportunities")
        total = cursor.fetchone()[0]
        
        # Check labeled rows
        cursor.execute("SELECT count(*) FROM opportunities WHERE status IN ('relevant', 'irrelevant')")
        labeled = cursor.fetchone()[0]
        
        print(f"Total Rows: {total}")
        print(f"Labeled Rows (Training Data): {labeled}")
        
        conn.close()
    except Exception as e:
        print(f"Error reading DB: {e}")

if __name__ == "__main__":
    check_db()
