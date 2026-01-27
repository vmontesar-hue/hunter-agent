import sqlite3
from datetime import datetime

import os

# Usar ruta absoluta basada en la ubicación del archivo actual
DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'opportunities.db')

def initialize_db():
    """Crea la tabla de oportunidades si no existe."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Asegurarnos de que la columna feedback_rationale existe
    try:
        cursor.execute("ALTER TABLE opportunities ADD COLUMN feedback_rationale TEXT;")
    except sqlite3.OperationalError:
        pass
        
    # Asegurarnos de que la columna country existe
    try:
        cursor.execute("ALTER TABLE opportunities ADD COLUMN country TEXT;")
    except sqlite3.OperationalError:
        pass

    # Asegurarnos de que la columna content existe
    try:
        cursor.execute("ALTER TABLE opportunities ADD COLUMN content TEXT;")
    except sqlite3.OperationalError:
        pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS opportunities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_url TEXT UNIQUE NOT NULL,
            headline TEXT,
            company_name TEXT,
            source_type TEXT,
            country TEXT,
            content TEXT,
            trigger_event TEXT,
            status TEXT DEFAULT 'detected',
            score REAL,
            analysis_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            notified_at TIMESTAMP,
            feedback_rationale TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print("Base de datos inicializada correctamente.")

def add_opportunity(url, headline, source_type, country=None, content=None, analysis_json=None):
    """Añade una nueva oportunidad con todos sus detalles."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO opportunities 
            (source_url, headline, source_type, country, content, analysis_json, processed_at) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (url, headline, source_type, country, content, analysis_json, datetime.now()))
        conn.commit()
        # Devolvemos el ID de la fila insertada para que el agente sepa que tuvo éxito
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        # La URL ya existe, no es un error, simplemente no la añadimos.
        print(f"  -> La URL {url} ya existe en la base de datos.")
        return None
    except Exception as e:
        print(f"  -> ERROR al añadir oportunidad en la base de datos: {e}")
        return None
    finally:
        conn.close()

def get_opportunities_by_status(status):
    """Obtiene todas las oportunidades con un estado específico, incluyendo el tipo de fuente."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # CAMBIO: Añadimos 'source_type' a la consulta SELECT
    cursor.execute("SELECT id, source_url, headline, source_type FROM opportunities WHERE status = ?", (status,))
    rows = cursor.fetchall()
    conn.close()
    # CAMBIO: Añadimos 'source_type' al diccionario que devolvemos
    return [{"id": row[0], "url": row[1], "headline": row[2], "source_type": row[3]} for row in rows]

def get_analysis_json_by_id(opp_id):
    """Obtiene el JSON de análisis para una oportunidad específica."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT analysis_json FROM opportunities WHERE id = ?", (opp_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def update_opportunity_status(opp_id, new_status):
    """Actualiza el estado de una oportunidad."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE opportunities SET status = ?, processed_at = ? WHERE id = ?",
                       (new_status, datetime.now(), opp_id))
    conn.commit()
    conn.close()

def get_all_opportunity_urls():
    """
    Recupera un conjunto (set) de todas las URLs de las oportunidades
    que ya están en la base de datos para una verificación rápida de duplicados.
    """
    try:
        # --- LA CORRECCIÓN ESTÁ AQUÍ ---
        conn = sqlite3.connect(DB_NAME)
        # -------------------------------

        cursor = conn.cursor()
        cursor.execute("SELECT source_url FROM opportunities")
        urls = {item[0] for item in cursor.fetchall()}
        conn.close()
        return urls
    except sqlite3.Error as e:
        print(f"Error de base de datos al obtener URLs: {e}")
        return set() # Devuelve un conjunto vacío en caso de error

def save_analysis(opp_id, trigger_event, score, analysis_json):
    """Guarda el resultado del análisis de la IA en la base de datos."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE opportunities
        SET trigger_event = ?, score = ?, analysis_json = ?, status = 'analyzed', processed_at = ?
        WHERE id = ?
    """, (trigger_event, score, analysis_json, datetime.now(), opp_id))
    conn.commit()
    conn.close()

def log_feedback_with_rationale(url, feedback, rationale):
    """
    NUEVA FUNCIÓN: Registra el feedback del usuario y su justificación.
    La antigua función log_feedback ha sido eliminada.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE opportunities SET status = ?, feedback_rationale = ? WHERE source_url = ?",
                   (feedback, rationale, url))
    conn.commit()
    conn.close()

