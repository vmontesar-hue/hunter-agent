"""
Knowledge Distillation Module
Extracts compact, actionable rules from ALL feedback examples
instead of using raw examples in prompts.
"""
import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
from database import get_all_feedback_examples

load_dotenv()
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

def distill_feedback_to_rules():
    """
    Analyzes ALL feedback examples and distills them into compact rules.
    Returns a structured set of criteria that can be used in prompts.
    """
    # Get ALL feedback (no limits - we want complete knowledge)
    feedback = get_all_feedback_examples(limit_per_category=1000)

    if not feedback['relevant'] and not feedback['irrelevant']:
        return None

    # Build comprehensive context for AI to analyze
    relevant_text = "\n".join([
        f"- {ex['headline']} | Razón: {ex['rationale'] or 'N/A'}"
        for ex in feedback['relevant']
    ])

    irrelevant_text = "\n".join([
        f"- {ex['headline']} | Razón: {ex['rationale'] or 'N/A'}"
        for ex in feedback['irrelevant']
    ])

    # Use AI to extract patterns and create compact rules
    distillation_prompt = f"""
    Eres un analista experto que debe extraer patrones de feedback de usuarios.

    OBJETIVO: Analizar TODO el feedback histórico y crear una LISTA COMPACTA de criterios
    de tipo SÍ/NO que permitan clasificar oportunidades sin necesidad de ver todos los ejemplos.

    EJEMPLOS MARCADOS COMO RELEVANTES ({len(feedback['relevant'])} total):
    {relevant_text}

    EJEMPLOS MARCADOS COMO IRRELEVANTES ({len(feedback['irrelevant'])} total):
    {irrelevant_text}

    TAREA: Extrae patrones y crea una lista compacta de criterios. Responde SOLO con JSON:

    {{
        "must_have_criteria": [
            "Lista de características que DEBE tener una oportunidad relevante",
            "Ejemplo: Menciona empresa específica con nombre propio",
            "Ejemplo: Acción concreta (M&A, inversión, expansión, nuevo producto)"
        ],
        "must_not_have_criteria": [
            "Lista de características que DESCALIFICAN una oportunidad",
            "Ejemplo: Artículos de opinión o tendencias generales",
            "Ejemplo: Geografía fuera de México, España, Portugal, LATAM"
        ],
        "positive_signals": [
            "Señales positivas que aumentan relevancia",
            "Ejemplo: Mención de transformación digital o innovación",
            "Ejemplo: Empresa con facturación >80M USD o >2000 empleados"
        ],
        "red_flags": [
            "Señales de alarma que sugieren irrelevancia",
            "Ejemplo: Enfoque en problemas sociales/políticos sin componente de negocio",
            "Ejemplo: Proyectos gubernamentales (salvo excepciones estratégicas)"
        ],
        "industry_patterns": [
            "Patrones por industria identificados en el feedback",
            "Ejemplo: Fintech: relevante si hay expansión de servicios",
            "Ejemplo: Retail: relevante si hay apertura de mercados nuevos"
        ],
        "geographic_rules": [
            "Reglas geográficas extraídas del feedback",
            "Ejemplo: PRIORIDAD 1: México, España, Portugal",
            "Ejemplo: EXCLUIR: Europa del Este, Medio Oriente (salvo excepciones)"
        ]
    }}

    IMPORTANTE: Cada criterio debe ser conciso (máximo 15 palabras). Extrae los patrones
    más importantes que se repiten en el feedback.
    """

    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(distillation_prompt)

        # Extract JSON from response
        json_text = response.text.strip()
        # Remove markdown code blocks if present
        if json_text.startswith('```'):
            json_text = json_text.split('```')[1]
            if json_text.startswith('json'):
                json_text = json_text[4:]
        json_text = json_text.strip()

        rules = json.loads(json_text)

        # Add metadata
        rules['metadata'] = {
            'total_relevant_examples': len(feedback['relevant']),
            'total_irrelevant_examples': len(feedback['irrelevant']),
            'distilled_from': len(feedback['relevant']) + len(feedback['irrelevant'])
        }

        return rules

    except Exception as e:
        print(f"Error distilling feedback: {e}")
        return None


