import requests
import time
import os
import json
import sys
from SPARQLWrapper import SPARQLWrapper, JSON
from tqdm import tqdm

# --- Configuration ---
WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
WIKIPEDIA_API_URL = "https://th.wikipedia.org/w/api.php"  # Thai Wikipedia
OUTPUT_DIR = "data/raw"
MANIFEST_PATH = os.path.join(OUTPUT_DIR, "_manifest.json")
USER_AGENT = "PersonaGuessApp/1.0"

# Comprehensive property list for Thai celebrities
PROPERTIES_TO_FETCH = [
    # Personal Info
    "P21",   # sex or gender
    "P19",   # place of birth
    "P20",   # place of death
    "P569",  # date of birth
    "P570",  # date of death
    "P172",  # ethnic group
    "P1412", # languages spoken
    
    # Family
    "P22",   # father
    "P25",   # mother
    "P40",   # child
    "P26",   # spouse
    "P3373", # sibling
    "P1038", # relative
    "P451",  # partner
    
    # Career & Profession
    "P106",  # occupation
    "P108",  # employer
    "P39",   # position held
    "P463",  # member of
    "P102",  # member of political party
    "P54",   # member of sports team
    "P1327", # partner in business/sport
    
    # Education
    "P69",   # educated at
    "P512",  # academic degree
    "P184",  # doctoral advisor
    "P185",  # doctoral student
    "P1066", # student of
    "P802",  # student
    
    # Creative Work
    "P800",  # notable work
    "P1344", # participant in
    "P175",  # performer
    "P161",  # cast member
    "P57",   # director
    "P86",   # composer
    "P170",  # creator
    "P50",   # author
    "P112",  # founded by
    
    # Influence
    "P737",  # influenced by
    "P738",  # influence of
    
    # Recognition
    "P166",  # award received
    "P1411", # nominated for
    
    # Location
    "P551",  # residence
    "P937",  # work location
    "P27",   # country of citizenship
    
    # Other
    "P140",  # religion
    "P793",  # significant event
    "P710",  # participant
]

