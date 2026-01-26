import sqlite3

db_path = 'c:/Users/VictorMontesa/projects/agents/hunter-agentv2/opportunities.db'

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # List tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables:", tables)
    
    for table_name in tables:
        table = table_name[0]
        print(f"\nSchema for table '{table}':")
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        for col in columns:
            print(col)
            
        # Check first few rows
        cursor.execute(f"SELECT * FROM {table} LIMIT 1")
        row = cursor.fetchone()
        if row:
            print(f"Sample row from '{table}':", row)
        else:
            print(f"Table '{table}' is empty.")

    conn.close()

except Exception as e:
    print(f"Error: {e}")
