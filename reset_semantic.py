"""
Reset semantic filter training data.
Run this to clear accumulated negatives and start fresh.
"""
import os
import pickle

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'semantic_filter.pkl')

def reset_semantic_filter():
    """Reset the semantic filter training data."""
    print("Resetting semantic filter...")
    
    if os.path.exists(MODEL_PATH):
        os.remove(MODEL_PATH)
        print(f"  -> Deleted {MODEL_PATH}")
    else:
        print(f"  -> No filter file found at {MODEL_PATH}")
    
    print("Done! Run bootstrap_semantic.py to repopulate from database.")

if __name__ == '__main__':
    reset_semantic_filter()
