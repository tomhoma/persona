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

# --- Helper Functions (from previous steps) ---

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

def get_wikidata_details(qid, sparql):
    """Fetches factual and relational data from Wikidata for a given person."""
    properties = ["P106", "P27", "P166", "P737", "P1066", "P800"]
    prop_str = " ".join([f"wdt:{p}" for p in properties])

    query = f"""
    SELECT ?prop ?value ?valueLabel WHERE {{
      VALUES ?item {{ wd:{qid} }}
      VALUES ?prop {{ {prop_str} }}
      ?item ?prop ?value.
      FILTER(isIRI(?value))
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    """

    try:
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()["results"]["bindings"]

        details = {}
        for r in results:
            prop_code = r['prop']['value'].split('/')[-1]
            value_qid = r['value']['value'].split('/')[-1]
            value_label = r.get('valueLabel', {}).get('value', '')

            if prop_code not in details:
                details[prop_code] = []

            if not any(d['qid'] == value_qid for d in details[prop_code]):
                details[prop_code].append({"qid": value_qid, "label": value_label})
        return details
    except Exception as e:
        print(f"  - Warning: Could not fetch Wikidata details for {qid}. Error: {e}")
        return {}

def main():
    """
    Fetches data for each person in the manifest who hasn't been processed yet.
    - Reads the manifest file.
    - For each person, checks if a corresponding JSON file exists.
    - If not, fetches Wikipedia summary and Wikidata details.
    - Saves the data to a new JSON file.
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

    for person in tqdm(person_list, desc="Fetching person data"):
        qid = person['qid']
        output_path = os.path.join(OUTPUT_DIR, f"{qid}.json")

        if os.path.exists(output_path):
            continue

        # Fetch data for this person
        summary = get_wikipedia_summary(person['thwiki_title'], session)
        details = get_wikidata_details(qid, sparql)

        person_data = {
            "qid": qid,
            "label": person['label'],
            "thwiki_title": person['thwiki_title'],
            "narrative_summary": summary,
            "details": details,
        }

        # Save the file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(person_data, f, ensure_ascii=False, indent=2)

        time.sleep(1) # Be polite to the APIs

    print("Data fetching complete.")


if __name__ == "__main__":
    main()
