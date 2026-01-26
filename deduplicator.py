"""
Semantic Deduplication Module for Hunter Agent v2

Purpose: Detect when different news outlets are covering the same story
to avoid sending duplicate opportunities to Slack.

Approach:
1. Extract key entities (company names, key terms)
2. Normalize text (remove stop words, lowercase, etc.)
3. Create content fingerprint using hashing
4. Check similarity against recent opportunities (last 7 days)

Author: Hunter Agent Team
Date: October 2025
"""

import re
import hashlib
from datetime import datetime, timedelta
from difflib import SequenceMatcher


def normalize_text(text):
    """
    Normaliza el texto para comparación semántica.

    Args:
        text (str): Texto original

    Returns:
        str: Texto normalizado
    """
    if not text:
        return ""

    # Convertir a minúsculas
    text = text.lower()

    # Eliminar URLs
    text = re.sub(r'http[s]?://\S+', '', text)

    # Eliminar puntuación y caracteres especiales (mantener espacios)
    text = re.sub(r'[^\w\s]', ' ', text)

    # Eliminar números solos (pero mantener números dentro de palabras como "5G")
    text = re.sub(r'\b\d+\b', '', text)

    # Eliminar palabras muy cortas (artículos, preposiciones)
    words = text.split()
    words = [w for w in words if len(w) > 2]

    # Eliminar stop words comunes en español e inglés
    stop_words = {
        'the', 'and', 'for', 'with', 'that', 'this', 'from', 'are', 'was', 'has',
        'una', 'para', 'con', 'por', 'los', 'las', 'del', 'que', 'como', 'sus'
    }
    words = [w for w in words if w not in stop_words]

    # Unir palabras y eliminar espacios múltiples
    normalized = ' '.join(words)
    normalized = re.sub(r'\s+', ' ', normalized).strip()

    return normalized


def extract_key_entities(text):
    """
    Extrae entidades clave del texto (nombres de empresas, ubicaciones).

    Args:
        text (str): Texto a analizar

    Returns:
        set: Conjunto de entidades clave encontradas
    """
    entities = set()

    # Patrón para nombres de empresas (palabras capitalizadas consecutivas)
    # Ejemplo: "Banco Santander", "Microsoft Corporation"
    company_pattern = r'\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,3})\b'
    companies = re.findall(company_pattern, text)
    entities.update([c.lower() for c in companies if len(c) > 4])

    # Palabras clave de acción (M&A, inversión, expansión, etc.)
    action_keywords = [
        'adquisición', 'fusión', 'inversión', 'expansión', 'lanzamiento',
        'acquisition', 'merger', 'investment', 'expansion', 'launch',
        'venture', 'partnership', 'transformación', 'digital'
    ]

    text_lower = text.lower()
    for keyword in action_keywords:
        if keyword in text_lower:
            entities.add(keyword)

    return entities


def create_content_fingerprint(headline, company_name=None):
    """
    Crea una huella digital del contenido basada en texto normalizado.

    Args:
        headline (str): Titular del artículo
        company_name (str, optional): Nombre de la empresa

    Returns:
        str: Hash MD5 del contenido normalizado
    """
    # Normalizar headline
    normalized_headline = normalize_text(headline)

    # Extraer entidades clave
    entities = extract_key_entities(headline)

    # Agregar company_name si existe
    if company_name:
        normalized_company = normalize_text(company_name)
        entities.add(normalized_company)

    # Crear string combinado para hash
    # Ordenamos las entidades para que el orden no afecte el hash
    sorted_entities = sorted(entities)
    combined = normalized_headline + ' ' + ' '.join(sorted_entities)

    # Crear hash MD5
    fingerprint = hashlib.md5(combined.encode('utf-8')).hexdigest()

    return fingerprint


def calculate_text_similarity(text1, text2):
    """
    Calcula la similitud entre dos textos usando SequenceMatcher.

    Args:
        text1 (str): Primer texto
        text2 (str): Segundo texto

    Returns:
        float: Ratio de similitud (0.0 a 1.0)
    """
    if not text1 or not text2:
        return 0.0

    # Normalizar ambos textos
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)

    # Calcular similitud
    similarity = SequenceMatcher(None, norm1, norm2).ratio()

    return similarity


