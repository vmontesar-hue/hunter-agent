import sqlite3
import os
import sys

# DATABASE PATH
DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'opportunities.db')

def seed_examples():
    """
    Allow user to manually enter positive examples to train the semantic filter.
    """
    if not os.path.exists(DB_NAME):
        print(f"Error: Database not found at {DB_NAME}")
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    print("\n" + "="*60)
    print("       SEMANTIC FILTER SEEDER TOOL")
    print("="*60)
    print("Use this tool to teach the AI what you WANT (Positive Examples).")
    print("Describe the ideal opportunity (e.g., 'Tech startup raising Series A in Spain').")
    print("Type 'EXIT' to finish.\n")

    count = 0
    while True:
        text = input(f"\nExample #{count + 1} (or EXIT): ").strip()
        
        if text.upper() == 'EXIT':
            break
        
        if not text:
            continue
        
        # Insert as a 'relevant' opportunity
        # We use a unique source_url to identify it as manual seed
        import time
        try:
            timestamp = int(time.time())
            cursor.execute("""
                INSERT INTO opportunities (source_url, content, headline, source_type, status, feedback_rationale)
                VALUES (?, ?, ?, 'manual_seed', 'relevant', 'Manual Seed')
            """, (f"manual_{timestamp}_{count}", text, text[:50]))
            
            conn.commit()
            print(f"  -> Saved! The AI will now look for things like: '{text[:40]}...'")
            count += 1
            
        except sqlite3.IntegrityError:
             print("  -> Skipped (Duplicate?)")
        except Exception as e:
            print(f"  -> Error: {e}")

    conn.close()
    
    if count > 0:
        print(f"\nSuccess! Added {count} new positive examples.")
        print("IMPORTANT: Now run 'python bootstrap_semantic.py' to update the filter!")
    else:
        print("\nNo examples added.")

if __name__ == "__main__":
    seed_examples()
