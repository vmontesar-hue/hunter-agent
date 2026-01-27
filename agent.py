import os
import json
import time
import re
import pickle 
import requests
import sqlite3
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv

from database import add_opportunity, get_all_opportunity_urls, get_all_feedback_examples, get_recent_opportunities, add_pending_article, add_ai_rejected_article, get_pending_articles, clear_pending_articles
from slack_notifier import send_slack_notification
from scrapers import scrape_glassdoor_jobs
from knowledge_extractor import load_distilled_rules, format_rules_for_prompt
from deduplicator import is_duplicate_opportunity, extract_key_entities
from semantic_filter import semantic_pre_filter, add_positive_example, add_negative_example, get_training_stats

load_dotenv()
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# =============================================================================
# API COST CONTROL CONFIG - UPDATE THIS SECTION WHEN MODELS/LIMITS CHANGE
# =============================================================================
MODEL_ROTATION = [
    {"name": "gemini-3-flash-preview",  "limit": 20},  # Works! 5 RPM, 20 RPD
    {"name": "gemini-2.5-flash",        "limit": 20},  # 5 RPM, 20 RPD
    {"name": "gemini-2.5-flash-lite",   "limit": 20},  # 10 RPM, 20 RPD
    {"name": "gemini-2.0-flash",        "limit": 20},  # 10 RPM, 20 RPD
    {"name": "gemini-2.0-flash-lite",   "limit": 20},  # 10 RPM, 20 RPD
]
RATE_LIMIT_SLEEP = 15  # seconds between API calls (5 RPM = need 12s, using 15s for safety)
ML_FILTER_THRESHOLD = 0.65  # 65% relevance probability required to pass ML filter
TOTAL_DAILY_LIMIT = sum(m["limit"] for m in MODEL_ROTATION)  # Auto-calculated: 100
# =============================================================================


# --- CONTEXTO ESTRATÉGICO DETALLADO DE IGENERIS ---
IGENERIS_CONTEXT = """
    - **Modelo:** Somos "constructores", no consultores. Nos implicamos operativamente desde el diseño y la validación hasta el lanzamiento y el escalado de nuevos negocios.
    - **Ofertas Clave:**

      1.  **Estrategia de Innovación de Negocio:** Abarcamos todo el espectro de la creación de valor y el crecimiento corporativo. Esto incluye:
          * **Emprendimiento Corporativo y Growth:** Somos expertos en la concepción, validación, lanzamiento y escalado de nuevas iniciativas que generan impacto en la cuenta de resultados del cliente.
              * **Corporate Venture Building:** Creamos nuevas ventures corporativas desde cero.
              * **Nuevos Productos y Servicios:** Diseñamos y lanzamos nuevas líneas de ingresos.
              * **Nuevas Unidades de Negocio:** Ayudamos a estructurar y poner en marcha nuevas áreas de negocio dentro de la corporación.
          * **Innovación Disruptiva y Estrategia:**
              * Diseñamos e implementamos marcos estratégicos de innovación.
              * Ayudamos a crear y operar vehículos de innovación internos (CVB, CVC, Innovación Abierta).
              * Desarrollamos estrategias Go-To-Market para la penetración en nuevos mercados o segmentos.
          * **Producto Digital:** Diseñamos y desarrollamos productos y negocios digitales escalables, alineando las soluciones tecnológicas con los objetivos de negocio.

      2.  **Estrategia Basada en el Dato:** Como partner #1 de Palantir en España, transformamos los datos en ventajas competitivas.
          * Implementamos Palantir Foundry para crear "gemelos digitales".
          * Aplicamos analítica avanzada e IA para optimizar operaciones y generar predicciones.
          * Creamos nuevos modelos de negocio basados en la monetización de datos.

    - **Flywheel:** La experiencia en un proyecto (ej. energía con Galp) nos da una ventaja competitiva ("derecho a ganar") en oportunidades similares. Menciona esto si es relevante.
    - **Perfil de Cliente Ideal (ICP):** Buscamos grandes corporaciones (a partir de 80 millones de dolares de facturación anual - o equivalente en moneda local - o 2000 empleados), a menudo multinacionales, en España, Portugal y América Latina (especialmente México, Perú, Chile, Colombia y Guatemala), que se encuentren en un punto de inflexión. Esto puede ser un 'Líder Consolidado Bajo Presión' (necesita innovar para defenderse) o un 'Líder Ambicioso' (quiere expandirse a nuevos mercados o tecnologías).
"""

