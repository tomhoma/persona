"""
Improved Similarity Calculation for PersonaGuess Backend
=========================================================
Integrates multi-aspect narrative similarity with existing factual/relational scoring.
"""

import numpy as np


def cosine_similarity(vec1, vec2):
    """Calculate cosine similarity between two vectors."""
    if not isinstance(vec1, np.ndarray):
        vec1 = np.array(vec1)
    if not isinstance(vec2, np.ndarray):
        vec2 = np.array(vec2)

    if vec1.shape != vec2.shape or np.linalg.norm(vec1) == 0 or np.linalg.norm(vec2) == 0:
        return 0.0

    return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))


def jaccard_similarity(set1, set2):
    """Calculate Jaccard similarity between two sets."""
    if not set1 and not set2:
        return 0.0
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union if union > 0 else 0.0


def calculate_metadata_similarity(metadata1, metadata2):
    """
    Calculate similarity based on structured metadata.

    Args:
        metadata1, metadata2: Dict with keys:
            - career_domain: str
            - era_category: str
            - achievement_score: float
            - thematic_tags: list of str

    Returns:
        float: Similarity score 0-1
        dict: Components breakdown
    """
    score = 0.0
    components = {}

    # 1. Career domain match (30% weight)
    domain_match = 1.0 if metadata1.get('career_domain') == metadata2.get('career_domain') else 0.0
    components['domain_match'] = domain_match
    score += domain_match * 0.30

    # 2. Era/generation match (20% weight)
    era_match = 1.0 if metadata1.get('era_category') == metadata2.get('era_category') else 0.0
    # Partial credit for adjacent eras
    era_order = ['pre_boomer', 'boomer', 'gen_x', 'millennial', 'millennial_late', 'gen_z', 'unknown']
    era1_idx = era_order.index(metadata1.get('era_category', 'unknown'))
    era2_idx = era_order.index(metadata2.get('era_category', 'unknown'))
    era_distance = abs(era1_idx - era2_idx)
    if era_distance == 1:
        era_match = 0.5  # Adjacent eras get partial credit
    components['era_match'] = era_match
    score += era_match * 0.20

    # 3. Achievement level similarity (20% weight)
    achievement1 = metadata1.get('achievement_score', 0)
    achievement2 = metadata2.get('achievement_score', 0)
    max_achievement = max(achievement1, achievement2, 1.0)
    min_achievement = min(achievement1, achievement2)
    achievement_similarity = min_achievement / max_achievement
    components['achievement_similarity'] = achievement_similarity
    score += achievement_similarity * 0.20

    # 4. Thematic tag overlap (30% weight)
    tags1 = set(metadata1.get('thematic_tags', []))
    tags2 = set(metadata2.get('thematic_tags', []))
    tag_similarity = jaccard_similarity(tags1, tags2)
    components['tag_similarity'] = tag_similarity
    score += tag_similarity * 0.30

    return score, components


def calculate_improved_narrative_similarity(person1_data, person2_data):
    """
    Calculate comprehensive narrative similarity using multi-aspect approach.

    Args:
        person1_data, person2_data: Dict with keys:
            - embeddings: dict with aspect embeddings
            - metadata: dict with structured metadata

    Returns:
        dict with:
            - overall_score: float (0-1)
            - aspect_scores: dict
            - metadata_score: float
            - explanation: str
    """
    embeddings1 = person1_data.get('embeddings', {})
    embeddings2 = person2_data.get('embeddings', {})
    metadata1 = person1_data.get('metadata', {})
    metadata2 = person2_data.get('metadata', {})

    # 1. Aspect-specific similarities
    career_sim = cosine_similarity(
        embeddings1.get('career_embedding', []),
        embeddings2.get('career_embedding', [])
    )

    achievement_sim = cosine_similarity(
        embeddings1.get('achievement_embedding', []),
        embeddings2.get('achievement_embedding', [])
    )

    bio_sim = cosine_similarity(
        embeddings1.get('biographical_embedding', []),
        embeddings2.get('biographical_embedding', [])
    )

    influence_sim = cosine_similarity(
        embeddings1.get('influence_embedding', []),
        embeddings2.get('influence_embedding', [])
    )

    combined_sim = cosine_similarity(
        embeddings1.get('combined_embedding', []),
        embeddings2.get('combined_embedding', [])
    )

    # 2. Metadata-based similarity
    metadata_sim, metadata_components = calculate_metadata_similarity(metadata1, metadata2)

    # 3. Weighted combination
    weights = {
        'career': 0.20,
        'achievement': 0.15,
        'biographical': 0.20,
        'influence': 0.10,
        'combined': 0.20,
        'metadata': 0.15
    }

    overall_score = (
        weights['career'] * career_sim +
        weights['achievement'] * achievement_sim +
        weights['biographical'] * bio_sim +
        weights['influence'] * influence_sim +
        weights['combined'] * combined_sim +
        weights['metadata'] * metadata_sim
    )

    # 4. Generate explanation
    explanation_parts = []

    if metadata_components['domain_match'] == 1.0:
        explanation_parts.append("Same professional domain")
    if metadata_components['era_match'] >= 0.5:
        explanation_parts.append("Same generation/era")
    if career_sim > 0.7:
        explanation_parts.append("Very similar career trajectory")
    if achievement_sim > 0.6:
        explanation_parts.append("Similar level of recognition")
    if metadata_components['tag_similarity'] > 0.5:
        explanation_parts.append("Shared thematic elements")

    explanation = "; ".join(explanation_parts) if explanation_parts else "Limited narrative overlap"

    return {
        'overall_score': float(overall_score),
        'aspect_scores': {
            'career': float(career_sim),
            'achievement': float(achievement_sim),
            'biographical': float(bio_sim),
            'influence': float(influence_sim),
            'combined': float(combined_sim)
        },
        'metadata_score': float(metadata_sim),
        'metadata_components': metadata_components,
        'explanation': explanation
    }


def get_improved_narrative_explanation(similarity_result):
    """Generate human-readable explanation for improved narrative similarity."""
    score = similarity_result['overall_score']

    if score >= 0.85:
        base = "Extremely high narrative similarity"
    elif score >= 0.75:
        base = "Very high narrative similarity"
    elif score >= 0.65:
        base = "High narrative similarity"
    elif score >= 0.50:
        base = "Moderate narrative similarity"
    elif score >= 0.35:
        base = "Low narrative similarity"
    elif score >= 0.20:
        base = "Very low narrative similarity"
    else:
        base = "Minimal narrative similarity"

    # Add specific explanation
    specific = similarity_result.get('explanation', '')
    if specific:
        return f"{base} - {specific}"
    return base


# Fallback to simple similarity if improved data not available
def calculate_simple_narrative_similarity(vec1, vec2):
    """
    Fallback to simple cosine similarity if improved embeddings not available.
    This maintains backward compatibility.
    """
    return cosine_similarity(vec1, vec2)