def format_rules_for_prompt(rules):
    """
    Formats distilled rules into a compact string for injection into prompts.
    """
    if not rules:
        return ""

    formatted = "\n**CRITERIOS EXTRAÍDOS DE TODO EL FEEDBACK HISTÓRICO**\n"
    formatted += f"(Basado en {rules['metadata']['distilled_from']} ejemplos analizados)\n\n"

    if rules.get('must_have_criteria'):
        formatted += "✅ **DEBE TENER (requisitos obligatorios):**\n"
        for criterion in rules['must_have_criteria']:
            formatted += f"  • {criterion}\n"
        formatted += "\n"

    if rules.get('must_not_have_criteria'):
        formatted += "❌ **NO DEBE TENER (descalificadores automáticos):**\n"
        for criterion in rules['must_not_have_criteria']:
            formatted += f"  • {criterion}\n"
        formatted += "\n"

    if rules.get('positive_signals'):
        formatted += "⭐ **SEÑALES POSITIVAS:**\n"
        for signal in rules['positive_signals']:
            formatted += f"  • {signal}\n"
        formatted += "\n"

    if rules.get('red_flags'):
        formatted += "🚩 **SEÑALES DE ALARMA:**\n"
        for flag in rules['red_flags']:
            formatted += f"  • {flag}\n"
        formatted += "\n"

    if rules.get('geographic_rules'):
        formatted += "🌍 **REGLAS GEOGRÁFICAS:**\n"
        for rule in rules['geographic_rules']:
            formatted += f"  • {rule}\n"
        formatted += "\n"

    if rules.get('industry_patterns'):
        formatted += "🏭 **PATRONES POR INDUSTRIA:**\n"
        for pattern in rules['industry_patterns']:
            formatted += f"  • {pattern}\n"

    return formatted


def save_distilled_rules(rules, filepath='distilled_rules.json'):
    """Save distilled rules to file for caching."""
    if rules:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(rules, f, indent=2, ensure_ascii=False)
        print(f"✅ Distilled rules saved to {filepath}")


def load_distilled_rules(filepath='distilled_rules.json'):
    """Load cached distilled rules from file."""
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading distilled rules: {e}")
    return None


if __name__ == "__main__":
    print("=" * 80)
    print("KNOWLEDGE DISTILLATION: Extracting Rules from ALL Feedback")
    print("=" * 80)

    # Get all feedback
    feedback = get_all_feedback_examples(limit_per_category=1000)
    print(f"\n📊 Analyzing {len(feedback['relevant'])} relevant + {len(feedback['irrelevant'])} irrelevant examples")
    print("🔄 Distilling knowledge using AI...\n")

    # Distill into rules
    rules = distill_feedback_to_rules()

    if rules:
        # Save for future use
        save_distilled_rules(rules)

        # Display the distilled knowledge
        print("\n" + "=" * 80)
        print("DISTILLED KNOWLEDGE (Compact Format)")
        print("=" * 80)
        print(format_rules_for_prompt(rules))

        print("\n" + "=" * 80)
        print("✅ SUCCESS: All feedback condensed into compact criteria")
        print("=" * 80)
        print(f"\nOriginal: {rules['metadata']['distilled_from']} examples")
        print(f"Condensed to: {sum(len(v) for k,v in rules.items() if k != 'metadata')} criteria")

        # Calculate token savings
        original_tokens = rules['metadata']['distilled_from'] * 50  # Estimate
        condensed_tokens = sum(len(v) for k,v in rules.items() if k != 'metadata') * 15  # Estimate
        print(f"\nEstimated token reduction: {original_tokens} → {condensed_tokens}")
        print(f"Savings: {100 - (condensed_tokens/original_tokens*100):.1f}%")
    else:
        print("❌ Failed to distill rules")
