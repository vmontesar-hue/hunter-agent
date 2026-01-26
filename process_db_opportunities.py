import sqlite3
import json
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Ensure we can import from the search path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent import (
    get_combined_analysis_prompt, 
    analyze_text_with_ai,
    pre_filter_content,
    load_ml_model,
    MODEL_ROTATION,
    ML_FILTER_THRESHOLD,
    RATE_LIMIT_SLEEP,
    TOTAL_DAILY_LIMIT
)
from slack_notifier import send_slack_notification
from database import DB_NAME, mark_as_notified, save_analysis, initialize_db

load_dotenv()

def process_opportunities():
    """
    Reads opportunities with status='detected' from the database,
    ensures they are analyzed, sends them to the correct regional Slack channel,
    and updates their status to 'notified'.
    """
    print("Starting processing of detected opportunities...")
    print(f"  -> Model rotation: {len(MODEL_ROTATION)} models, {TOTAL_DAILY_LIMIT} max calls")
    print(f"  -> ML threshold: {ML_FILTER_THRESHOLD}")
    
    # Ensure DB schema is up to date (adds missing columns if needed)
    initialize_db()
    
    # Load ML model for pre-filtering
    ml_model = load_ml_model()
    if ml_model:
        print("  -> ML model loaded successfully")
    else:
        print("  -> WARNING: ML model not found, skipping ML pre-filter")
    
    # API call counter for model rotation
    api_call_counter = 0
    
    def get_current_model():
        """Returns the current model based on api_call_counter"""
        nonlocal api_call_counter
        calls_made = 0
        for model_config in MODEL_ROTATION:
            if api_call_counter < calls_made + model_config["limit"]:
                return model_config["name"]
            calls_made += model_config["limit"]
        return None  # All models exhausted
    
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Get detected opportunities that haven't been notified yet
        cursor.execute("""
            SELECT id, source_url, content, source_type, country, analysis_json, headline 
            FROM opportunities 
            WHERE status IN ('detected', 'analyzed')
        """)
        rows = cursor.fetchall()
        
        print(f"Found {len(rows)} opportunities pending notification.")
        
        processed_count = 0
        error_count = 0
        ml_filtered_count = 0
        
        for row in rows:
            opp_id, url, content, source_type, country, analysis_json_str, headline = row
            
            # Helper to infer country if missing
            if not country and url:
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(url).netloc
                    if domain.endswith('.es'): country = 'es'
                    elif domain.endswith('.mx'): country = 'mx'
                    elif domain.endswith('.pt') or domain.endswith('.br'): country = 'pt'
                    elif domain.endswith('.cl'): country = 'cl'
                    elif domain.endswith('.co'): country = 'co'
                    elif domain.endswith('.pe'): country = 'pe'
                    elif domain.endswith('.ar'): country = 'ar'
                except:
                    pass

            print(f"\nProcessing Opportunity ID {opp_id}: {headline[:50]}...")
            print(f"  -> Country: {country if country else 'Unknown (sending to default)'}")
            
            analysis_result = None
            is_valid_for_notification = False
            
            # Campos REQUERIDOS para el formato rico de Slack
            REQUIRED_FIELDS = ['company_name', 'opportunity_summary', 'igeneris_fit', 'proposed_solution', 'value_proposition']
            
            # 1. Try to use existing analysis
            if analysis_json_str:
                try:
                    analysis_result = json.loads(analysis_json_str)
                    # VALIDACIÓN ESTRICTA: verificar que TODOS los campos requeridos existan y no estén vacíos
                    missing_fields = [f for f in REQUIRED_FIELDS if not analysis_result.get(f)]
                    if missing_fields:
                        print(f"  -> Warning: Analysis incompleto, faltan: {missing_fields}")
                        analysis_result = None  # Considerar inválido
                    else:
                        is_valid_for_notification = True
                except json.JSONDecodeError:
                    print("  -> Warning: Stored analysis JSON is invalid.")
            
            # 2. If no valid analysis, try to generate it using AI (only if we have content)
            if not is_valid_for_notification:
                if content:
                    # ML Pre-filter: Skip if low relevance probability
                    if ml_model:
                        config = {}  # Empty config, we're not using regex filter here
                        if not pre_filter_content(content, config):
                            print(f"  -> ML FILTER: Rejected (below {ML_FILTER_THRESHOLD} threshold)")
                            cursor.execute("UPDATE opportunities SET status = 'ml_filtered' WHERE id = ?", (opp_id,))
                            conn.commit()
                            ml_filtered_count += 1
                            continue
                    
                    # Check API call budget
                    current_model = get_current_model()
                    if current_model is None:
                        print(f"\n⚠️ LÍMITE TOTAL ALCANZADO: {TOTAL_DAILY_LIMIT} llamadas.")
                        print(f"   Deteniendo procesamiento.")
                        break
                    
                    if api_call_counter % 20 == 0:
                        print(f"\n📊 Usando modelo: {current_model} (Llamada {api_call_counter + 1}/{TOTAL_DAILY_LIMIT})")
                    
                    print("  -> Generating analysis with AI...")
                    import time
                    time.sleep(RATE_LIMIT_SLEEP)
                    try:
                        prompt = get_combined_analysis_prompt(content, source_type)
                        analysis_result = analyze_text_with_ai(prompt, model_name=current_model)
                        api_call_counter += 1
                        
                        if analysis_result:
                            # Validar el resultado generado
                            missing_fields = [f for f in REQUIRED_FIELDS if not analysis_result.get(f)]
                            if missing_fields:
                                print(f"  -> Warning: AI generó análisis incompleto, faltan: {missing_fields}")
                                analysis_result = None
                            else:
                                # Guardar análisis válido
                                trigger_event = "ManualProcess" 
                                save_analysis(opp_id, trigger_event, 0.0, json.dumps(analysis_result))
                                print("  -> Analysis generated and saved.")
                                is_valid_for_notification = True
                    except Exception as e:
                        print(f"  -> Error during AI analysis: {e}")
                else:
                    # Sin contenido Y sin análisis válido = registro legacy, marcarlo para no procesarlo más
                    print("  -> LEGACY RECORD: No content stored, no valid analysis. Marking as 'legacy_skip'.")
                    cursor.execute("UPDATE opportunities SET status = 'legacy_skip' WHERE id = ?", (opp_id,))
                    conn.commit()
                    error_count += 1
                    continue  # Saltar al siguiente sin intentar enviar
            
            # 3. Send Notification corresponding to the region (SOLO si es válido para notificación)
            if is_valid_for_notification and analysis_result:
                success = send_slack_notification(
                    analysis_json_str=json.dumps(analysis_result),
                    source_url=url,
                    country=country
                )
                
                if success:
                    mark_as_notified(opp_id)
                    print("  -> SUCCESS: Notification sent and marked as notified.")
                    processed_count += 1
                    import time
                    time.sleep(2) # Pausa de 2s para evitar Rate Limit de Slack (aprox 1 msg/s permitido)
                else:
                    print("  -> FAILED: Could not send Slack notification.")
                    error_count += 1
            else:
                error_count += 1
                print("  -> SKIPPING: Unable to obtain valid analysis.")

        print(f"\nProcessing complete.")
        print(f"  -> Successfully processed: {processed_count}")
        print(f"  -> ML Filtered: {ml_filtered_count}")
        print(f"  -> API calls made: {api_call_counter}/{TOTAL_DAILY_LIMIT}")
        print(f"  -> Errors/Skipped: {error_count}")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    process_opportunities()
