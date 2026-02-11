"""
Bootstrap script for Semantic Filter
One-time script to populate semantic filter from existing database data.
Run this before the first agent run to avoid Naive Bayes fallback.
"""
import sqlite3
import os

# Import semantic filter functions
from semantic_filter import add_positive_example, add_negative_example, get_training_stats, get_model

DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'opportunities.db')

def bootstrap_semantic_filter():
    """Load existing DB data to train the semantic filter."""
    
    print("=" * 60)
    print("BOOTSTRAP: Semantic Filter Training")
    print("=" * 60)
    
    # Ensure model is loaded first
    model = get_model()
    if model is None:
        print("ERROR: Could not load Sentence Transformer model.")
        print("Make sure sentence-transformers is installed.")
        return
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Get positive examples (notified, relevant)
    cursor.execute("""
        SELECT content, headline FROM opportunities 
        WHERE status IN ('notified', 'relevant') 
    """)

    positive_rows = cursor.fetchall()
    
    # Get negative examples (irrelevant, ai_rejected)
    cursor.execute("""
        SELECT content, headline, analysis_json FROM opportunities 
        WHERE status IN ('irrelevant', 'ai_rejected', 'rejected', 'irrelevant_ai_filtered')
    """)
    negative_rows = cursor.fetchall()
    
    conn.close()
    
    print(f"\nFound in database:")
    print(f"  - Positive examples: {len(positive_rows)}")
    print(f"  - Negative examples: {len(negative_rows)}")
    
    if len(positive_rows) == 0 and len(negative_rows) == 0:
        print("\nNo training data found in database!")
        print("Run the agent first to collect some data, or this is a fresh install.")
        return
    
    # Add positive examples
    print(f"\nTraining positive examples...")
    for i, (content, headline) in enumerate(positive_rows):
        text = f"{headline or ''} {content or ''}"
        if text.strip():
            add_positive_example(text)
            if (i + 1) % 10 == 0:
                print(f"  Processed {i + 1}/{len(positive_rows)} positive examples")
    
    # Add negative examples
    print(f"\nTraining negative examples...")
    import json
    for i, (content, headline, analysis_json) in enumerate(negative_rows):
        text = f"{headline or ''} {content or ''}"
        
        # Try to extract rejection reason from analysis_json
        reason = "User marked irrelevant"
        if analysis_json:
            try:
                analysis = json.loads(analysis_json)
                reason = analysis.get('reason', reason)
            except:
                pass
        
        if text.strip():
            add_negative_example(text, reason)
            if (i + 1) % 10 == 0:
                print(f"  Processed {i + 1}/{len(negative_rows)} negative examples")
    
    # Show final stats
    stats = get_training_stats()
    print(f"\n" + "=" * 60)
    print("BOOTSTRAP COMPLETE")
    print("=" * 60)
    print(f"Semantic filter now has:")
    print(f"  - {stats['positive_count']} positive examples")
    print(f"  - {stats['negative_count']} negative examples")
    print(f"  - Model loaded: {stats['model_loaded']}")
    print(f"\nThe agent will now use the semantic filter instead of Naive Bayes!")

if __name__ == '__main__':
    bootstrap_semantic_filter()
