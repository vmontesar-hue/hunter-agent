import os
import json
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

def send_slack_notification(analysis_json_str, source_url, country=None):
    """
    Formatea y envía una notificación a Slack al canal correspondiente según la región.
    """
    slack_token = os.environ.get("SLACK_BOT_TOKEN")
    client = WebClient(token=slack_token)
    
    # Canales por región (Hardcoded según solicitud del usuario)
    CHANNELS = {
        'es': 'CHANNELID',  # Spain
        'pt': 'CHANNELID',  # Portugal/Brazil
        'br': 'CHANNELID',  # Portugal/Brazil
        'mx': 'CHANNELID',  # Mexico
        'pe': 'CHANNELID',  # Peru/Chile/Colombia
        'cl': 'CHANNELID',  # Peru/Chile/Colombia
        'co': 'CHANNELID',  # Peru/Chile/Colombia
        'gt': 'CHANNELID',  # Guatemala/Argentina/Ecuador/Paraguay/Uruguay
        'ar': 'CHANNELID',  # Guatemala/Argentina/Ecuador/Paraguay/Uruguay
        'ec': 'CHANNELID',  # Guatemala/Argentina/Ecuador/Paraguay/Uruguay
        'py': 'CHANNELID',  # Guatemala/Argentina/Ecuador/Paraguay/Uruguay
        'uy': 'CHANNELID'   # Guatemala/Argentina/Ecuador/Paraguay/Uruguay
    }
    
    # Mapeo de nombres completos a códigos de 2 letras
    COUNTRY_ALIASES = {
        'spain': 'es', 'españa': 'es', 'espana': 'es',
        'portugal': 'pt',
        'brazil': 'br', 'brasil': 'br',
        'mexico': 'mx', 'méxico': 'mx',
        'peru': 'pe', 'perú': 'pe',
        'chile': 'cl',
        'colombia': 'co',
        'guatemala': 'gt',
        'argentina': 'ar',
        'ecuador': 'ec',
        'paraguay': 'py',
        'uruguay': 'uy'
    }

    # Determinar el canal. Primero normalizar el país a código de 2 letras.
    country_key = country.lower() if country else None
    if country_key and country_key not in CHANNELS:
        # Intentar buscar en aliases
        country_key = COUNTRY_ALIASES.get(country_key, country_key)
    channel_id = CHANNELS.get(country_key, os.environ.get("SLACK_CHANNEL_ID_V1")) # Fallback to V1 if not found

    if not slack_token:
        print("Error: Falta la variable de entorno SLACK_BOT_TOKEN.")
        return False
        
    if not channel_id:
         print(f"Error: No se pudo determinar un canal para el país '{country}' (Key: '{country_key}') y no hay fallback.")
         return False


    try:
        analysis = json.loads(analysis_json_str)
        company_name = analysis.get("company_name", "")
        opportunity_summary = analysis.get("opportunity_summary", "")
        COMPANY_fit = analysis.get("COMPANY_fit", "")
        proposed_solution = analysis.get("proposed_solution", "")
        value_proposition = analysis.get("value_proposition", "")
        
        # VALIDACIÓN ESTRICTA: Sin estos campos NO se puede crear el formato rico correcto
        required_values = [company_name, opportunity_summary, COMPANY_fit, proposed_solution, value_proposition]
        if not all(required_values):
            missing = []
            if not company_name: missing.append("company_name")
            if not opportunity_summary: missing.append("opportunity_summary")
            if not COMPANY_fit: missing.append("COMPANY_fit")
            if not proposed_solution: missing.append("proposed_solution")
            if not value_proposition: missing.append("value_proposition")
            print(f"Error: Datos incompletos para formato rico. Campos vacíos: {missing}", flush=True)
            return False  # NO enviar nada si los datos están incompletos
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🚀 Nueva Oportunidad Identificada: {company_name}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Oportunidad:*\n{opportunity_summary}"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Fuente:* <{source_url}|Link al Artículo> | *País:* {country.upper() if country else 'N/A'}"
                    }
                ]
            },
            {"type": "divider"},
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"🔹 *COMPANY Fit (Nuestro Ángulo):*\n{COMPANY_fit}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"🔹 *Nuestra Propuesta de Solución:*\n{proposed_solution}"
                    }
                ]
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Propuesta de Valor:*\n_{value_proposition}_"
                }
            },
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "✍️ Añadir Feedback",
                            "emoji": True
                        },
                        "style": "primary",
                        "value": source_url,
                        "action_id": "open_feedback_modal"
                    }
                ]
            }
        ]

        fallback_text = f"Nueva Oportunidad: {company_name} - {opportunity_summary} (Fuente: {source_url})"

        try:
            # Enviar con formato rico (blocks) - SIN FALLBACK a texto plano
            response = client.chat_postMessage(channel=channel_id, text=fallback_text, blocks=blocks)
            print(f"Notificación enviada a Slack (Canal {channel_id}) para la oportunidad: {company_name}", flush=True)
            return True
        except SlackApiError as e:
            print(f"Error enviando el mensaje a Slack: {e.response['error']}", flush=True)
            return False

    except json.JSONDecodeError:
        print("Error: El string de análisis no es un JSON válido.", flush=True)
    except Exception as e:
        print(f"Un error inesperado ocurrió en send_slack_notification: {e}", flush=True)
    

    return False
