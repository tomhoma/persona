import os
import json
from SPARQLWrapper import SPARQLWrapper, JSON
from tqdm import tqdm

# Configuration
WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
OUTPUT_DIR = "data/raw"
MANIFEST_PATH = os.path.join(OUTPUT_DIR, "_manifest.json")
USER_AGENT = "PersonaGuessApp/1.0"
# You can still use occupations to get a diverse set of people from that country
# Arts & Entertainment: Politician, Actor, Singer, Writer, Musician, Film Director, Painter, Comedian, Dancer, Photographer
# Science & Academia: Scientist, Physicist, Chemist, Biologist, Philosopher, Historian, Mathematician
# Sports: Athlete
SEED_OCCUPATIONS = ["Q82955", "Q33999", "Q177220", "Q36180", "Q639669", "Q2526255", "Q1028181", "Q245068", "Q5716684", "Q33231", "Q901", "Q169470", "Q593644", "Q864503", "Q4964182", "Q201788", "Q170790", "Q2066131"]
LIMIT_PER_OCCUPATION = 500
MIN_SITELINKS = 5 # Lowering this may be necessary for smaller countries

# --- Country Filter ---
# Set the Wikidata QID for the country you want to filter by.
# Q869 is for Thailand. You can find others on Wikidata.
COUNTRY_QID = "Q869" 

def test_connection(sparql):
    """Tests connection to Wikidata SPARQL endpoint."""
    print("🔌 Testing connection to Wikidata SPARQL endpoint...")
    test_query = """
    SELECT ?item WHERE {
      ?item wdt:P31 wd:Q5.
    }
    LIMIT 1
    """
    try:
        sparql.setQuery(test_query)
        sparql.setReturnFormat(JSON)
        sparql.query().convert()
        print("✅ Connection successful!\n")
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("Please check your internet connection and try again.\n")
        return False

def fetch_persons_for_occupation(occupation_qid, sparql):
    """Fetches persons from Wikidata for a single occupation from a specific country."""
    
    query = f"""
    SELECT DISTINCT ?item ?itemLabel ?itemDescription ?birthDate ?thwiki_title ?image WHERE {{
      ?item wdt:P31 wd:Q5;                    # Instance of human
            wdt:P27 wd:{COUNTRY_QID};         # Country of citizenship
            wdt:P106/wdt:P279* wd:{occupation_qid}.  # Occupation
      
      # Must have Thai Wikipedia article
      ?thwiki_title schema:about ?item;
                    schema:isPartOf <https://th.wikipedia.org/>;
                    schema:name ?thwiki_title.
      
      # Optional: birth date and image
      OPTIONAL {{ ?item wdt:P569 ?birthDate. }}
      OPTIONAL {{ ?item wdt:P18 ?image. }}
      
      # Prefer people born from 1940 onwards (if birth date exists)
      FILTER(!BOUND(?birthDate) || ?birthDate >= "1940-01-01T00:00:00Z"^^xsd:dateTime)
      
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "th,en". }}
    }}
    ORDER BY DESC(?birthDate)
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
                "description": r.get("itemDescription", {}).get("value", ""),
                "birth_date": r.get("birthDate", {}).get("value", ""),
                "thwiki_title": r["thwiki_title"]["value"],
                "image": r.get("image", {}).get("value", "")
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
    
    # Test connection before proceeding
    if not test_connection(sparql):
        print("Exiting due to connection failure.")
        return
    
    all_persons = {}
    print(f"🔍 Fetching persons from country: {COUNTRY_QID}")
    print(f"📊 Processing {len(SEED_OCCUPATIONS)} occupation types")
    print(f"🎯 Limit per occupation: {LIMIT_PER_OCCUPATION}\n")
    
    for i, occupation_qid in enumerate(tqdm(SEED_OCCUPATIONS, desc="Progress"), 1):
        persons = fetch_persons_for_occupation(occupation_qid, sparql)
        new_persons = 0
        for person in persons:
            if person['qid'] not in all_persons:
                all_persons[person['qid']] = person
                new_persons += 1
        
        tqdm.write(f"  ✓ {occupation_qid}: Found {len(persons)} persons ({new_persons} new, {len(persons)-new_persons} duplicates)")
    
    person_list = list(all_persons.values())
    print(f"\n✅ Total unique persons collected: {len(person_list)}")
    
    # Delete old data if it exists to ensure a clean slate
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
            old_manifest = json.load(f)
        for person in old_manifest:
            old_file = os.path.join(OUTPUT_DIR, f"{person['qid']}.json")
            if os.path.exists(old_file):
                os.remove(old_file)

    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(person_list, f, ensure_ascii=False, indent=2)
        
    print(f"Manifest created with {len(person_list)} unique persons at: {MANIFEST_PATH}")
    print("You should now run fetch_data.py and populate_databases.py again.")

if __name__ == "__main__":
    main()