# --- FUNCIÓN DE RECOLECCIÓN DE NOTICIAS ---
def get_news_from_newsdata(config):
    """
    Obtiene noticias de la API newsdata.io usando la jerarquía de Tiers definida en config.json.
    """
    print(" -> Buscando noticias (estrategia jerárquica por Tiers)...", flush=True)
    all_articles = []
    seen_urls = set()

    api_key = os.environ.get("NEWS_API_KEY_V2")
    if not api_key:
        print("   -> ERROR: No se encontró la variable de entorno NEWS_API_KEY_V2.")
        return []

    trigger_lexicon = config.get("trigger_lexicon", {})
    keywords = {kw for category in trigger_lexicon.values() for lang in category.values() for kw in lang}

    country_tiers = config.get("search_tiers", {}).values()

    print(f"   -> Buscando {len(keywords)} palabras clave en {len(country_tiers)} Tiers de países.")

    for group in country_tiers:
        print(f"\n--- Buscando en el Tier de países: {group} ---", flush=True)
        for keyword in list(keywords):
            try:
                print(f"  - Consultando para keyword '{keyword}'...", flush=True)
                query = requests.utils.quote(keyword)
                url = f"https://newsdata.io/api/1/news?apikey={api_key}&q={query}&country={group}&language=es,en"

                response = requests.get(url)
                response.raise_for_status()
                articles = response.json().get('results', [])

                for article in articles:
                    article_url = article.get('link')
                    if article_url and article_url not in seen_urls:
                        all_articles.append({
                            "source_url": article_url,
                            "content": f"{article.get('title', '')}. {article.get('description', '')}",
                            "source_type": "noticia",
                            "country": article.get('country', [])[0] if (isinstance(article.get('country'), list) and article.get('country')) else None
                        })
                        seen_urls.add(article_url)

            except requests.exceptions.RequestException as e:
                print(f"    -> Error en la consulta para '{keyword}': {e}")
            finally:
                print("    -> Pausa de 30 segundos...")
                time.sleep(30)

    print(f" -> Búsqueda de noticias finalizada. Se encontraron {len(all_articles)} artículos.", flush=True)
    return all_articles

# --- PROMPTS DE ANÁLISIS CON IA ---
# --- FILTRO DE PRE-CLASIFICACIÓN (HÍBRIDO: ML) ---
def load_ml_model(model_path='filter_model.pkl'):
    try:
        if os.path.exists(model_path):
            with open(model_path, 'rb') as f:
                return pickle.load(f)
    except Exception as e:
        print(f"  -> Error loading ML model: {e}")
    return None

# Cargar modelo al iniciar (variable global para no recargar)
ml_model = load_ml_model()

def pre_filter_content(content, config):
    """
    Filtro Híbrido:
    1. Intenta primero el filtro semántico (Sentence Transformers)
    2. Fallback: Naive Bayes si el semántico no está disponible
    """
    if not content:
        return False
    
    # 1. SEMANTIC FILTERING (Primary - uses embeddings with reasons)
    stats = get_training_stats()
    if stats['model_loaded'] and (stats['positive_count'] > 0 or stats['negative_count'] > 0):
        return semantic_pre_filter(content, threshold=ML_FILTER_THRESHOLD)
    
    # 2. NAIVE BAYES FALLBACK (If no semantic data yet)
    if ml_model:
        try:
            # Predict probability: [prob_irrelevant, prob_relevant]
            proba = ml_model.predict_proba([content])[0]
            prob_relevant = proba[1]
            
            if prob_relevant < ML_FILTER_THRESHOLD: 
                print(f"  -> ML Filter (Naive Bayes): REJECTED (Score: {prob_relevant:.2f})")
                return False
                
        except Exception as e:
            print(f"  -> ML Prediction Error: {e}")

    # If no model or model approves, pass through
    return True


