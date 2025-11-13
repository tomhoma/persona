"""
Enhanced Narrative Builder for PersonaGuess
============================================
This module creates richer, multi-aspect narrative representations that capture:
1. Career trajectory and professional domain
2. Achievement magnitude and recognition level
3. Temporal/era context
4. Biographical themes
5. Social network position

This significantly improves narrative similarity accuracy compared to simple Wikipedia summaries.
"""

import os
import json
from collections import defaultdict
from tqdm import tqdm


# Career domain categories for thematic grouping
CAREER_DOMAINS = {
    'entertainment': ['Q33999', 'Q177220', 'Q488205', 'Q10800557', 'Q10798782', 'Q2405480',
                     'Q4610556', 'Q2259451', 'Q245068'],  # actors, singers, comedians
    'sports': ['Q937857', 'Q11513337', 'Q10833314', 'Q10871364', 'Q14089670',
               'Q10843402', 'Q10843263', 'Q15117302', 'Q2066131'],  # athletes
    'creative_arts': ['Q2526255', 'Q3455803', 'Q3286043', 'Q1414443', 'Q1028181',
                      'Q33231', 'Q15296811', 'Q483501', 'Q266569'],  # directors, artists
    'media': ['Q947873', 'Q1329383', 'Q2722764', 'Q13590141', 'Q7042855'],  # presenters, influencers
    'music': ['Q639669', 'Q855091', 'Q36834', 'Q753110', 'Q130857',
              'Q5716684', 'Q2643890', 'Q386854'],  # musicians
    'politics': ['Q82955', 'Q372436'],  # politicians
    'business': ['Q131524', 'Q5322166', 'Q5716455'],  # entrepreneurs, designers
    'writing': ['Q36180', 'Q6625963', 'Q15980158', 'Q214917', 'Q1930187']  # writers, journalists
}

# Recognition/prestige properties (higher weight in narrative)
PRESTIGE_PROPERTIES = {
    'P166': 3.0,   # awards received (high weight)
    'P1411': 2.0,  # nominated for (medium weight)
    'P800': 2.5,   # notable work (high weight)
    'P39': 2.0,    # position held (medium-high weight)
}

# Career progression properties
CAREER_PROPERTIES = {
    'P106': 'occupation',
    'P108': 'employer',
    'P463': 'member_of',
    'P54': 'sports_team',
    'P102': 'political_party'
}

# Influence/mentorship properties
INFLUENCE_PROPERTIES = {
    'P737': 'influenced_by',
    'P738': 'influenced',
    'P1066': 'student_of',
    'P802': 'student',
    'P184': 'doctoral_advisor'
}


def get_career_domain(occupations):
    """Determine primary career domain from occupation QIDs."""
    occupation_qids = {occ.get('qid') for occ in occupations}

    domain_scores = {}
    for domain, domain_qids in CAREER_DOMAINS.items():
        overlap = len(occupation_qids.intersection(set(domain_qids)))
        if overlap > 0:
            domain_scores[domain] = overlap

    if domain_scores:
        return max(domain_scores, key=domain_scores.get)
    return 'other'


def calculate_achievement_score(details):
    """Calculate achievement score based on awards, notable works, positions."""
    score = 0.0

    for prop_code, weight in PRESTIGE_PROPERTIES.items():
        if prop_code in details:
            count = len(details[prop_code])
            score += count * weight

    return min(score, 100.0)  # Cap at 100


def get_era_category(birth_year):
    """Categorize person by era/generation."""
    if birth_year is None:
        return 'unknown'
    elif birth_year >= 2000:
        return 'gen_z'  # Gen Z
    elif birth_year >= 1990:
        return 'millennial_late'
    elif birth_year >= 1980:
        return 'millennial'
    elif birth_year >= 1965:
        return 'gen_x'
    elif birth_year >= 1946:
        return 'boomer'
    else:
        return 'pre_boomer'


