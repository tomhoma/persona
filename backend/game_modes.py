"""
Game Mode Configuration for PersonaGuess
=========================================
Defines different game modes that filter the person pool by category.
"""

# Game mode definitions
# Each mode maps to a set of occupation QIDs that match the category
GAME_MODES = {
    'all': {
        'name': 'All Persons',
        'name_th': 'บุคคลทั้งหมด',
        'description': 'All famous Thai persons across all categories',
        'description_th': 'บุคคลชื่อดังทุกประเภท',
        'icon': '🌟',
        'occupation_filter': None,  # No filter, includes everyone
        'career_domains': None  # No domain filter
    },

    'entertainment': {
        'name': 'Entertainment',
        'name_th': 'บันเทิง',
        'description': 'Actors, actresses, comedians, TV presenters',
        'description_th': 'นักแสดง ดารา นักแสดงตลก พิธีกร',
        'icon': '🎬',
        'occupation_filter': [
            'Q33999',      # Actor/Actress
            'Q10800557',   # Film actor
            'Q10798782',   # Television actor
            'Q2405480',    # Voice actor
            'Q2259451',    # Stage actor
            'Q245068',     # Comedian
            'Q947873',     # Television presenter
            'Q1329383',    # News presenter
            'Q4610556',    # Model (fashion)
        ],
        'career_domains': ['entertainment', 'media']
    },

    'sports': {
        'name': 'Sports',
        'name_th': 'กีฬา',
        'description': 'Athletes, footballers, and sports personalities',
        'description_th': 'นักกีฬา นักฟุตบอล นักกีฬาอาชีพ',
        'icon': '⚽',
        'occupation_filter': [
            'Q937857',     # Footballer
            'Q11513337',   # Association football player
            'Q10833314',   # Tennis player
            'Q10871364',   # Badminton player
            'Q14089670',   # Muay Thai fighter
            'Q10843402',   # Volleyball player
            'Q10843263',   # Basketball player
            'Q15117302',   # Esports player
            'Q2066131',    # Athlete (general)
        ],
        'career_domains': ['sports']
    },

    'music': {
        'name': 'Music',
        'name_th': 'ดนตรี',
        'description': 'Singers, musicians, composers, DJs',
        'description_th': 'นักร้อง นักดนตรี นักแต่งเพลง ดีเจ',
        'icon': '🎵',
        'occupation_filter': [
            'Q177220',     # Singer
            'Q488205',     # Singer-songwriter
            'Q639669',     # Musician
            'Q855091',     # Guitarist
            'Q36834',      # Composer
            'Q753110',     # Songwriter
            'Q130857',     # Rapper
            'Q5716684',    # Dancer
            'Q2643890',    # Choreographer
            'Q386854',     # Disc jockey (DJ)
        ],
        'career_domains': ['music']
    },

    'important_person': {
        'name': 'Important Persons',
        'name_th': 'บุคคลสำคัญ',
        'description': 'Politicians, leaders, and highly influential figures',
        'description_th': 'นักการเมือง ผู้นำ บุคคลที่มีอิทธิพลสูง',
        'icon': '👔',
        'occupation_filter': [
            'Q82955',      # Politician
            'Q372436',     # Statesman
        ],
        'career_domains': ['politics'],
        'min_achievement_score': 20  # Only include notable politicians
    },

    'arts_culture': {
        'name': 'Arts & Culture',
        'name_th': 'ศิลปะและวัฒนธรรม',
        'description': 'Directors, artists, writers, photographers',
        'description_th': 'ผู้กำกับ ศิลปิน นักเขียน ช่างภาพ',
        'icon': '🎨',
        'occupation_filter': [
            'Q2526255',    # Film director
            'Q3455803',    # Director
            'Q3286043',    # Producer
            'Q1414443',    # Screenwriter
            'Q1028181',    # Painter
            'Q33231',      # Photographer
            'Q15296811',   # Drawer/Illustrator
            'Q483501',     # Artist
            'Q266569',     # Graphic designer
            'Q36180',      # Writer
            'Q6625963',    # Novelist
            'Q15980158',   # Poet
            'Q214917',     # Playwright
            'Q1930187',    # Journalist
        ],
        'career_domains': ['creative_arts', 'writing', 'media']
    },

    'influencers': {
        'name': 'Social Media & Influencers',
        'name_th': 'โซเชียลมีเดียและอินฟลูเอนเซอร์',
        'description': 'YouTubers, influencers, bloggers, content creators',
        'description_th': 'ยูทูบเบอร์ อินฟลูเอนเซอร์ บล็อกเกอร์',
        'icon': '📱',
        'occupation_filter': [
            'Q2722764',    # YouTuber
            'Q13590141',   # Influencer
            'Q7042855',    # Blogger
        ],
        'career_domains': ['media'],
        'era_categories': ['millennial', 'millennial_late', 'gen_z']  # Younger generation
    }
}


def filter_persons_by_mode(person_cache, mode_id, enriched_cache=None):
    """
    Filter person cache by game mode.

    Args:
        person_cache: Dict of all persons {qid: person_data}
        mode_id: Game mode ID (e.g., 'entertainment', 'sports')
        enriched_cache: Optional dict of enriched data for advanced filtering

    Returns:
        List of QIDs that match the game mode criteria
    """
    if mode_id not in GAME_MODES:
        mode_id = 'all'

    mode = GAME_MODES[mode_id]

    # If mode is 'all', return everyone
    if mode['occupation_filter'] is None and mode['career_domains'] is None:
        return list(person_cache.keys())

    filtered_qids = []

    for qid, person_data in person_cache.items():
        # Check occupation filter (basic filtering using factual_qids)
        if mode['occupation_filter']:
            person_occupations = person_data.get('factual_qids', set())
            occupation_match = any(
                occ_qid in person_occupations
                for occ_qid in mode['occupation_filter']
            )

            if not occupation_match:
                continue

        # Check career domain filter (advanced filtering using enriched data)
        if mode['career_domains'] and enriched_cache and qid in enriched_cache:
            enriched = enriched_cache[qid]
            metadata = enriched.get('metadata', {})
            career_domain = metadata.get('career_domain', 'other')

            if career_domain not in mode['career_domains']:
                continue

            # Check minimum achievement score if specified
            if 'min_achievement_score' in mode:
                achievement_score = metadata.get('achievement_score', 0)
                if achievement_score < mode['min_achievement_score']:
                    continue

            # Check era categories if specified
            if 'era_categories' in mode:
                era_category = metadata.get('era_category', 'unknown')
                if era_category not in mode['era_categories']:
                    continue

        # If all checks passed, include this person
        filtered_qids.append(qid)

    return filtered_qids


def get_mode_statistics(person_cache, enriched_cache=None):
    """
    Get statistics for each game mode (how many persons in each category).

    Returns:
        Dict with mode_id -> count
    """
    stats = {}

    for mode_id in GAME_MODES.keys():
        filtered = filter_persons_by_mode(person_cache, mode_id, enriched_cache)
        stats[mode_id] = {
            'count': len(filtered),
            'name': GAME_MODES[mode_id]['name'],
            'name_th': GAME_MODES[mode_id]['name_th'],
            'description': GAME_MODES[mode_id]['description'],
            'description_th': GAME_MODES[mode_id]['description_th'],
            'icon': GAME_MODES[mode_id]['icon']
        }

    return stats
