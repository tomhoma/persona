import requests
import time
import os
import json
import sys
from SPARQLWrapper import SPARQLWrapper, JSON
from tqdm import tqdm

# --- Configuration ---
WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
OUTPUT_DIR = "data/raw"
MANIFEST_PATH = os.path.join(OUTPUT_DIR, "_manifest.json")

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
    Micro-Task Mode for fetching individual person data.
    - Finds the first person in the manifest without a corresponding JSON file.
    - Fetches and saves data for ONLY that person.
    - Exits.
    """
    if not os.path.exists(MANIFEST_PATH):
        print("Error: Manifest file not found. Please create it first.")
        return

    with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
        person_list = json.load(f)

    # Find the first person to process
    person_to_process = None
    for person in person_list:
        output_path = os.path.join(OUTPUT_DIR, f"{person['qid']}.json")
        if not os.path.exists(output_path):
            person_to_process = person
            break

    if not person_to_process:
        print("All persons have been processed. Nothing to do.")
        return

    qid = person_to_process['qid']
    print(f"--- Processing Person: {person_to_process['label']} ({qid}) ---")

    user_agent = "PersonaGuessApp/1.0 (https://github.com/your-repo; your-email@example.com)"
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})
    sparql = SPARQLWrapper(WIKIDATA_SPARQL_URL, agent=user_agent)

    # Fetch data for this one person
    summary = get_wikipedia_summary(person_to_process['enwiki_title'], session)
    details = get_wikidata_details(qid, sparql)

    person_data = {
        "qid": qid,
        "label": person_to_process['label'],
        "enwiki_title": person_to_process['enwiki_title'],
        "narrative_summary": summary,
        "details": details,
    }

    # Save the file
    output_path = os.path.join(OUTPUT_DIR, f"{qid}.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(person_data, f, ensure_ascii=False, indent=2)

    print(f"Successfully fetched and saved data for {qid}.")
    print("--------------------------------------------------")

if __name__ == "__main__":
    main()