# --- PROMPT UNIFICADO DE ANÁLISIS ---
def get_combined_analysis_prompt(text_to_analyze, source_type):
    """
    Combina clasificación y extracción en una sola llamada para ahorrar tokens.
    """
    # Load distilled rules that condense ALL feedback into compact criteria
    distilled_rules = load_distilled_rules()

    learned_criteria = ""
    guidance_text = ""
    
    if distilled_rules:
        # Rules for classification
        learned_criteria = format_rules_for_prompt(distilled_rules)
        # Signals for extraction quality
        if distilled_rules.get('positive_signals'):
             guidance_text += "Asegúrate capturar estos elementos si existen:\n" + "\n".join([f"  • {s}" for s in distilled_rules['positive_signals'][:3]])
    else:
        # Fallback: Use recent examples
        feedback_examples = get_all_feedback_examples(limit_per_category=3)
        if feedback_examples['relevant']:
            learned_criteria = "\n**EJEMPLOS RELEVANTES:**\n" + "\n".join([f"- {ex['headline']}" for ex in feedback_examples['relevant']])

    return f"""
        Tu rol es actuar como un analista de desarrollo de negocio para Igeneris. 
        Realiza un análisis COMPLETO (Clasificación + Extracción) del siguiente texto.
        
        **CONTEXTO SOBRE IGENERIS:**
        {IGENERIS_CONTEXT}

        **CRITERIOS DE CLASIFICACIÓN:**
        1.  **ACCIÓN CONCRETA:** Debe ser una acción específica (inversión, M&A, lanzamiento, expansión) de una empresa grande (ICP).
        2.  **FIT:** Debe encajar con nuestras ofertas (Corporate Venturing, Estrategia de Datos, etc.).
        
        {learned_criteria}
        {guidance_text}

        **Texto a analizar ({source_type}):**
        "{text_to_analyze}"

        **INSTRUCCIONES DE RESPUESTA:**
        Responde ÚNICAMENTE con un objeto JSON.
        
        Si NO es una oportunidad (is_opportunity = false), el JSON debe ser:
        {{
            "is_opportunity": false,
            "reason": "Explicación breve de por qué se descartó"
        }}

        Si SÍ es una oportunidad (is_opportunity = true), el JSON debe incluir los detalles:
        {{
            "is_opportunity": true,
            "company_name": "Nombre de la empresa",
            "opportunity_summary": "Resumen ejecutivo de la acción concreta",
            "igeneris_fit": "Por qué encaja con Igeneris",
            "proposed_solution": "Hipótesis de solución/servicio",
            "value_proposition": "Propuesta de valor en una frase"
        }}
    """

def analyze_text_with_ai(prompt, model_name="gemini-2.0-flash"):
    """
    Analyzes text using the specified Gemini model.
    
    Args:
        prompt: The prompt to send to the model
        model_name: Name of the Gemini model to use (from MODEL_ROTATION config)
    """
    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            json_text = response.text.strip().lstrip("```json").rstrip("```")
            return json.loads(json_text)
        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                print(f"  -> AVISO: Rate limit (429) detectado en {model_name}. Reintentando en {retry_delay}s... (Intento {attempt + 1}/{max_retries})", flush=True)
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                print(f"  -> ERROR: Fallo en análisis IA con {model_name} (final): {e}", flush=True)
                return None
    return None