def check_content_similarity(new_headline, new_company, recent_opportunities, similarity_threshold=0.70):
    """
    Verifica si el contenido nuevo es similar a oportunidades recientes.

    Args:
        new_headline (str): Titular del nuevo artículo
        new_company (str): Nombre de la empresa
        recent_opportunities (list): Lista de oportunidades recientes
        similarity_threshold (float): Umbral de similitud (0.0 a 1.0)

    Returns:
        tuple: (is_duplicate: bool, similar_to: dict or None)
    """
    new_normalized = normalize_text(new_headline)
    new_entities = extract_key_entities(new_headline)

    if new_company:
        # Normalizar y agregar variaciones del nombre de la empresa
        company_normalized = normalize_text(new_company)
        new_entities.add(company_normalized)
        # Agregar también la primera palabra (ej: "Santander" de "Banco Santander")
        company_first_word = company_normalized.split()[0] if company_normalized else ''
        if len(company_first_word) > 3:
            new_entities.add(company_first_word)

    for opp in recent_opportunities:
        opp_headline = opp.get('headline', '')
        opp_company = opp.get('company_name', '')

        # Preparar entidades de la oportunidad existente
        opp_entities = extract_key_entities(opp_headline)
        if opp_company:
            opp_company_normalized = normalize_text(opp_company)
            opp_entities.add(opp_company_normalized)
            opp_company_first_word = opp_company_normalized.split()[0] if opp_company_normalized else ''
            if len(opp_company_first_word) > 3:
                opp_entities.add(opp_company_first_word)

        # REGLA 1: Verificar si la empresa principal es la misma (fuzzy match)
        company_match = False
        if new_company and opp_company:
            # Match exacto normalizado
            if normalize_text(new_company) == normalize_text(opp_company):
                company_match = True
            # Match parcial (ej: "Santander" está en "Banco Santander")
            elif (normalize_text(new_company) in normalize_text(opp_company) or
                  normalize_text(opp_company) in normalize_text(new_company)):
                company_match = True

        # REGLA 2: Similitud de texto alta (75%+)
        text_similarity = calculate_text_similarity(new_headline, opp_headline)

        if text_similarity >= similarity_threshold:
            return True, {
                'headline': opp_headline,
                'company': opp_company,
                'similarity': text_similarity,
                'reason': 'high_text_similarity'
            }

        # REGLA 3: Misma empresa + similitud moderada (50%+)
        if company_match and text_similarity >= 0.45:
            return True, {
                'headline': opp_headline,
                'company': opp_company,
                'similarity': text_similarity,
                'reason': 'same_company_similar_content'
            }

        # REGLA 4: Entidades clave compartidas
        if len(new_entities) > 0 and len(opp_entities) > 0:
            shared_entities = new_entities.intersection(opp_entities)
            entity_overlap_ratio = len(shared_entities) / max(len(new_entities), len(opp_entities))

            # Si comparten empresa + otras entidades clave (acción, país), es duplicado
            if company_match and entity_overlap_ratio >= 0.5:
                return True, {
                    'headline': opp_headline,
                    'company': opp_company,
                    'similarity': entity_overlap_ratio,
                    'reason': 'same_company_shared_entities',
                    'shared_entities': list(shared_entities)
                }

            # Si comparten 70%+ de entidades (aunque no sea la misma empresa), probablemente duplicado
            # Esto captura casos como "Kueski adquirida por Santander" vs "Santander adquiere Kueski"
            if entity_overlap_ratio >= 0.70:
                return True, {
                    'headline': opp_headline,
                    'company': opp_company,
                    'similarity': entity_overlap_ratio,
                    'reason': 'high_entity_overlap',
                    'shared_entities': list(shared_entities)
                }

    # No se encontró duplicado
    return False, None


