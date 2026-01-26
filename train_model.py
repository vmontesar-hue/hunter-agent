import sqlite3
import pickle
import os
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

# Configuration
DB_PATH = 'opportunities.db'
MODEL_FILE = 'filter_model.pkl'

def get_training_data():
    """Fetches labeled data from the database."""
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return pd.DataFrame()

    conn = sqlite3.connect(DB_PATH)
    
    # Fetch Relevant items (status='relevant') AND Notified items (status='notified')
    # Strategy Update: User requested to treat 'notified' items as 'relevant' initially 
    # to avoid a restrictive model due to lack of explicit positive labels.
    
    query = """
        SELECT headline, content, status 
        FROM opportunities 
        WHERE status IN ('relevant', 'irrelevant', 'notified')
    """
    
    try:
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        print(f"Error reading database: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

def train():
    print("Loading data from database...")
    df = get_training_data()
    
    if df.empty:
        print("No training data found (no items with status 'relevant' or 'irrelevant').")
        print("Please use the agent and provide feedback via Slack to build a dataset.")
        return

    print(f"Found {len(df)} labeled examples.")
    print(df['status'].value_counts())

    # Prepare data
    # We combine headline and content for richer features, or just use headline if content is empty
    df['full_text'] = df['headline'].fillna('') + " " + df['content'].fillna('')
    
    X = df['full_text']
    X = df['full_text']
    # Labeling: 'irrelevant' -> 0, Everything else ('relevant', 'notified') -> 1
    y = df['status'].apply(lambda x: 0 if x == 'irrelevant' else 1)
    
    # Remove rows where mapping failed (if any other status crept in)
    X = X[y.notna()]
    y = y[y.notna()]

    if len(y) < 5:
        print("Not enough data to train (need at least 5 examples per class ideally).")
        return

    # CHECK FOR CLASS IMBALANCE (CRITICAL)
    unique_classes = y.unique()
    if len(unique_classes) < 2:
        print(f"\n⚠️ CRITICAL WARNING: Only found one class of data ({unique_classes[0]}).")
        print("You have 'Irrelevant' examples but ZERO 'Relevant' examples (or vice versa).")
        print("The model cannot learn to distinguish if it hasn't seen both types.")
        print(">> ACTION REQUIRED: Please go to Slack/App and mark at least 1-2 items as 'Relevant'.")
        print(">> Model was NOT saved to prevent blocking all content.")
        return

    # Split (Optional, good for validation output)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Define Pipeline
    # CountVectorizer: Converts text to token counts (Bag of Words)
    # MultinomialNB: Naive Bayes classifier suitable for word counts
    text_clf = Pipeline([
        ('vect', CountVectorizer(stop_words='english')), # Basic English stop words
        ('clf', MultinomialNB()),
    ])

    print("Training model...")
    text_clf.fit(X_train, y_train)

    # Validate
    predictions = text_clf.predict(X_test)
    print("\nModel Evaluation:")
    print(f"Accuracy: {accuracy_score(y_test, predictions):.2f}")
    
    # Train on FULL dataset before saving
    print("Retraining on full dataset...")
    text_clf.fit(X, y)

    # Save
    with open(MODEL_FILE, 'wb') as f:
        pickle.dump(text_clf, f)
    
    print(f"Model saved to {MODEL_FILE}")

if __name__ == "__main__":
    train()
