import sqlite3
try:
    conn = sqlite3.connect('opportunities.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE opportunities SET status = 'detected' WHERE status IN ('relevant', 'error_analysis')")
    updated = cursor.rowcount
    conn.commit()
    print(f"Successfully updated {updated} records to 'detected' status.")
except Exception as e:
    print(f"Error: {e}")
finally:
    if conn: conn.close()
