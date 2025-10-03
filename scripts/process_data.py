import sys
import os
import json
import time
import requests
import sqlite3
import chromadb
import numpy as np
from SPARQLWrapper import SPARQLWrapper, JSON
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import logging

# --- Configuration ---
DB_DIR = "data"
SQLITE_PATH = os.path.join(DB_DIR, "persona.db")
CHROMA_PATH = os.path.join(DB_DIR, "chroma")
WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
MODEL_NAME = 'all-MiniLM-L6-v2'
USER_AGENT = "PersonaGuessApp/1.0 (https://github.com/your-repo; your-email@example.com)"

# --- Properties ---
FACTUAL_PROPERTIES = ["P106", "P27", "P166"]
RELATIONAL_PROPERTIES = ["P737", "P1066", "P800"]

# --- Occupations to Seed ---
SEED_OCCUPATIONS = [
    "Q82955", "Q483501", "Q901", "Q36180", "Q33999", "Q2066131",
    "Q18814623", "Q177220", "Q49757", "Q169470",
]
LIMIT_PER_OCCUPATION = 50 # Reduced for better performance per run
MIN_SITELINKS = 25

# --- Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
os.makedirs(DB_DIR, exist_ok=True)

def setup_databases():
    """Initializes SQLite tables and ChromaDB collections if they don't exist."""
    # SQLite
    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS persons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        qid TEXT NOT NULL UNIQUE,
        label TEXT NOT NULL,
        enwiki_title TEXT
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS person_properties (
        person_qid TEXT NOT NULL,
        property_qid TEXT NOT NULL,
        type TEXT NOT NULL, -- 'factual' or 'relational'
        PRIMARY KEY (person_qid, property_qid)
    )""")
    conn.commit()
    conn.close()

    # ChromaDB
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    client.get_or_create_collection(name="narrative_vectors")
    logging.info("Databases initialized successfully.")
    return client

def fetch_single_occupation(occupation_qid, sparql):
    """Fetches a list of persons for a single occupation."""
    query = f"""
    SELECT ?item ?itemLabel ?enwiki_title WHERE {{
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
      ?item wdt:P106/wdt:P279* wd:{occupation_qid}.
      ?item wikibase:sitelinks ?sitelinkCount.
      ?enwiki schema:about ?item; schema:isPartOf <https://en.wikipedia.org/>; schema:name ?enwiki_title.
      FILTER(?sitelinkCount > {MIN_SITELINKS})
    }} LIMIT {LIMIT_PER_OCCUPATION}
    """
    try:
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()["results"]["bindings"]
        return [{"qid": r["item"]["value"].split("/")[-1], "label": r["itemLabel"]["value"], "enwiki_title": r["enwiki_title"]["value"]} for r in results]
    except Exception as e:
        logging.error(f"Failed to fetch occupation {occupation_qid}: {e}")
        return []

def get_wikipedia_summary(page_title, session):
    params = {"action": "query", "format": "json", "titles": page_title, "prop": "extracts", "exintro": True, "explaintext": True, "redirects": 1}
    try:
        r = session.get(WIKIPEDIA_API_URL, params=params, timeout=10)
        r.raise_for_status()
        pages = r.json()["query"]["pages"]
        return next((pages[p].get("extract", "") for p in pages if p != "-1"), "")
    except Exception:
        return ""

def get_wikidata_details(qid, sparql):
    prop_str = " ".join([f"wdt:{p}" for p in FACTUAL_PROPERTIES + RELATIONAL_PROPERTIES])
    query = f"SELECT ?prop ?value WHERE {{ VALUES ?item {{wd:{qid}}} VALUES ?prop {{ {prop_str} }} ?item ?prop ?value. FILTER(isIRI(?value)) }}"
    try:
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()["results"]["bindings"]
        details = {}
        for r in results:
            prop = r['prop']['value'].split('/')[-1]
            val_qid = r['value']['value'].split('/')[-1]
            if prop not in details: details[prop] = []
            if val_qid not in details[prop]: details[prop].append(val_qid)
        return details
    except Exception:
        return {}

def insert_data(person_data, conn, chroma_collection):
    """Inserts a fully processed person's data into the databases."""
    cursor = conn.cursor()
    qid = person_data['qid']

    # Insert metadata
    cursor.execute("INSERT OR IGNORE INTO persons (qid, label, enwiki_title) VALUES (?, ?, ?)",
                   (qid, person_data['label'], person_data['enwiki_title']))

    # Insert properties
    prop_data = []
    for prop_qid in person_data['factual_qids']:
        prop_data.append((qid, prop_qid, 'factual'))
    for prop_qid in person_data['relational_qids']:
        prop_data.append((qid, prop_qid, 'relational'))
    cursor.executemany("INSERT OR IGNORE INTO person_properties (person_qid, property_qid, type) VALUES (?, ?, ?)", prop_data)

    # Insert narrative vector
    if person_data['narrative_vector']:
        chroma_collection.add(
            embeddings=[person_data['narrative_vector']],
            ids=[qid]
        )
    conn.commit()

def main(job_index):
    """Main processing loop for a single occupation index."""
    # --- Setup ---
    chroma_client = setup_databases()
    narrative_collection = chroma_client.get_collection(name="narrative_vectors")
    sqlite_conn = sqlite3.connect(SQLITE_PATH)

    model = SentenceTransformer(MODEL_NAME)
    sparql = SPARQLWrapper(WIKIDATA_SPARQL_URL, agent=USER_AGENT)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    # --- Fetch persons for the given occupation ---
    occupation_qid = SEED_OCCUPATIONS[job_index]
    logging.info(f"Processing occupation {job_index+1}/{len(SEED_OCCUPATIONS)}: {occupation_qid}")
    persons_to_process = fetch_single_occupation(occupation_qid, sparql)

    if not persons_to_process:
        logging.warning("No persons found for this occupation. Exiting.")
        return

    # --- Process each person ---
    for person in tqdm(persons_to_process, desc=f"Processing {occupation_qid}"):
        qid = person['qid']

        # Check if already processed
        if narrative_collection.get(ids=[qid])['ids']:
            logging.info(f"Skipping {qid} as it already exists in the database.")
            continue

        # 1. Fetch details
        summary = get_wikipedia_summary(person['enwiki_title'], session)
        details = get_wikidata_details(qid, sparql)

        # 2. Generate vectors/QID sets
        narrative_vector = model.encode(summary).tolist() if summary else []
        factual_qids = {qid for prop in FACTUAL_PROPERTIES if prop in details for qid in details[prop]}
        relational_qids = {qid for prop in RELATIONAL_PROPERTIES if prop in details for qid in details[prop]}

        # 3. Prepare data object
        processed_data = {
            "qid": qid,
            "label": person['label'],
            "enwiki_title": person['enwiki_title'],
            "narrative_vector": narrative_vector,
            "factual_qids": list(factual_qids),
            "relational_qids": list(relational_qids),
        }

        # 4. Insert into databases
        insert_data(processed_data, sqlite_conn, narrative_collection)
        logging.info(f"Successfully processed and stored {qid} ({person['label']}).")
        time.sleep(1) # Be polite

    sqlite_conn.close()
    logging.info("Batch processing complete for this occupation.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <occupation_index_0_to_9>")
        sys.exit(1)
    try:
        job_index = int(sys.argv[1])
        if not (0 <= job_index < len(SEED_OCCUPATIONS)):
            raise ValueError()
        main(job_index)
    except (ValueError, IndexError):
        print(f"Invalid index. Please provide a number between 0 and {len(SEED_OCCUPATIONS) - 1}.")
        sys.exit(1)