def build_enriched_narrative(person_data):
    """
    Build a rich, multi-aspect narrative representation.

    Returns dict with:
    - career_narrative: Professional journey description
    - achievement_narrative: Recognition and accomplishments
    - biographical_narrative: Life story elements
    - thematic_tags: Key themes/topics
    - metadata: Structured data for similarity calculation
    """

    details = person_data.get('details', {})
    summary = person_data.get('narrative_summary', '')
    birth_year = None

    # Extract birth year
    if 'P569' in details and details['P569']:
        birth_date = details['P569'][0].get('qid', '')
        try:
            birth_year = int(birth_date[:4]) if len(birth_date) >= 4 else None
        except:
            pass

    # If not in details, try from manifest data
    if birth_year is None:
        birth_date_str = person_data.get('birth_date', '')
        if birth_date_str:
            try:
                birth_year = int(birth_date_str[:4])
            except:
                pass

    # 1. CAREER NARRATIVE
    occupations = details.get('P106', [])
    career_domain = get_career_domain(occupations)
    occupation_text = ', '.join([occ.get('label', '') for occ in occupations[:3]])

    employers = details.get('P108', [])
    employer_text = ', '.join([emp.get('label', '') for emp in employers[:3]])

    teams = details.get('P54', [])
    team_text = ', '.join([team.get('label', '') for team in teams[:3]])

    career_parts = []
    if occupation_text:
        career_parts.append(f"Professional: {occupation_text}")
    if employer_text:
        career_parts.append(f"Worked at: {employer_text}")
    if team_text:
        career_parts.append(f"Played for: {team_text}")

    career_narrative = '. '.join(career_parts)

    # 2. ACHIEVEMENT NARRATIVE
    awards = details.get('P166', [])
    award_text = ', '.join([award.get('label', '') for award in awards[:5]])

    notable_works = details.get('P800', [])
    work_text = ', '.join([work.get('label', '') for work in notable_works[:5]])

    positions = details.get('P39', [])
    position_text = ', '.join([pos.get('label', '') for pos in positions[:3]])

    achievement_parts = []
    if award_text:
        achievement_parts.append(f"Awards: {award_text}")
    if work_text:
        achievement_parts.append(f"Notable works: {work_text}")
    if position_text:
        achievement_parts.append(f"Positions held: {position_text}")

    achievement_narrative = '. '.join(achievement_parts)
    achievement_score = calculate_achievement_score(details)

    # 3. BIOGRAPHICAL NARRATIVE (enhanced Wikipedia summary)
    birthplace = details.get('P19', [])
    birthplace_text = birthplace[0].get('label', '') if birthplace else ''

    education = details.get('P69', [])
    education_text = ', '.join([edu.get('label', '') for edu in education[:3]])

    bio_parts = []
    if birthplace_text:
        bio_parts.append(f"Born in {birthplace_text}")
    if education_text:
        bio_parts.append(f"Educated at: {education_text}")
    if summary:
        bio_parts.append(summary)

    biographical_narrative = '. '.join(bio_parts)

    # 4. INFLUENCE/NETWORK NARRATIVE
    influenced_by = details.get('P737', [])
    influenced_by_text = ', '.join([p.get('label', '') for p in influenced_by[:3]])

    students = details.get('P802', [])
    student_text = ', '.join([s.get('label', '') for s in students[:3]])

    influence_parts = []
    if influenced_by_text:
        influence_parts.append(f"Influenced by: {influenced_by_text}")
    if student_text:
        influence_parts.append(f"Students: {student_text}")

    influence_narrative = '. '.join(influence_parts) if influence_parts else ''

    # 5. THEMATIC TAGS
    thematic_tags = [
        career_domain,
        get_era_category(birth_year),
        f"achievement_level_{int(achievement_score / 20)}"  # 0-5 scale
    ]

    # Add specific themes
    if awards:
        thematic_tags.append('award_winner')
    if notable_works:
        thematic_tags.append('notable_creator')
    if len(details.get('P161', [])) > 0:  # cast member
        thematic_tags.append('performer')
    if len(details.get('P54', [])) > 0:  # sports team
        thematic_tags.append('team_sports')

    # 6. COMBINED WEIGHTED NARRATIVE
    # Weight different aspects for embedding
    weighted_narrative_parts = [
        career_narrative,  # 1x
        career_narrative,  # repeat for emphasis (2x total)
        achievement_narrative if achievement_score > 10 else '',  # only if significant
        biographical_narrative,
        influence_narrative
    ]

    combined_narrative = '. '.join([p for p in weighted_narrative_parts if p])

    # 7. METADATA for structured comparison
    metadata = {
        'career_domain': career_domain,
        'era_category': get_era_category(birth_year),
        'achievement_score': achievement_score,
        'birth_year': birth_year,
        'num_awards': len(awards),
        'num_notable_works': len(notable_works),
        'num_occupations': len(occupations),
        'has_influence_network': len(influenced_by) > 0 or len(students) > 0,
        'thematic_tags': thematic_tags
    }

    return {
        'qid': person_data['qid'],
        'label': person_data['label'],
        'career_narrative': career_narrative,
        'achievement_narrative': achievement_narrative,
        'biographical_narrative': biographical_narrative,
        'influence_narrative': influence_narrative,
        'combined_narrative': combined_narrative,
        'thematic_tags': thematic_tags,
        'metadata': metadata
    }