def mark_as_notified(opp_id):
    """Marca una oportunidad como notificada."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE opportunities SET status = 'notified', notified_at = ? WHERE id = ?",
                       (datetime.now(), opp_id))
    conn.commit()
    conn.close()

def add_pending_article(url, headline, source_type, country=None, content=None):
    """
    Queue an article that failed API analysis for retry later.
    Status 'pending' indicates it should be retried in the next cycle.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO opportunities 
            (source_url, headline, source_type, country, content, status) 
            VALUES (?, ?, ?, ?, ?, 'pending')
        """, (url, headline, source_type, country, content))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        # URL already exists
        return None
    finally:
        conn.close()

def add_ai_rejected_article(url, headline, source_type, country=None, content=None, rejection_reason=None):
    """
    Save articles rejected by AI with the rejection reason for ML training.
    Status 'ai_rejected' is used for semantic filter training.
    """
    import json
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        analysis_json = json.dumps({"is_opportunity": False, "reason": rejection_reason}) if rejection_reason else None
        cursor.execute("""
            INSERT INTO opportunities 
            (source_url, headline, source_type, country, content, analysis_json, 
             status, processed_at) 
            VALUES (?, ?, ?, ?, ?, ?, 'ai_rejected', ?)
        """, (url, headline, source_type, country, content, analysis_json, datetime.now()))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        # URL already exists
        return None
    finally:
        conn.close()

def get_pending_articles():
    """Get all pending articles that need to be retried."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, source_url, headline, source_type, country, content 
        FROM opportunities 
        WHERE status = 'pending'
        ORDER BY created_at ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [
        {'id': r[0], 'source_url': r[1], 'headline': r[2], 
         'source_type': r[3], 'country': r[4], 'content': r[5]}
        for r in rows
    ]

def clear_pending_articles():
    """
    Clear all pending articles at the end of a cycle.
    Pending queue is a within-cycle safety net, not cross-cycle.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM opportunities WHERE status = 'pending'")
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    if deleted > 0:
        print(f"  -> Cola de pendientes limpiada: {deleted} artículos descartados")
    return deleted

def get_all_feedback_examples(limit_per_category=10):
    """
    Recupera ejemplos de feedback (relevantes e irrelevantes) limitados y ordenados por recencia.

    Args:
        limit_per_category (int): Número máximo de ejemplos por categoría (default: 10)

    Returns:
        dict: Diccionario con listas de ejemplos relevantes e irrelevantes
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Obtenemos los ejemplos relevantes MÁS RECIENTES (ordenados por fecha)
    cursor.execute("""
        SELECT headline, feedback_rationale
        FROM opportunities
        WHERE status = 'relevant' AND feedback_rationale IS NOT NULL
        ORDER BY notified_at DESC
        LIMIT ?
    """, (limit_per_category,))
    relevant_examples = cursor.fetchall()

    # Obtenemos los ejemplos irrelevantes MÁS RECIENTES (ordenados por fecha)
    cursor.execute("""
        SELECT headline, feedback_rationale
        FROM opportunities
        WHERE status = 'irrelevant' AND feedback_rationale IS NOT NULL
        ORDER BY notified_at DESC
        LIMIT ?
    """, (limit_per_category,))
    irrelevant_examples = cursor.fetchall()

    conn.close()

    # Devolvemos los resultados en un formato fácil de usar
    return {
        "relevant": [{"headline": row[0], "rationale": row[1]} for row in relevant_examples],
        "irrelevant": [{"headline": row[0], "rationale": row[1]} for row in irrelevant_examples]
    }

def get_recent_opportunities(days_back=7):
    """
    Recupera oportunidades recientes para verificar duplicados semánticos.

    Args:
        days_back (int): Número de días hacia atrás para buscar (default: 7)

    Returns:
        list: Lista de diccionarios con información de oportunidades recientes
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Solo buscamos oportunidades notificadas (ya enviadas a Slack)
    cursor.execute("""
        SELECT headline, company_name, source_url, notified_at, created_at
        FROM opportunities
        WHERE status = 'notified'
        ORDER BY notified_at DESC
        LIMIT 100
    """)

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            'headline': row[0],
            'company_name': row[1],
            'source_url': row[2],
            'notified_at': row[3],
            'created_at': row[4]
        }
        for row in rows
    ]


if __name__ == '__main__':
    initialize_db()