# --- FLUJO PRINCIPAL UNIFICADO ---
def run_collection_phase(config):
    """
    Flujo principal que ahora aplica la búsqueda por Tiers a TODAS las fuentes.
    """
    print("Iniciando fase de recolección de oportunidades...", flush=True)
    all_items_to_process = []

    data_sources = config.get("data_sources", {})
    search_tiers = config.get("search_tiers", {}).values()

    # 1. Recolectar Noticias si está habilitado
    if data_sources.get("news_api", {}).get("enabled", False):
        all_items_to_process.extend(get_news_from_newsdata(config))

    # 2. Recolectar Empleos si está habilitado
    if data_sources.get("job_portals", {}).get("enabled", False):
        print(" -> Buscando vacantes de empleo (estrategia jerárquica por Tiers)...", flush=True)
        job_titles = config.get("job_monitoring", {}).get("target_job_titles", [])

        # --- CAMBIO: El bucle de empleos ahora también usa los Tiers ---
        for tier_countries_str in search_tiers:
            # La API de Glassdoor (a través de nuestra URL) solo acepta un país a la vez
            for location in tier_countries_str.split(','):
                print(f"\n--- Buscando empleos en el país: {location} ---", flush=True)
                for title in job_titles:
                    found_jobs = scrape_glassdoor_jobs(title, location)
                    for job in found_jobs:
                        all_items_to_process.append({
                            "source_url": job["source_url"],
                            "content": f"Vacante: {job['title']}. Empresa: {job['company_name']}. Ubicación: {job['location']}",
                            "source_type": "vacante",
                            "country": location
                        })

    if not all_items_to_process:
        print("Fase de recolección finalizada. No se encontraron nuevos items para analizar.", flush=True)
        return

    processed_urls = get_all_opportunity_urls()
    recent_opportunities = get_recent_opportunities(days_back=7)  # Últimos 7 días para deduplicación
    new_opportunities_count = 0
    duplicates_found = 0
    api_call_counter = 0  # Tracks total API calls across all models


    for item in all_items_to_process:
        # LAYER 1: URL-based deduplication (fast)
        if item["source_url"] in processed_urls:
            continue

        print(f"\nProcesando: {item['source_url']}", flush=True)

        # LAYER 2: Pre-Filtering (Python Regex) - ZERO COST
        if not pre_filter_content(item["content"], config):
            print("  -> RECHAZADO por filtro de palabras clave (Python). Ahorro de token.", flush=True)
            continue

        # LAYER 3: Early Semantic Deduplication (Before AI) - ZERO COST
        # Intentamos detectar duplicados usando el texto crudo. 
        # Pasamos empresa="" porque aun no la conocemos, pero la similitud de texto 
        # y la extraccion de entidades dentro de deduplicator haran el trabajo.
        is_duplicate, duplicate_info = is_duplicate_opportunity(
            new_headline=item["content"], # Usamos el contenido/titulo raw
            new_company="", # No la tenemos aun
            recent_opportunities=recent_opportunities,
            days_lookback=7
        )

        if is_duplicate:
            print(f"  -> DUPLICADO SEMÁNTICO DETECTADO (Pre-AI).", flush=True)
            print(f"     Similar a: {duplicate_info['headline']}", flush=True)
            print(f"     Ahorro de token.", flush=True)
            duplicates_found += 1
            continue
        
        
        # LAYER 4: Model Rotation & API Call Budget
        # Determine which model to use based on call count
        current_model = None
        calls_made = 0
        
        for model_config in MODEL_ROTATION:
            if api_call_counter < calls_made + model_config["limit"]:
                current_model = model_config["name"]
                calls_remaining_this_model = calls_made + model_config["limit"] - api_call_counter
                break
            calls_made += model_config["limit"]
        
        # If no model available (exceeded all limits), stop
        if current_model is None:
            print(f"\n⚠️ LÍMITE TOTAL ALCANZADO: {TOTAL_DAILY_LIMIT} llamadas.", flush=True)
            print(f"   Todos los modelos agotados. Deteniendo procesamiento.", flush=True)
            print(f"   Items procesados: {api_call_counter}, Restantes: {len(all_items_to_process) - all_items_to_process.index(item)}", flush=True)
            break
        
        # Log which model we're using
        if api_call_counter == 0 or api_call_counter % 20 == 0:
            print(f"\n📊 Usando modelo: {current_model} (Llamada {api_call_counter + 1}/{TOTAL_DAILY_LIMIT})", flush=True)

        # Rate limiting: Sleep before making the call
        time.sleep(RATE_LIMIT_SLEEP)

        # Make the API call with the selected model
        analysis_prompt = get_combined_analysis_prompt(item["content"], item["source_type"])
        analysis_result = analyze_text_with_ai(analysis_prompt, model_name=current_model)
        api_call_counter += 1  # Increment counter after API call



        if analysis_result and analysis_result.get("is_opportunity") is True:
            print("  -> OPORTUNIDAD DETECTADA Y ANALIZADA.", flush=True)
            
            # Extraemos datos del resultado unificado
            new_headline = analysis_result.get('opportunity_summary', 'Sin resumen')
            new_company = analysis_result.get('company_name', '')
            
            # No necesitamos Deduplicación POST-AI porque ya hicimos PRE-AI
            # (Aunque podriamos repetirla aqui para mayor precision con el nombre exacto de la empresa,
            #  pero para ahorrar tokens confiamos en el filtro previo y la "novedad" real).

            add_opportunity(
                url=item["source_url"],
                headline=new_headline,
                source_type=item["source_type"],
                country=item.get("country"),
                content=item.get("content"),
                analysis_json=json.dumps(analysis_result)
            )

            send_slack_notification(
                analysis_json_str=json.dumps(analysis_result),
                source_url=item["source_url"],
                country=item.get("country")
            )
            new_opportunities_count += 1

            # Train semantic filter with this positive example
            add_positive_example(item.get("content", ""))

            # Agregar a recent_opportunities para detectar duplicados en este mismo ciclo
            recent_opportunities.append({
                'headline': new_headline,
                'company_name': new_company,
                'source_url': item["source_url"],
                'notified_at': datetime.now().isoformat(),
                'created_at': datetime.now().isoformat()
            })
        elif analysis_result is None:
            # API ERROR - Queue article for retry in next cycle
            print(f"  -> ERROR API: Guardando para reintentar.", flush=True)
            api_call_counter -= 1  # Refund the call since it failed
            add_pending_article(
                url=item["source_url"],
                headline=item.get("headline", ""),
                source_type=item["source_type"],
                country=item.get("country"),
                content=item.get("content")
            )
        else:
            # AI rejected - SAVE for ML training with semantic embeddings
            reason = analysis_result.get("reason", "No especificada")
            print(f"  -> IRRELEVANTE (AI). Razón: {reason}", flush=True)
            add_ai_rejected_article(
                url=item["source_url"],
                headline=item.get("headline", ""),
                source_type=item["source_type"],
                country=item.get("country"),
                content=item.get("content"),
                rejection_reason=reason
            )
            # Train semantic filter with this rejection
            add_negative_example(item.get("content", ""), reason)

    print(f"\nFase de recolección finalizada.", flush=True)
    print(f"  -> Nuevas oportunidades: {new_opportunities_count}", flush=True)
    print(f"  -> Duplicados semánticos evitados: {duplicates_found}", flush=True)
    print(f"  -> Llamadas API realizadas: {api_call_counter}/{TOTAL_DAILY_LIMIT}", flush=True)
    
    # Clean up pending queue at end of cycle (within-cycle safety net only)
    clear_pending_articles()


if __name__ == '__main__':
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        run_collection_phase(config)
    except FileNotFoundError:
        print("ERROR: No se encontró el archivo 'config.json'.")
    except json.JSONDecodeError:
        print("ERROR: El archivo 'config.json' tiene un formato incorrecto.")