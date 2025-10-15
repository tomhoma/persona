import os
import json
from SPARQLWrapper import SPARQLWrapper, JSON
from tqdm import tqdm

# Configuration
WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
OUTPUT_DIR = "data/raw"
MANIFEST_PATH = os.path.join(OUTPUT_DIR, "_manifest.json")
USER_AGENT = "PersonaGuessApp/1.0"
SEED_OCCUPATIONS = ["Q82955", "Q483501", "Q901", "Q36180", "Q33999", "Q2066131", "Q18814623", "Q177220", "Q49757", "Q169470"]
LIMIT_PER_OCCUPATION = 30
MIN_SITELINKS = 25

def fetch_persons_for_occupation(occupation_qid, sparql):
    """Fetches persons from Wikidata for a single occupation."""
    query = f"""
    SELECT ?item ?itemLabel ?enwiki_title WHERE {{
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
      ?item wdt:P106/wdt:P279* wd:{occupation_qid}.
      ?item wikibase:sitelinks ?sitelinkCount.
      ?enwiki schema:about ?item;
              schema:isPartOf <https://en.wikipedia.org/>;
              schema:name ?enwiki_title.
      FILTER(?sitelinkCount > {MIN_SITELINKS})
    }}
    LIMIT {LIMIT_PER_OCCUPATION}
    """
    try:
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()["results"]["bindings"]
        return [
            {
                "qid": r["item"]["value"].split("/")[-1],
                "label": r["itemLabel"]["value"],
                "enwiki_title": r["enwiki_title"]["value"]
            }
            for r in results
        ]
    except Exception as e:
        print(f"Warning: Could not fetch data for occupation {occupation_qid}. Error: {e}")
        return []

def main():
    """Fetches a list of notable persons from Wikidata and creates a manifest file."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    sparql = SPARQLWrapper(WIKIDATA_SPARQL_URL, agent=USER_AGENT)

    all_persons = {}
    for occupation_qid in tqdm(SEED_OCCUPATIONS, desc="Fetching persons by occupation"):
        persons = fetch_persons_for_occupation(occupation_qid, sparql)
        for person in persons:
            if person['qid'] not in all_persons:
                all_persons[person['qid']] = person

    person_list = list(all_persons.values())

    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(person_list, f, ensure_ascii=False, indent=2)

    print(f"Manifest created with {len(person_list)} unique persons at: {MANIFEST_PATH}")

if __name__ == "__main__":
    main()
