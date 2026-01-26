"""
Unified Feedback Handler for Hunter Agent
==========================================
Handles Slack feedback for:
- hunter-agent (V1): Writes to CSV
- hunter-agentv2 (V2): Writes to SQLite (5 regional channels)

Location: hunter-agentv2/web_app.py
"""

import os
import json
import sqlite3
import csv
from flask import Flask, request, jsonify
from slack_sdk import WebClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Configuration ---
app = Flask(__name__)

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
client = WebClient(token=SLACK_BOT_TOKEN)

# V2 Channels (hunter-agentv2 - writes to SQLite)
# Format: comma-separated list of channel IDs
V2_CHANNEL_IDS = [
    "C0A35QRSH8Q",   # Spain
    "C0A2F3BPSUC",   # Portugal, Brazil
    "C0A29EHE5U6",   # Mexico
    "C0A254D9RQT",   # Peru, Chile, Colombia
    "C0A29EXJ8RL",   # Guatemala, Argentina, Ecuador, Paraguay, Uruguay
]

# Also allow configuration via environment variable (overrides defaults)
env_v2_channels = os.environ.get("SLACK_CHANNEL_IDS_V2", "")
if env_v2_channels:
    V2_CHANNEL_IDS = [ch.strip() for ch in env_v2_channels.split(",") if ch.strip()]

# File paths
DB_NAME_V2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'opportunities.db')

# Validate required config
if not SLACK_BOT_TOKEN:
    # Warning only, so app doesn't crash on import if env not loaded yet
    print("Warning: SLACK_BOT_TOKEN not found in environment", flush=True)

print(f"Feedback Handler initialized:", flush=True)
print(f"Feedback Handler initialized:", flush=True)
print(f"  V2 Channels: {V2_CHANNEL_IDS}", flush=True)
print(f"  V2 Database: {DB_NAME_V2}", flush=True)


# --- Database Functions ---
def log_feedback_to_db_v2(url, feedback, rationale):
    """Save feedback to hunter-agentv2 SQLite database."""
    try:
        conn = sqlite3.connect(DB_NAME_V2)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE opportunities SET status = ?, feedback_rationale = ? WHERE source_url = ?",
            (feedback, rationale, url)
        )
        conn.commit()
        rows_affected = cursor.rowcount
        conn.close()
        
        if rows_affected > 0:
            print(f"✅ Feedback V2 guardado para {url}", flush=True)
        else:
            print(f"⚠️ URL no encontrada en BD: {url}", flush=True)
        return rows_affected > 0
    except Exception as e:
        print(f"❌ ERROR al escribir en la BD V2: {e}", flush=True)
        return False





# --- Slack Modal Definition ---
def get_feedback_modal(source_url):
    """Returns the Slack modal view for feedback submission."""
    return {
        "type": "modal",
        "callback_id": "feedback_submission_v2",
        "title": {"type": "plain_text", "text": "Añadir Feedback"},
        "submit": {"type": "plain_text", "text": "Enviar"},
        "private_metadata": source_url,
        "blocks": [
            {
                "type": "input",
                "block_id": "status_block",
                "label": {"type": "plain_text", "text": "Calificación"},
                "element": {
                    "type": "radio_buttons",
                    "action_id": "status_input",
                    "options": [
                        {"text": {"type": "plain_text", "text": "✅ Relevante"}, "value": "relevant"},
                        {"text": {"type": "plain_text", "text": "❌ No Relevante"}, "value": "irrelevant"}
                    ]
                }
            },
            {
                "type": "input",
                "block_id": "rationale_block",
                "label": {"type": "plain_text", "text": "Justificación (Opcional)"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "rationale_input",
                    "multiline": True
                },
                "optional": True
            }
        ]
    }


# --- Main Route ---
@app.route('/', methods=['POST'])
def handle_all_feedback():
    """
    Unified endpoint for all Slack interactions.
    Routes to V1 or V2 handler based on channel ID.
    """
    payload_str = request.form.get('payload')
    if not payload_str:
        return jsonify({'error': 'No payload'}), 400

    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid JSON'}), 400

    # Determine channel ID from payload
    channel_id = None
    
    # For button clicks, channel is in payload
    if payload.get('channel'):
        channel_id = payload.get('channel', {}).get('id')
    
    # For modal submissions, check callback_id
    if payload.get('type') == 'view_submission':
        callback_id = payload.get('view', {}).get('callback_id', '')
        if callback_id == 'feedback_submission_v2':
            # V2 modal submission - handle directly
            return handle_v2_modal_submission(payload)
        elif callback_id == 'feedback_submission':
            # Legacy callback_id - also V2
            return handle_v2_modal_submission(payload)

    # Route based on Action ID (Prioritize V2 'open_feedback_modal')
    # This ensures that even if a message is in a "V1" channel, 
    # if it has the V2 button, it gets the V2 modal behavior.
    if payload.get('type') == 'block_actions':
        action_id = payload.get('actions', [{}])[0].get('action_id')
        if action_id == 'open_feedback_modal':
            return handle_v2_interaction(payload)

    # Fallback: Route based on channel
    if channel_id in V2_CHANNEL_IDS:
        return handle_v2_interaction(payload)
    else:
        print(f"⚠️ Canal no reconocido: {channel_id} - Usando V2 por defecto", flush=True)
        # Default to V2 behavior for unknown channels
        return handle_v2_interaction(payload)


def handle_v2_interaction(payload):
    """Handle V2 button clicks - open feedback modal."""
    print("📥 Petición recibida para Agente V2", flush=True)
    
    if payload.get('type') == 'block_actions':
        action = payload.get('actions', [{}])[0]
        action_id = action.get('action_id', '')
        
        if action_id == 'open_feedback_modal':
            trigger_id = payload['trigger_id']
            source_url = action.get('value', '')
            
            try:
                client.views_open(
                    trigger_id=trigger_id,
                    view=get_feedback_modal(source_url)
                )
                return "", 200
            except Exception as e:
                print(f"❌ Error abriendo modal: {e}", flush=True)
                return "Error opening modal", 500
    
    return "Acción V2 no reconocida", 200


def handle_v2_modal_submission(payload):
    """Handle V2 modal form submission."""
    print("📥 Modal V2 enviado", flush=True)
    
    try:
        view_state = payload['view']['state']['values']
        source_url = payload['view']['private_metadata']
        status = view_state['status_block']['status_input']['selected_option']['value']
        rationale = view_state['rationale_block']['rationale_input'].get('value') or ""
        
        log_feedback_to_db_v2(source_url, status, rationale)
        return "", 200
    except Exception as e:
        print(f"❌ Error procesando modal V2: {e}", flush=True)
        return "", 200  # Return 200 to avoid Slack error message





# --- Health Check ---
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring."""
    return jsonify({
        'status': 'healthy',
        'v2_channels': V2_CHANNEL_IDS,
        'db_path': DB_NAME_V2
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
