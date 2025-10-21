import os
import json
import sqlite3
import chromadb
import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
from collections import defaultdict

# --- Configuration ---
DB_DIR = "data"
RAW_DATA_DIR = "data/raw"
SQLITE_PATH = os.path.join(DB_DIR, "persona.db")
CHROMA_PATH = os.path.join(DB_DIR, "chroma")
MODEL_NAME = 'all-MiniLM-L6-v2'

# Expanded property sets
FACTUAL_PROPERTIES = [
    "P106",  # occupation
    "P27",   # country of citizenship  
    "P166",  # award received
    "P69",   # educated at
    "P19",   # place of birth
    "P20",   # place of death
    "P21",   # sex or gender
    "P569",  # date of birth
    "P570",  # date of death
]

RELATIONAL_PROPERTIES = [
    # Direct family relationships
    "P22",   # father
    "P25",   # mother
    "P40",   # child
    "P26",   # spouse
    "P3373", # sibling
    "P1038", # relative
    
    # Professional relationships  
    "P1327", # partner in business or sport
    "P108",  # employer
    "P54",   # member of sports team
    "P463",  # member of
    "P102",  # member of political party
    "P39",   # position held
    
    # Creative relationships
    "P175",  # performer
    "P161",  # cast member
    "P57",   # director
    "P86",   # composer
    "P170",  # creator
    "P50",   # author
    "P1877", # after a work by
    
    # Influence relationships
    "P737",  # influenced by
    "P738",  # influence of
    "P1066", # student of
    "P802",  # student
    "P184",  # doctoral advisor
    
    # Event relationships
    "P1344", # participant in
    "P793",  # significant event
    "P710",  # participant
    
    # Other associations
    "P800",  # notable work
    "P551",  # residence
    "P937",  # work location
    "P140",  # religion
    "P172",  # ethnic group
    "P1412", # languages spoken
]

# Properties that indicate shared context (indirect relationships)
SHARED_CONTEXT_PROPERTIES = {
    "P69": "educated_at",        # Same school/university
    "P108": "worked_at",          # Same employer
    "P54": "played_for",          # Same sports team
    "P463": "member_of",          # Same organization
    "P102": "political_party",    # Same political party
    "P19": "born_in",             # Same birthplace
    "P551": "lived_in",           # Same residence
    "P937": "worked_in",          # Same work location
    "P166": "received_award",     # Same award
    "P1344": "participated_in",   # Same event
}

RELATIONSHIP_TYPE_LABELS = {
    "P22": "father",
    "P25": "mother",
    "P40": "child",
    "P26": "spouse",
    "P3373": "sibling",
    "P1038": "relative",
    "P1327": "partner",
    "P175": "performer",
    "P161": "co-star",
    "P57": "directed_by",
    "P86": "composed_for",
    "P737": "influenced_by",
    "P738": "influenced",
    "P1066": "student_of",
    "P802": "teacher_of",
    "P184": "doctoral_advisor",
}