def get_wikipedia_summary(page_title, session):
    """Fetches the introductory summary of a Wikipedia page."""
    params = {
        "action": "query",
        "format": "json",
        "titles": page_title,
        "prop": "extracts",
        "exintro": True,
        "explaintext": True,
        "redirects": 1,
    }
    try:
        response = session.get(WIKIPEDIA_API_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        pages = data["query"]["pages"]
        for page_id in pages:
            if page_id != "-1":
                return pages[page_id].get("extract", "")
    except requests.exceptions.RequestException as e:
        print(f"  - Warning: Could not fetch Wikipedia summary for '{page_title}'. Error: {e}")
    return ""

def get_wikidata_details_enhanced(qid, sparql):
    """Fetches comprehensive relational data from Wikidata including reverse relationships."""
    prop_str = " ".join([f"wdt:{p}" for p in PROPERTIES_TO_FETCH])
    
    # Query for outgoing properties (this person -> others)
    query_outgoing = f"""
    SELECT ?prop ?value ?valueLabel WHERE {{
      VALUES ?item {{ wd:{qid} }}
      VALUES ?prop {{ {prop_str} }}
      ?item ?prop ?value.
      FILTER(isIRI(?value))
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "th,en". }}
    }}
    """
    
    # Query for incoming relationships (others -> this person)
    # Focus on key reverse relationships
    query_incoming = f"""
    SELECT ?prop ?subject ?subjectLabel WHERE {{
      VALUES ?object {{ wd:{qid} }}
      VALUES ?prop {{ wdt:P40 wdt:P26 wdt:P22 wdt:P25 wdt:P802 wdt:P185 wdt:P738 wdt:P161 wdt:P175 wdt:P50 wdt:P86 wdt:P57 }}
      ?subject ?prop ?object.
      ?subject wdt:P31 wd:Q5.  # Must be human
      FILTER(isIRI(?subject))
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "th,en". }}
    }}
    LIMIT 100
    """
    
    details = {}
    reverse_relationships = []
    
    try:
        # Get outgoing relationships
        sparql.setQuery(query_outgoing)
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()["results"]["bindings"]
        
        for r in results:
            prop_code = r['prop']['value'].split('/')[-1]
            value_qid = r['value']['value'].split('/')[-1]
            value_label = r.get('valueLabel', {}).get('value', '')
            
            if prop_code not in details:
                details[prop_code] = []
            
            if not any(d['qid'] == value_qid for d in details[prop_code]):
                details[prop_code].append({
                    "qid": value_qid,
                    "label": value_label
                })
        
        # Get incoming relationships
        sparql.setQuery(query_incoming)
        results_incoming = sparql.query().convert()["results"]["bindings"]
        
        for r in results_incoming:
            prop_code = r['prop']['value'].split('/')[-1]
            subject_qid = r['subject']['value'].split('/')[-1]
            subject_label = r.get('subjectLabel', {}).get('value', '')
            
            reverse_relationships.append({
                "property": prop_code,
                "subject_qid": subject_qid,
                "subject_label": subject_label,
                "direction": "incoming"
            })
        
    except Exception as e:
        print(f"  - Warning: Could not fetch Wikidata details for {qid}. Error: {e}")
    
    return details, reverse_relationships

def get_collaborations(qid, sparql):
    """Find people who worked together on the same projects/films/events."""
    query = f"""
    SELECT DISTINCT ?person ?personLabel ?work ?workLabel ?role WHERE {{
      # Find works/events this person participated in
      wd:{qid} (wdt:P1344|wdt:P161|wdt:P175|wdt:P800) ?work.
      
      # Find other people in same work
      ?person (wdt:P1344|wdt:P161|wdt:P175|wdt:P800) ?work.
      ?person wdt:P31 wd:Q5.  # Must be human
      
      # Don't include self
      FILTER(?person != wd:{qid})
      
      # Optional: their role
      OPTIONAL {{ ?person wdt:P106 ?role }}
      
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "th,en". }}
    }}
    LIMIT 50
    """
    
    collaborations = []
    try:
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()["results"]["bindings"]
        
        for r in results:
            collaborations.append({
                "person_qid": r['person']['value'].split('/')[-1],
                "person_label": r.get('personLabel', {}).get('value', ''),
                "work_qid": r['work']['value'].split('/')[-1],
                "work_label": r.get('workLabel', {}).get('value', '')
            })
    except:
        pass
    
    return collaborations

def main():
    """
    Enhanced data fetching with bidirectional relationships and collaborations.
    """
    if not os.path.exists(MANIFEST_PATH):
        print("Error: Manifest file not found. Please run create_manifest.py first.")
        return

    with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
        person_list = json.load(f)

    # Setup network clients
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    sparql = SPARQLWrapper(WIKIDATA_SPARQL_URL, agent=USER_AGENT)

    print(f"Found {len(person_list)} persons in the manifest.")
    
    # Track statistics
    total_relationships = 0
    total_reverse_relationships = 0
    total_collaborations = 0

    for person in tqdm(person_list, desc="Fetching enhanced person data"):
        qid = person['qid']
        output_path = os.path.join(OUTPUT_DIR, f"{qid}.json")

        # Skip if already processed (delete file to reprocess)
        if os.path.exists(output_path):
            continue

        # Fetch all data
        summary = get_wikipedia_summary(person['thwiki_title'], session)
        details, reverse_rels = get_wikidata_details_enhanced(qid, sparql)
        collaborations = get_collaborations(qid, sparql)
        
        # Count relationships
        rel_count = sum(len(items) for items in details.values())
        total_relationships += rel_count
        total_reverse_relationships += len(reverse_rels)
        total_collaborations += len(collaborations)

        person_data = {
            "qid": qid,
            "label": person['label'],
            "thwiki_title": person['thwiki_title'],
            "birth_date": person.get('birth_date', ''),
            "image": person.get('image', ''),
            "narrative_summary": summary,
            "details": details,
            "reverse_relationships": reverse_rels,
            "collaborations": collaborations,
            "stats": {
                "num_properties": len(details),
                "num_relationships": rel_count,
                "num_reverse_relationships": len(reverse_rels),
                "num_collaborations": len(collaborations)
            }
        }

        # Save the file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(person_data, f, ensure_ascii=False, indent=2)

        # Progress indicator
        if len(person_list) > 50 and person_list.index(person) % 50 == 0:
            tqdm.write(f"  Progress: {person['label']} - {rel_count} relationships, {len(collaborations)} collaborations")

        time.sleep(0.5)  # Be polite to APIs

    print(f"\n✅ Data fetching complete!")
    print(f"   Total relationships found: {total_relationships}")
    print(f"   Total reverse relationships: {total_reverse_relationships}")  
    print(f"   Total collaborations: {total_collaborations}")
    print(f"   Average relationships per person: {total_relationships / len(person_list):.1f}")

if __name__ == "__main__":
    main()