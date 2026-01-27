"""
Semantic Filter using Sentence Transformers
Replaces Naive Bayes with embedding-based similarity for smarter filtering.
"""
import os
import json
import pickle
import numpy as np
from typing import Optional, Tuple

# Lazy loading to avoid slow startup
_model = None
_embeddings_cache = None

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'semantic_filter.pkl')
SENTENCE_TRANSFORMER_MODEL = 'all-MiniLM-L6-v2'  # ~80MB, very fast

def get_model():
    """Lazy load the sentence transformer model."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(SENTENCE_TRANSFORMER_MODEL)
            print(f"  -> Modelo semántico cargado: {SENTENCE_TRANSFORMER_MODEL}")
        except ImportError:
            print("  -> AVISO: sentence-transformers no instalado. Filtro semántico desactivado.")
            return None
        except Exception as e:
            print(f"  -> Error cargando modelo semántico: {e}")
            return None
    return _model

def load_training_data() -> dict:
    """Load saved embeddings and examples from disk."""
    global _embeddings_cache
    if _embeddings_cache is not None:
        return _embeddings_cache
    
    if os.path.exists(MODEL_PATH):
        try:
            with open(MODEL_PATH, 'rb') as f:
                _embeddings_cache = pickle.load(f)
                print(f"  -> Datos de filtro semántico cargados ({len(_embeddings_cache.get('positive', []))} positivos, {len(_embeddings_cache.get('negative', []))} negativos)")
                return _embeddings_cache
        except Exception as e:
            print(f"  -> Error cargando filtro semántico: {e}")
    
    # Return empty structure if no saved data
    _embeddings_cache = {
        'positive': [],  # List of (text, embedding) tuples for relevant articles
        'negative': [],  # List of (text, reason, embedding) tuples for rejected articles
        'positive_embeddings': None,  # Numpy array of positive embeddings
        'negative_embeddings': None,  # Numpy array of negative embeddings
    }
    return _embeddings_cache

def save_training_data(data: dict):
    """Save embeddings and examples to disk."""
    global _embeddings_cache
    _embeddings_cache = data
    try:
        with open(MODEL_PATH, 'wb') as f:
            pickle.dump(data, f)
    except Exception as e:
        print(f"  -> Error guardando filtro semántico: {e}")

def add_positive_example(text: str):
    """Add a positive (relevant) example to the training data."""
    model = get_model()
    if model is None:
        return
    
    data = load_training_data()
    embedding = model.encode(text)
    data['positive'].append((text, embedding))
    
    # Rebuild embeddings matrix
    if data['positive']:
        data['positive_embeddings'] = np.array([e[1] for e in data['positive']])
    
    save_training_data(data)
    print(f"  -> Añadido ejemplo positivo para entrenamiento semántico")

def add_negative_example(text: str, reason: str):
    """Add a negative (rejected) example with AI's reason."""
    model = get_model()
    if model is None:
        return
    
    # Combine text and reason for richer embedding
    combined = f"{text}\n\nRejection reason: {reason}"
    embedding = model.encode(combined)
    data = load_training_data()
    data['negative'].append((text, reason, embedding))
    
    # Rebuild embeddings matrix
    if data['negative']:
        data['negative_embeddings'] = np.array([e[2] for e in data['negative']])
    
    save_training_data(data)
    print(f"  -> Añadido ejemplo negativo para entrenamiento semántico")

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors."""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def predict_relevance(text: str, threshold: float = 0.65) -> Tuple[bool, float, str]:
    """
    Predict if an article is relevant using semantic similarity.
    
    Returns:
        Tuple of (is_relevant, confidence, explanation)
    """
    model = get_model()
    if model is None:
        # Fallback: pass everything if model not available
        return True, 0.5, "Modelo semántico no disponible"
    
    data = load_training_data()
    
    # If no training data yet, pass everything
    if not data['positive'] and not data['negative']:
        return True, 0.5, "Sin datos de entrenamiento"
    
    # Get embedding for input text
    text_embedding = model.encode(text)
    
    # Calculate average similarity to positive examples
    pos_similarity = 0.0
    if data['positive_embeddings'] is not None and len(data['positive_embeddings']) > 0:
        similarities = [cosine_similarity(text_embedding, pe) for pe in data['positive_embeddings']]
        pos_similarity = max(similarities) if similarities else 0.0
    
    # Calculate average similarity to negative examples
    neg_similarity = 0.0
    most_similar_negative_reason = ""
    if data['negative_embeddings'] is not None and len(data['negative_embeddings']) > 0:
        negative_similarities = []
        for i, ne in enumerate(data['negative_embeddings']):
            sim = cosine_similarity(text_embedding, ne)
            negative_similarities.append((sim, data['negative'][i][1]))  # (similarity, reason)
        
        if negative_similarities:
            most_similar = max(negative_similarities, key=lambda x: x[0])
            neg_similarity = most_similar[0]
            most_similar_negative_reason = most_similar[1]
    
    # Decision logic
    # If more similar to positive examples, it's likely relevant
    if pos_similarity > 0 or neg_similarity > 0:
        # Normalized score: how much more similar to positive vs negative
        total = pos_similarity + neg_similarity
        if total > 0:
            relevance_score = pos_similarity / total
        else:
            relevance_score = 0.5
    else:
        relevance_score = 0.5
    
    is_relevant = relevance_score >= threshold
    
    if is_relevant:
        explanation = f"Similar a ejemplos positivos (score: {relevance_score:.2f})"
    else:
        explanation = f"Similar a rechazos: '{most_similar_negative_reason[:50]}...' (score: {relevance_score:.2f})"
    
    return is_relevant, relevance_score, explanation

def semantic_pre_filter(content: str, threshold: float = 0.65) -> bool:
    """
    Pre-filter content using semantic similarity.
    Drop-in replacement for the Naive Bayes filter.
    
    Args:
        content: Article text to filter
        threshold: Minimum relevance score to pass (0-1)
    
    Returns:
        True if content should be processed by AI, False to skip
    """
    if not content:
        return False
    
    is_relevant, score, explanation = predict_relevance(content, threshold)
    
    if not is_relevant:
        print(f"  -> Filtro Semántico: RECHAZADO ({explanation})")
        return False
    
    return True

# Convenience function to get training stats
def get_training_stats() -> dict:
    """Get statistics about the current training data."""
    data = load_training_data()
    return {
        'positive_count': len(data.get('positive', [])),
        'negative_count': len(data.get('negative', [])),
        'model_loaded': get_model() is not None
    }