# --- Database Setup ---
def setup_databases():
    """Initializes SQLite and ChromaDB with comprehensive relationship schema."""
    os.makedirs(DB_DIR, exist_ok=True)

    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS persons (
            qid TEXT PRIMARY KEY,
            label TEXT,
            thwiki_title TEXT,
            birth_year INTEGER,
            occupation_primary TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS person_properties (
            person_qid TEXT,
            property_qid TEXT,
            property_code TEXT,
            type TEXT,
            label TEXT,
            PRIMARY KEY (person_qid, property_qid, property_code)
        )
    """)
    
    # Direct person-to-person relationships
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS person_relationships (
            person1_qid TEXT,
            person2_qid TEXT,
            relationship_type TEXT,
            property_code TEXT,
            strength INTEGER DEFAULT 1,
            PRIMARY KEY (person1_qid, person2_qid, property_code)
        )
    """)
    
    # Shared context relationships (indirect)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shared_contexts (
            person1_qid TEXT,
            person2_qid TEXT,
            context_type TEXT,
            context_qid TEXT,
            context_label TEXT,
            property_code TEXT,
            PRIMARY KEY (person1_qid, person2_qid, context_type, context_qid)
        )
    """)
    
    # Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_person_props ON person_properties(person_qid)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_prop_qid ON person_properties(property_qid)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_relationships ON person_relationships(person1_qid)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_relationships2 ON person_relationships(person2_qid)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shared_contexts ON shared_contexts(person1_qid)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shared_contexts2 ON shared_contexts(person2_qid)")
    
    conn.commit()
    conn.close()

    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(name="narrative_vectors")

    print("Databases initialized with enhanced relationship schema.")
    return client, collection

def extract_birth_year(birth_date_str):
    """Extract year from ISO date string."""
    if birth_date_str and len(birth_date_str) >= 4:
        try:
            return int(birth_date_str[:4])
        except:
            pass
    return None

def build_comprehensive_relationships(person_list, raw_data_dir):
    """Build both direct and indirect (shared context) relationships."""
    all_persons_qids = {p['qid'] for p in person_list}
    
    # Storage for relationships
    direct_relationships = defaultdict(list)
    shared_contexts = defaultdict(lambda: defaultdict(list))
    
    print("Building comprehensive relationship network...")
    
    # First pass: collect all data
    person_data_cache = {}
    for person in tqdm(person_list, desc="Loading person data"):
        qid = person['qid']
        json_path = os.path.join(raw_data_dir, f"{qid}.json")
        
        if not os.path.exists(json_path):
            continue
            
        with open(json_path, 'r', encoding='utf-8') as f:
            person_data_cache[qid] = json.load(f)
    
    # Second pass: identify direct relationships
    print("Finding direct relationships...")
    for qid, person_data in tqdm(person_data_cache.items(), desc="Direct relationships"):
        details = person_data.get("details", {})
        
        # Check direct person-to-person relationships
        for prop_code in RELATIONAL_PROPERTIES:
            if prop_code in details:
                for item in details[prop_code]:
                    if item['qid'] in all_persons_qids:
                        rel_type = RELATIONSHIP_TYPE_LABELS.get(prop_code, item.get('label', 'related'))
                        direct_relationships[qid].append({
                            'person2_qid': item['qid'],
                            'property_code': prop_code,
                            'relationship_type': rel_type,
                            'strength': 3  # Direct relationships are strong
                        })
        
        # Check reverse_relationships from JSON
        reverse_rels = person_data.get("reverse_relationships", [])
        for rel in reverse_rels:
            subject_qid = rel.get('subject_qid')
            if subject_qid and subject_qid in all_persons_qids:
                prop_code = rel.get('property')
                rel_type = RELATIONSHIP_TYPE_LABELS.get(prop_code, 'related')
                direct_relationships[qid].append({
                    'person2_qid': subject_qid,
                    'property_code': prop_code + '_reverse',
                    'relationship_type': rel_type + '_reverse',
                    'strength': 3
                })
        
        # Check collaborations from JSON
        collabs = person_data.get("collaborations", [])
        for collab in collabs:
            collab_qid = collab.get('collaborator_qid')
            if collab_qid and collab_qid in all_persons_qids:
                direct_relationships[qid].append({
                    'person2_qid': collab_qid,
                    'property_code': 'collaboration',
                    'relationship_type': 'collaborator',
                    'strength': 2  # Collaborations are moderately strong
                })
    
    # Third pass: identify shared contexts
    print("Finding shared contexts...")
    context_index = defaultdict(lambda: defaultdict(set))
    
    # Build index of who has what context
    for qid, person_data in person_data_cache.items():
        details = person_data.get("details", {})
        for prop_code, context_type in SHARED_CONTEXT_PROPERTIES.items():
            if prop_code in details:
                for item in details[prop_code]:
                    context_qid = item['qid']
                    context_label = item.get('label', '')
                    context_index[prop_code][context_qid].add((qid, context_label))
    
    # Find people who share contexts
    for prop_code, contexts in tqdm(context_index.items(), desc="Shared contexts"):
        context_type = SHARED_CONTEXT_PROPERTIES[prop_code]
        for context_qid, people_set in contexts.items():
            people_list = list(people_set)
            if len(people_list) < 2:
                continue
            
            # Create relationships between all people who share this context
            for i, (person1_qid, context_label) in enumerate(people_list):
                for person2_qid, _ in people_list[i+1:]:
                    shared_contexts[person1_qid][person2_qid].append({
                        'context_type': context_type,
                        'context_qid': context_qid,
                        'context_label': context_label,
                        'property_code': prop_code
                    })
                    # Add reverse too
                    shared_contexts[person2_qid][person1_qid].append({
                        'context_type': context_type,
                        'context_qid': context_qid,
                        'context_label': context_label,
                        'property_code': prop_code
                    })
    
    return dict(direct_relationships), dict(shared_contexts)

# --- Main Logic ---
def main():
    """Populates databases with comprehensive relationship data."""
    chroma_client, narrative_collection = setup_databases()
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    model = SentenceTransformer(MODEL_NAME)

    manifest_path = os.path.join(RAW_DATA_DIR, "_manifest.json")
    if not os.path.exists(manifest_path):
        print("Error: Manifest file not found. Please run create_manifest.py first.")
        return

    with open(manifest_path, 'r', encoding='utf-8') as f:
        person_list = json.load(f)

    print(f"Processing {len(person_list)} persons from the manifest.")
    
    # Build comprehensive relationships
    direct_rels, shared_contexts = build_comprehensive_relationships(person_list, RAW_DATA_DIR)
    
    print(f"\nRelationship Statistics:")
    print(f"  Persons with direct relationships: {len(direct_rels)}")
    print(f"  Persons with shared contexts: {len(shared_contexts)}")
    
    total_direct = sum(len(rels) for rels in direct_rels.values())
    total_shared = sum(sum(len(contexts) for contexts in person_contexts.values()) 
                      for person_contexts in shared_contexts.values())
    print(f"  Total direct relationships: {total_direct}")
    print(f"  Total shared contexts: {total_shared}")

    # Process each person
    cursor = sqlite_conn.cursor()
    
    for person_manifest in tqdm(person_list, desc="Populating databases"):
        qid = person_manifest['qid']
        json_path = os.path.join(RAW_DATA_DIR, f"{qid}.json")

        if not os.path.exists(json_path):
            continue

        with open(json_path, 'r', encoding='utf-8') as f:
            person_data = json.load(f)

        # Check if person already exists
        if cursor.execute("SELECT 1 FROM persons WHERE qid=?", (qid,)).fetchone():
            continue

        # Extract data
        summary = person_data.get("narrative_summary", "")
        details = person_data.get("details", {})
        birth_year = extract_birth_year(person_manifest.get('birth_date', ''))
        occupations = details.get('P106', [])
        primary_occupation = occupations[0]['label'] if occupations else None
        narrative_vector = model.encode(summary).tolist() if summary else []

        # Insert person
        cursor.execute(
            "INSERT OR IGNORE INTO persons (qid, label, thwiki_title, birth_year, occupation_primary) VALUES (?, ?, ?, ?, ?)",
            (qid, person_data['label'], person_data['thwiki_title'], birth_year, primary_occupation)
        )

        # Insert properties
        for prop_type, prop_list in [('factual', FACTUAL_PROPERTIES), ('relational', RELATIONAL_PROPERTIES)]:
            for prop_code in prop_list:
                if prop_code in details:
                    for item in details[prop_code]:
                        cursor.execute(
                            "INSERT OR IGNORE INTO person_properties (person_qid, property_qid, property_code, type, label) VALUES (?, ?, ?, ?, ?)",
                            (qid, item['qid'], prop_code, prop_type, item.get('label', ''))
                        )

        # Insert direct relationships
        if qid in direct_rels:
            for rel in direct_rels[qid]:
                cursor.execute(
                    "INSERT OR IGNORE INTO person_relationships (person1_qid, person2_qid, relationship_type, property_code, strength) VALUES (?, ?, ?, ?, ?)",
                    (qid, rel['person2_qid'], rel['relationship_type'], rel['property_code'], rel['strength'])
                )

        # Insert shared contexts
        if qid in shared_contexts:
            for person2_qid, contexts in shared_contexts[qid].items():
                for context in contexts:
                    cursor.execute(
                        "INSERT OR IGNORE INTO shared_contexts (person1_qid, person2_qid, context_type, context_qid, context_label, property_code) VALUES (?, ?, ?, ?, ?, ?)",
                        (qid, person2_qid, context['context_type'], context['context_qid'], context['context_label'], context['property_code'])
                    )

        # Add to ChromaDB
        if narrative_vector:
            num_direct_rels = len(direct_rels.get(qid, []))
            num_shared_contexts = sum(len(contexts) for contexts in shared_contexts.get(qid, {}).values())
            
            metadata = {
                'label': person_data['label'],
                'birth_year': birth_year or 0,
                'occupation': primary_occupation or '',
                'num_direct_relationships': num_direct_rels,
                'num_shared_contexts': num_shared_contexts
            }
            
            narrative_collection.add(
                embeddings=[narrative_vector],
                ids=[qid],
                metadatas=[metadata]
            )

        sqlite_conn.commit()

    # Display final statistics
    total_persons = cursor.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
    total_properties = cursor.execute("SELECT COUNT(*) FROM person_properties").fetchone()[0]
    total_direct_rels = cursor.execute("SELECT COUNT(*) FROM person_relationships").fetchone()[0]
    total_shared = cursor.execute("SELECT COUNT(*) FROM shared_contexts").fetchone()[0]
    
    print(f"\n{'='*60}")
    print(f"DATABASE POPULATION COMPLETE!")
    print(f"{'='*60}")
    print(f"Total persons: {total_persons}")
    print(f"Total properties: {total_properties}")
    print(f"Total direct relationships: {total_direct_rels}")
    print(f"Total shared contexts: {total_shared}")
    
    # Coverage statistics
    persons_with_direct = cursor.execute(
        "SELECT COUNT(DISTINCT person1_qid) FROM person_relationships"
    ).fetchone()[0]
    persons_with_shared = cursor.execute(
        "SELECT COUNT(DISTINCT person1_qid) FROM shared_contexts"
    ).fetchone()[0]
    
    print(f"\nCoverage:")
    print(f"  Persons with direct relationships: {persons_with_direct} ({100*persons_with_direct/total_persons:.1f}%)")
    print(f"  Persons with shared contexts: {persons_with_shared} ({100*persons_with_shared/total_persons:.1f}%)")
    
    # Sample relationships
    print(f"\n{'='*60}")
    print("Sample Direct Relationships:")
    print(f"{'='*60}")
    sample_direct = cursor.execute("""
        SELECT p1.label, p2.label, r.relationship_type, r.property_code, r.strength
        FROM person_relationships r
        JOIN persons p1 ON r.person1_qid = p1.qid
        JOIN persons p2 ON r.person2_qid = p2.qid
        ORDER BY r.strength DESC
        LIMIT 10
    """).fetchall()
    
    for rel in sample_direct:
        print(f"  {rel[0]} ← [{rel[2]}] → {rel[1]} (strength: {rel[4]})")
    
    print(f"\n{'='*60}")
    print("Sample Shared Contexts:")
    print(f"{'='*60}")
    sample_shared = cursor.execute("""
        SELECT p1.label, p2.label, s.context_type, s.context_label
        FROM shared_contexts s
        JOIN persons p1 ON s.person1_qid = p1.qid
        JOIN persons p2 ON s.person2_qid = p2.qid
        LIMIT 10
    """).fetchall()
    
    for rel in sample_shared:
        print(f"  {rel[0]} & {rel[1]} → both {rel[2]}: {rel[3]}")
    
    # Top connected people
    print(f"\n{'='*60}")
    print("Top 10 Most Connected People:")
    print(f"{'='*60}")
    top_connected = cursor.execute("""
        SELECT 
            p.label,
            COUNT(DISTINCT r.person2_qid) as direct_connections,
            COUNT(DISTINCT s.person2_qid) as shared_connections
        FROM persons p
        LEFT JOIN person_relationships r ON p.qid = r.person1_qid
        LEFT JOIN shared_contexts s ON p.qid = s.person1_qid
        GROUP BY p.qid
        ORDER BY (direct_connections + shared_connections) DESC
        LIMIT 10
    """).fetchall()
    
    for i, person in enumerate(top_connected, 1):
        total_conn = person[1] + person[2]
        print(f"  {i}. {person[0]}: {total_conn} total ({person[1]} direct, {person[2]} shared)")

    sqlite_conn.close()

if __name__ == "__main__":
    main()