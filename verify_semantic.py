"""
Verification script for Semantic Filter Upgrade
"""
import time
# Wait for imports to be available if running immediately after install
try:
    from semantic_filter import predict_relevance, get_model, SENTENCE_TRANSFORMER_MODEL
except ImportError:
    print("Waiting for dependencies...")
    import time
    time.sleep(5)
    from semantic_filter import predict_relevance, get_model, SENTENCE_TRANSFORMER_MODEL

def verify():
    print("="*60)
    print("VERIFICATION: Semantic Filter Upgrade")
    print("="*60)
    
    # 1. Verify Model Name
    print(f"Target Model: {SENTENCE_TRANSFORMER_MODEL}")
    model = get_model()
    if model:
        print(f"Model Loaded Successfully: {type(model)}")
    else:
        print("ERROR: Model failed to load")
        return

    # 2. Test Scoring on Spanish Content
    # Case A: Relevant (Business/Innovation)
    relevant_text = """
    La empresa española EnergySolar ha anunciado una alianza estratégica con TechGiant para desarrollar 
    nuevas soluciones de hidrógeno verde en México. La inversión inicial será de 50 millones de euros 
    y busca expandir su presencia en el mercado latinoamericano.
    """
    
    # Case B: Irrelevant (Horoscope/General)
    irrelevant_text = """
    Horóscopo de hoy: Aries, tendrás un día lleno de energía. No olvides beber agua y cuidar tu salud.
    En el amor, todo parece indicar que habrá sorpresas.
    """
    
    print("\n--- TEST CASE A: Relevant Spanish Article ---")
    is_rel, score, reason = predict_relevance(relevant_text, threshold=0.50)
    print(f"Text: {relevant_text.strip()[:100]}...")
    print(f"Score: {score:.4f}")
    print(f"Passed: {is_rel}")
    print(f"Reason: {reason}")
    
    print("\n--- TEST CASE B: Irrelevant Spanish Article ---")
    is_rel, score, reason = predict_relevance(irrelevant_text, threshold=0.50)
    print(f"Text: {irrelevant_text.strip()[:100]}...")
    print(f"Score: {score:.4f}")
    print(f"Passed: {is_rel}")
    print(f"Reason: {reason}")

if __name__ == "__main__":
    verify()