def main():
    """Process all persons and create enriched narratives."""
    RAW_DATA_DIR = "data/raw"
    OUTPUT_DIR = "data/enriched"
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Get all person files
    raw_files = [f for f in os.listdir(RAW_DATA_DIR)
                 if f.endswith('.json') and not f.startswith('_')]

    print(f"Building enriched narratives for {len(raw_files)} persons...")

    enriched_data = []
    stats = {
        'total_processed': 0,
        'domain_distribution': defaultdict(int),
        'era_distribution': defaultdict(int),
        'avg_achievement_score': 0.0
    }

    total_achievement = 0.0

    for filename in tqdm(raw_files, desc="Processing"):
        filepath = os.path.join(RAW_DATA_DIR, filename)

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                person_data = json.load(f)

            enriched = build_enriched_narrative(person_data)
            enriched_data.append(enriched)

            # Update stats
            stats['total_processed'] += 1
            stats['domain_distribution'][enriched['metadata']['career_domain']] += 1
            stats['era_distribution'][enriched['metadata']['era_category']] += 1
            total_achievement += enriched['metadata']['achievement_score']

            # Save individual enriched file
            output_path = os.path.join(OUTPUT_DIR, filename)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(enriched, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"Error processing {filename}: {e}")
            continue

    # Calculate average achievement score
    if stats['total_processed'] > 0:
        stats['avg_achievement_score'] = total_achievement / stats['total_processed']

    # Save summary statistics
    summary_path = os.path.join(OUTPUT_DIR, '_enrichment_summary.json')
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump({
            'statistics': {
                'total_processed': stats['total_processed'],
                'average_achievement_score': stats['avg_achievement_score'],
                'domain_distribution': dict(stats['domain_distribution']),
                'era_distribution': dict(stats['era_distribution'])
            },
            'sample_narratives': enriched_data[:5]  # Save first 5 as examples
        }, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Enriched narratives created!")
    print(f"   Total processed: {stats['total_processed']}")
    print(f"   Average achievement score: {stats['avg_achievement_score']:.2f}")
    print(f"\nDomain distribution:")
    for domain, count in sorted(stats['domain_distribution'].items(), key=lambda x: x[1], reverse=True):
        print(f"   {domain}: {count}")
    print(f"\nEra distribution:")
    for era, count in sorted(stats['era_distribution'].items(), key=lambda x: x[1], reverse=True):
        print(f"   {era}: {count}")


if __name__ == "__main__":
    main()
