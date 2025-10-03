import sys, os, json, time, requests, sqlite3, chromadb, numpy as np
from SPARQLWrapper import SPARQLWrapper, JSON
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import logging

DB_DIR = "data"
SQLITE_PATH = os.path.join(DB_DIR, "persona.db")
CHROMA_PATH = os.path.join(DB_DIR, "chroma")
WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
MODEL_NAME = 'all-MiniLM-L6-v2'
USER_AGENT = "PersonaGuessApp/1.0"
FACTUAL_PROPERTIES = ["P106", "P27", "P166"]
RELATIONAL_PROPERTIES = ["P737", "P1066", "P800"]
SEED_OCCUPATIONS = ["Q82955", "Q483501", "Q901", "Q36180", "Q33999", "Q2066131", "Q18814623", "Q177220", "Q49757", "Q169470"]
LIMIT_PER_OCCUPATION = 30
MIN_SITELINKS = 25

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def setup_databases():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS persons (qid TEXT PRIMARY KEY, label TEXT, enwiki_title TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS person_properties (person_qid TEXT, property_qid TEXT, type TEXT, PRIMARY KEY (person_qid, property_qid))")
    conn.commit()
    conn.close()
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(name="narrative_vectors")
    logging.info("Databases initialized.")
    return client, collection

def fetch_single_occupation(occupation_qid, sparql):
    query = f"SELECT ?item ?itemLabel ?enwiki_title WHERE {{ SERVICE wikibase:label {{ bd:serviceParam wikibase:language \"en\". }} ?item wdt:P106/wdt:P279* wd:{occupation_qid}. ?item wikibase:sitelinks ?sitelinkCount. ?enwiki schema:about ?item; schema:isPartOf <https://en.wikipedia.org/>; schema:name ?enwiki_title. FILTER(?sitelinkCount > {MIN_SITELINKS}) }} LIMIT {LIMIT_PER_OCCUPATION}"
    try:
        sparql.setQuery(query); sparql.setReturnFormat(JSON)
        results = sparql.query().convert()["results"]["bindings"]
        return [{"qid": r["item"]["value"].split("/")[-1], "label": r["itemLabel"]["value"], "enwiki_title": r["enwiki_title"]["value"]} for r in results]
    except Exception as e:
        logging.error(f"Failed to fetch {occupation_qid}: {e}"); return []

def get_wikipedia_summary(title, session):
    params = {"action":"query", "format":"json", "titles":title, "prop":"extracts", "exintro":True, "explaintext":True, "redirects":1}
    try:
        r = session.get(WIKIPEDIA_API_URL, params=params, timeout=15); r.raise_for_status(); pages = r.json()["query"]["pages"]
        return next((pages[p].get("extract", "") for p in pages if p != "-1"), "")
    except Exception: return ""

def get_wikidata_details(qid, sparql):
    prop_str = " ".join([f"wdt:{p}" for p in FACTUAL_PROPERTIES + RELATIONAL_PROPERTIES])
    query = f"SELECT ?prop ?value WHERE {{ VALUES ?item {{wd:{qid}}} VALUES ?prop {{ {prop_str} }} ?item ?prop ?value. FILTER(isIRI(?value)) }}"
    try:
        sparql.setQuery(query); sparql.setReturnFormat(JSON)
        results = sparql.query().convert()["results"]["bindings"]
        details = {}
        for r in results:
            prop, val_qid = r['prop']['value'].split('/')[-1], r['value']['value'].split('/')[-1]
            if prop not in details: details[prop] = []
            if val_qid not in details[prop]: details[prop].append(val_qid)
        return details
    except Exception: return {}

def main(job_index):
    chroma_client, narrative_collection = setup_databases()
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    model = SentenceTransformer(MODEL_NAME)
    sparql = SPARQLWrapper(WIKIDATA_SPARQL_URL, agent=USER_AGENT)
    session = requests.Session(); session.headers.update({"User-Agent": USER_AGENT})
    occupation_qid = SEED_OCCUPATIONS[job_index]
    logging.info(f"Processing occupation {job_index+1}/{len(SEED_OCCUPATIONS)}: {occupation_qid}")
    persons = fetch_single_occupation(occupation_qid, sparql)
    if not persons: return
    for person in tqdm(persons, desc=f"Processing {occupation_qid}"):
        qid = person['qid']
        if sqlite_conn.execute("SELECT 1 FROM persons WHERE qid=?", (qid,)).fetchone(): continue
        summary = get_wikipedia_summary(person['enwiki_title'], session)
        details = get_wikidata_details(qid, sparql)
        narrative_vector = model.encode(summary).tolist() if summary else []
        factual_qids = {qid for p in FACTUAL_PROPERTIES if p in details for qid in details[p]}
        relational_qids = {qid for p in RELATIONAL_PROPERTIES if p in details for qid in details[p]}
        cursor = sqlite_conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO persons (qid, label, enwiki_title) VALUES (?, ?, ?)", (qid, person['label'], person['enwiki_title']))
        prop_data = [(qid, pq, 'factual') for pq in factual_qids] + [(qid, pq, 'relational') for pq in relational_qids]
        cursor.executemany("INSERT OR IGNORE INTO person_properties (person_qid, property_qid, type) VALUES (?, ?, ?)", prop_data)
        if narrative_vector:
            narrative_collection.add(embeddings=[narrative_vector], ids=[qid])
        sqlite_conn.commit()
        time.sleep(1)
    sqlite_conn.close()
    logging.info("Batch complete.")

if __name__ == "__main__":
    main(int(sys.argv[1]))