def is_duplicate_opportunity(new_headline, new_company, recent_opportunities, days_lookback=7):
    """
    Función principal: verifica si una nueva oportunidad es duplicada.

    Args:
        new_headline (str): Titular del nuevo artículo
        new_company (str): Nombre de la empresa
        recent_opportunities (list): Lista de oportunidades recientes de la DB
        days_lookback (int): Días hacia atrás para buscar duplicados (default: 7)

    Returns:
        tuple: (is_duplicate: bool, duplicate_info: dict or None)
    """
    # Filtrar oportunidades por fecha (últimos N días)
    cutoff_date = datetime.now() - timedelta(days=days_lookback)

    filtered_opps = []
    for opp in recent_opportunities:
        # Si tiene fecha de notificación, usarla; sino, usar created_at
        opp_date_str = opp.get('notified_at') or opp.get('created_at')
        if opp_date_str:
            try:
                opp_date = datetime.fromisoformat(opp_date_str)
                if opp_date >= cutoff_date:
                    filtered_opps.append(opp)
            except (ValueError, TypeError):
                # Si hay error parseando fecha, incluir la oportunidad por seguridad
                filtered_opps.append(opp)
        else:
            # Sin fecha, incluir por seguridad
            filtered_opps.append(opp)

    # Verificar similitud de contenido
    return check_content_similarity(
        new_headline=new_headline,
        new_company=new_company,
        recent_opportunities=filtered_opps,
        similarity_threshold=0.75
    )


if __name__ == '__main__':
    # --- TESTS ---
    print("=== Testing Deduplication Module ===\n")

    # Test 1: Misma noticia de diferentes fuentes
    print("Test 1: Same story from different sources")
    headline1 = "Banco Santander adquiere fintech mexicana por 500 millones"
    headline2 = "Santander completa adquisición de startup fintech en México por $500M"

    similarity = calculate_text_similarity(headline1, headline2)
    print(f"  Headline 1: {headline1}")
    print(f"  Headline 2: {headline2}")
    print(f"  Similarity: {similarity:.2%}")
    print(f"  Duplicate? {similarity >= 0.75}\n")

    # Test 2: Noticias completamente diferentes
    print("Test 2: Completely different stories")
    headline3 = "Tesla lanza nuevo modelo de vehículo eléctrico en España"
    headline4 = "Amazon expande su negocio de cloud computing en Colombia"

    similarity2 = calculate_text_similarity(headline3, headline4)
    print(f"  Headline 1: {headline3}")
    print(f"  Headline 2: {headline4}")
    print(f"  Similarity: {similarity2:.2%}")
    print(f"  Duplicate? {similarity2 >= 0.75}\n")

    # Test 3: Verificar extracción de entidades
    print("Test 3: Entity extraction")
    test_text = "Microsoft Corporation anuncia inversión de 100M en startup de IA en México"
    entities = extract_key_entities(test_text)
    print(f"  Text: {test_text}")
    print(f"  Entities: {entities}\n")

    # Test 4: Content fingerprint
    print("Test 4: Content fingerprinting")
    fp1 = create_content_fingerprint("Telefónica invierte en transformación digital", "Telefónica")
    fp2 = create_content_fingerprint("Telefónica apuesta por la transformación digital", "Telefónica")
    fp3 = create_content_fingerprint("BBVA lanza nuevo producto fintech", "BBVA")

    print(f"  FP1: {fp1}")
    print(f"  FP2: {fp2}")
    print(f"  FP3: {fp3}")
    print(f"  FP1 == FP2? {fp1 == fp2}")
    print(f"  FP1 == FP3? {fp1 == fp3}\n")

    # Test 5: Duplicate detection con lista de oportunidades
    print("Test 5: Full duplicate detection")
    recent_opps = [
        {
            'headline': 'Santander adquiere fintech mexicana por 500 millones',
            'company_name': 'Santander',
            'notified_at': datetime.now().isoformat()
        },
        {
            'headline': 'BBVA lanza plataforma de open banking en Perú',
            'company_name': 'BBVA',
            'notified_at': datetime.now().isoformat()
        }
    ]

    new_headline = "Banco Santander completa compra de startup fintech en México"
    new_company = "Santander"

    is_dup, dup_info = is_duplicate_opportunity(new_headline, new_company, recent_opps)
    print(f"  New: {new_headline}")
    print(f"  Is duplicate? {is_dup}")
    if is_dup:
        print(f"  Similar to: {dup_info['headline']}")
        print(f"  Reason: {dup_info['reason']}")
        print(f"  Similarity: {dup_info['similarity']:.2%}")

    print("\n=== Tests Complete ===")
