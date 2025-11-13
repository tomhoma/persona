"""
Improved Narrative Embedding and Similarity System
===================================================
Multi-dimensional narrative similarity that combines:
1. Aspect-specific embeddings (career, achievements, biography, influence)
2. Metadata-based similarity (domain, era, achievement level)
3. Thematic tag overlap
4. Temporal/generational similarity

This provides much more accurate narrative similarity than simple text comparison.
"""

import os
import json
import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm


# Model configuration
# For Thai language support, consider using multilingual models
MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2'  # Better multilingual support
# Alternative: 'distiluse-base-multilingual-cased-v2' for longer texts


def cosine_similarity(vec1, vec2):
    """Calculate cosine similarity between two vectors."""
    if not isinstance(vec1, np.ndarray):
        vec1 = np.array(vec1)
    if not isinstance(vec2, np.ndarray):
        vec2 = np.array(vec2)

    if vec1.shape != vec2.shape or np.linalg.norm(vec1) == 0 or np.linalg.norm(vec2) == 0:
        return 0.0

    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))


def jaccard_similarity(set1, set2):
    """Calculate Jaccard similarity between two sets."""
    if not set1 and not set2:
        return 0.0
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union if union > 0 else 0.0


def encode_text_safely(text, model):
    """Encode text with error handling."""
    if not text or not isinstance(text, str) or len(text.strip()) == 0:
        return np.zeros(model.get_sentence_embedding_dimension()).tolist()

    try:
        vector = model.encode(text, convert_to_numpy=True, show_progress_bar=False)
        return vector.tolist()
    except Exception as e:
        print(f"Error encoding text: {e}")
        return np.zeros(model.get_sentence_embedding_dimension()).tolist()


def create_multi_aspect_embeddings(enriched_data, model):
    """
    Create separate embeddings for different narrative aspects.

    Returns dict with:
    - career_embedding: Professional domain and trajectory
    - achievement_embedding: Recognition and accomplishments
    - biographical_embedding: Life story and context
    - influence_embedding: Network and influence patterns
    - combined_embedding: Weighted combination of all aspects
    """

    embeddings = {}

    # 1. Career embedding
    career_text = enriched_data.get('career_narrative', '')
    embeddings['career_embedding'] = encode_text_safely(career_text, model)

    # 2. Achievement embedding
    achievement_text = enriched_data.get('achievement_narrative', '')
    embeddings['achievement_embedding'] = encode_text_safely(achievement_text, model)

    # 3. Biographical embedding
    bio_text = enriched_data.get('biographical_narrative', '')
    embeddings['biographical_embedding'] = encode_text_safely(bio_text, model)

    # 4. Influence embedding
    influence_text = enriched_data.get('influence_narrative', '')
    embeddings['influence_embedding'] = encode_text_safely(influence_text, model)

    # 5. Combined embedding (weighted by importance)
    combined_text = enriched_data.get('combined_narrative', '')
    embeddings['combined_embedding'] = encode_text_safely(combined_text, model)

    return embeddings


def calculate_metadata_similarity(metadata1, metadata2):
    """
    Calculate similarity based on structured metadata.

    Returns a score 0-1 based on:
    - Same career domain
    - Same era/generation
    - Similar achievement level
    - Thematic tag overlap
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

    Returns:
    - overall_score: Combined narrative similarity (0-1)
    - aspect_scores: Breakdown by aspect
    - metadata_score: Structured similarity
    - explanation: Human-readable breakdown
    """

    embeddings1 = person1_data['embeddings']
    embeddings2 = person2_data['embeddings']
    metadata1 = person1_data['metadata']
    metadata2 = person2_data['metadata']

    # 1. Aspect-specific similarities
    career_sim = cosine_similarity(
        embeddings1['career_embedding'],
        embeddings2['career_embedding']
    )

    achievement_sim = cosine_similarity(
        embeddings1['achievement_embedding'],
        embeddings2['achievement_embedding']
    )

    bio_sim = cosine_similarity(
        embeddings1['biographical_embedding'],
        embeddings2['biographical_embedding']
    )

    influence_sim = cosine_similarity(
        embeddings1['influence_embedding'],
        embeddings2['influence_embedding']
    )

    combined_sim = cosine_similarity(
        embeddings1['combined_embedding'],
        embeddings2['combined_embedding']
    )

    # 2. Metadata-based similarity
    metadata_sim, metadata_components = calculate_metadata_similarity(metadata1, metadata2)

    # 3. Weighted combination
    # Weights can be tuned based on testing
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
        explanation_parts.append("Similar level of recognition/achievements")
    if metadata_components['tag_similarity'] > 0.5:
        explanation_parts.append("Shared thematic elements")

    explanation = "; ".join(explanation_parts) if explanation_parts else "Limited narrative overlap"

    return {
        'overall_score': overall_score,
        'aspect_scores': {
            'career': career_sim,
            'achievement': achievement_sim,
            'biographical': bio_sim,
            'influence': influence_sim,
            'combined': combined_sim
        },
        'metadata_score': metadata_sim,
        'metadata_components': metadata_components,
        'explanation': explanation
    }


def main():
    """Generate improved embeddings for all enriched narratives."""
    ENRICHED_DIR = "data/enriched"
    OUTPUT_DIR = "data/narrative_embeddings"
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Loading model: {MODEL_NAME}")
    try:
        model = SentenceTransformer(MODEL_NAME)
    except Exception as e:
        print(f"Error loading model: {e}")
        print("Falling back to default model...")
        model = SentenceTransformer('all-MiniLM-L6-v2')

    # Get all enriched files
    enriched_files = [f for f in os.listdir(ENRICHED_DIR)
                     if f.endswith('.json') and not f.startswith('_')]

    print(f"Processing {len(enriched_files)} enriched narratives...")

    all_embeddings = {}

    for filename in tqdm(enriched_files, desc="Creating embeddings"):
        filepath = os.path.join(ENRICHED_DIR, filename)

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                enriched_data = json.load(f)

            qid = enriched_data['qid']

            # Create multi-aspect embeddings
            embeddings = create_multi_aspect_embeddings(enriched_data, model)

            # Store with metadata
            all_embeddings[qid] = {
                'qid': qid,
                'label': enriched_data['label'],
                'embeddings': embeddings,
                'metadata': enriched_data['metadata'],
                'thematic_tags': enriched_data['thematic_tags']
            }

            # Save individual file
            output_path = os.path.join(OUTPUT_DIR, filename)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(all_embeddings[qid], f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"Error processing {filename}: {e}")
            continue

    # Save combined embeddings file
    combined_path = os.path.join(OUTPUT_DIR, '_all_embeddings.json')
    print(f"Saving combined embeddings to {combined_path}")

    # Save metadata and sample embeddings (not full vectors to save space)
    summary_data = {
        'total_persons': len(all_embeddings),
        'model_used': MODEL_NAME,
        'embedding_dimensions': model.get_sentence_embedding_dimension(),
        'persons': {
            qid: {
                'label': data['label'],
                'metadata': data['metadata'],
                'thematic_tags': data['thematic_tags']
            }
            for qid, data in all_embeddings.items()
        }
    }

    with open(combined_path, 'w', encoding='utf-8') as f:
        json.dump(summary_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Improved embeddings created!")
    print(f"   Total persons: {len(all_embeddings)}")
    print(f"   Model: {MODEL_NAME}")
    print(f"   Embedding dimensions: {model.get_sentence_embedding_dimension()}")
    print(f"   Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
