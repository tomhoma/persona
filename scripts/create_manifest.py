import os
import json
from SPARQLWrapper import SPARQLWrapper, JSON
from tqdm import tqdm

# Configuration
WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
OUTPUT_DIR = "data/raw"
MANIFEST_PATH = os.path.join(OUTPUT_DIR, "_manifest.json")
USER_AGENT = "PersonaGuessApp/1.0"

# Expanded occupation list - targeting younger audience (15-35)
SEED_OCCUPATIONS = [
    # Entertainment & Pop Culture (most relevant for young audience)
    "Q33999",      # Actor/Actress
    "Q177220",     # Singer
    "Q488205",     # Singer-songwriter
    "Q10800557",   # Film actor
    "Q10798782",   # Television actor
    "Q2405480",    # Voice actor
    "Q4610556",    # Model (fashion)
    "Q2259451",    # Stage actor
    
    # Social Media & Modern Influencers
    "Q947873",     # Television presenter
    "Q1329383",    # News presenter (ผู้ประกาศข่าว)
    "Q2722764",    # YouTuber (ยูทูบเบอร์)
    "Q13590141",   # Influencer
    "Q7042855",    # Blogger
    
    # Music & Performance
    "Q639669",     # Musician
    "Q855091",     # Guitarist
    "Q36834",      # Composer
    "Q753110",     # Songwriter
    "Q130857",     # Rapper
    "Q5716684",    # Dancer
    "Q2643890",    # Choreographer
    "Q386854",     # Disc jockey (DJ)
    
    # Sports (popular among youth)
    "Q937857",     # Footballer
    "Q11513337",   # Association football player
    "Q10833314",   # Tennis player
    "Q10871364",   # Badminton player
    "Q14089670",   # Muay Thai fighter
    "Q10843402",   # Volleyball player
    "Q10843263",   # Basketball player
    "Q15117302",   # Esports player
    "Q2066131",    # Athlete (general)
    
    # Creative & Arts
    "Q2526255",    # Film director
    "Q3455803",    # Director
    "Q3286043",    # Producer
    "Q1414443",    # Screenwriter
    "Q1028181",    # Painter
    "Q33231",      # Photographer
    "Q15296811",   # Drawer/Illustrator
    "Q483501",     # Artist
    "Q266569",     # Graphic designer
    
    # Writers & Content Creators
    "Q36180",      # Writer
    "Q6625963",    # Novelist
    "Q15980158",   # Poet
    "Q214917",     # Playwright
    "Q1930187",    # Journalist
    
    # Business & Tech (modern careers)
    "Q131524",     # Entrepreneur
    "Q5322166",    # Designer
    "Q5716455",    # Fashion designer
    
    # Politicians (some for diversity, removed Monarch)
    "Q82955",      # Politician
    "Q372436",     # Statesman
    
    # Comedy & Entertainment
    "Q245068",     # Comedian (นักแสดงตลก)
    "Q2405480",    # Voice actor
]

LIMIT_PER_OCCUPATION = 500  # Reduced to get more variety
MIN_SITELINKS = 1   # Lowered to include more people
MIN_STATEMENTS = 9 # Lowered to include more people
COUNTRY_QID = "Q869"  # Thailand

# Birth year range to target younger, more relatable people
MIN_BIRTH_YEAR = 1940  # Include some older famous people for diversity
MAX_BIRTH_YEAR = 2020  # Include very young rising stars

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

def fetch_persons_for_occupation(occupation_qid, sparql, debug=False):
    """Fetches persons from Wikidata with quality filters and birth year range."""
    
    query = f"""
    SELECT DISTINCT ?item ?itemLabel ?itemDescription ?birthDate ?thwiki_title ?image 
           ?sitelinks ?statements WHERE {{
      ?item wdt:P31 wd:Q5;                    # Instance of human
            wdt:P27 wd:{COUNTRY_QID};         # Country of citizenship
            wdt:P106 wd:{occupation_qid};     # Occupation
            wikibase:sitelinks ?sitelinks;    # Number of Wikipedia articles
            wikibase:statements ?statements.  # Number of statements (data richness)
      
      # Must have Thai Wikipedia article
      ?thwiki schema:about ?item;
              schema:isPartOf <https://th.wikipedia.org/>;
              schema:name ?thwiki_title.
      
      # Quality filters
      FILTER(?sitelinks >= {MIN_SITELINKS})
      FILTER(?statements >= {MIN_STATEMENTS})
      
      # EXCLUDE MONARCHS AND ROYALTY - regardless of other occupations
      FILTER NOT EXISTS {{ ?item wdt:P106 wd:Q116. }}        # Not a Monarch
      FILTER NOT EXISTS {{ ?item wdt:P106 wd:Q10732476. }}   # Not a Head of State
      FILTER NOT EXISTS {{ ?item wdt:P39 wd:Q217903. }}      # Never held position: King of Thailand
      FILTER NOT EXISTS {{ ?item wdt:P39 wd:Q3847454. }}     # Never held position: Queen of Thailand
      FILTER NOT EXISTS {{ ?item wdt:P31 wd:Q10855449. }}    # Not instance of: Thai royalty
      
      # Birth date required and within range
      ?item wdt:P569 ?birthDate.
      FILTER(YEAR(?birthDate) >= {MIN_BIRTH_YEAR} && YEAR(?birthDate) <= {MAX_BIRTH_YEAR})
      
      # Optional: image
      OPTIONAL {{ ?item wdt:P18 ?image. }}
      
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "th,en". }}
    }}
    ORDER BY DESC(?sitelinks) DESC(?statements)
    LIMIT {LIMIT_PER_OCCUPATION}
    """
    
    if debug:
        print(f"\n🐛 DEBUG - Occupation: {occupation_qid}")
        print(f"Filters: sitelinks>={MIN_SITELINKS}, statements>={MIN_STATEMENTS}, birth: {MIN_BIRTH_YEAR}-{MAX_BIRTH_YEAR}")
        print(f"EXCLUDING: Monarchs, Royalty, Heads of State\n")
    
    try:
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        raw_results = sparql.query().convert()
        results = raw_results["results"]["bindings"]
        
        if debug and len(results) > 0:
            print(f"Found {len(results)} persons")
            birth_year = results[0].get('birthDate', {}).get('value', '')[:4] if 'birthDate' in results[0] else 'N/A'
            print(f"Top result: {results[0].get('itemLabel', {}).get('value', 'N/A')} "
                  f"(born: {birth_year}, sitelinks: {results[0].get('sitelinks', {}).get('value', 'N/A')})")
        
        parsed_results = [
            {
                "qid": r["item"]["value"].split("/")[-1],
                "label": r["itemLabel"]["value"],
                "description": r.get("itemDescription", {}).get("value", ""),
                "birth_date": r.get("birthDate", {}).get("value", ""),
                "birth_year": int(r["birthDate"]["value"][:4]) if "birthDate" in r else None,
                "thwiki_title": r["thwiki_title"]["value"],
                "image": r.get("image", {}).get("value", ""),
                "sitelinks": int(r["sitelinks"]["value"]),
                "statements": int(r["statements"]["value"])
            }
            for r in results
        ]
        
        return parsed_results
        
    except Exception as e:
        if debug:
            print(f"❌ ERROR: {e}\n")
        return []

def calculate_fame_score(person):
    """Calculate a fame score based on various metrics."""
    # Weight sitelinks more heavily (international recognition)
    # Weight statements moderately (data quality/completeness)
    fame_score = (person['sitelinks'] * 10) + (person['statements'] * 2)
    
    # Bonus for having an image (visual recognition)
    if person.get('image'):
        fame_score += 50
    
    return fame_score

def main():
    """Fetches a diverse list of Thai persons targeting younger audience (15-35)."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    sparql = SPARQLWrapper(WIKIDATA_SPARQL_URL, agent=USER_AGENT)
    
    if not test_connection(sparql):
        print("Exiting due to connection failure.")
        return
    
    all_persons = {}
    print(f"🇹🇭 Fetching Thai persons for YOUNGER AUDIENCE (ages 15-35)")
    print(f"📊 Quality filters: MIN_SITELINKS={MIN_SITELINKS}, MIN_STATEMENTS={MIN_STATEMENTS}")
    print(f"📅 Birth year range: {MIN_BIRTH_YEAR}-{MAX_BIRTH_YEAR}")
    print(f"🎯 Processing {len(SEED_OCCUPATIONS)} occupation types\n")
    
    for i, occupation_qid in enumerate(tqdm(SEED_OCCUPATIONS, desc="Progress"), 1):
        debug_mode = (i <= 3)
        persons = fetch_persons_for_occupation(occupation_qid, sparql, debug=debug_mode)
        new_persons = 0
        
        for person in persons:
            # Calculate fame score
            person['fame_score'] = calculate_fame_score(person)
            
            if person['qid'] not in all_persons:
                all_persons[person['qid']] = person
                new_persons += 1
            else:
                # Keep the entry with higher fame score
                if person['fame_score'] > all_persons[person['qid']]['fame_score']:
                    all_persons[person['qid']] = person
        
        if persons:
            avg_sitelinks = sum(p['sitelinks'] for p in persons) / len(persons)
            avg_birth_year = sum(p.get('birth_year', 0) for p in persons if p.get('birth_year')) / max(len([p for p in persons if p.get('birth_year')]), 1)
            tqdm.write(f"  ✓ {occupation_qid}: {len(persons)} persons ({new_persons} new) "
                      f"[avg {avg_sitelinks:.1f} sitelinks, avg birth {int(avg_birth_year)}]")
        else:
            tqdm.write(f"  ✗ {occupation_qid}: 0 persons found")
    
    # Sort by fame score
    person_list = sorted(all_persons.values(), key=lambda x: x['fame_score'], reverse=True)
    
    # Statistics
    print(f"\n✅ Total unique persons collected: {len(person_list)}")
    
    if person_list:
        avg_sitelinks = sum(p['sitelinks'] for p in person_list) / len(person_list)
        avg_statements = sum(p['statements'] for p in person_list) / len(person_list)
        with_images = sum(1 for p in person_list if p.get('image'))
        
        # Birth year statistics
        birth_years = [p.get('birth_year') for p in person_list if p.get('birth_year')]
        if birth_years:
            avg_birth = sum(birth_years) / len(birth_years)
            oldest = min(birth_years)
            youngest = max(birth_years)
            
            # Age distribution
            current_year = 2025
            ages = [current_year - year for year in birth_years]
            under_30 = sum(1 for age in ages if age < 30)
            age_30_50 = sum(1 for age in ages if 30 <= age < 50)
            age_50_plus = sum(1 for age in ages if age >= 50)
        
        print(f"📈 Average sitelinks: {avg_sitelinks:.1f}")
        print(f"📈 Average statements: {avg_statements:.1f}")
        print(f"📸 Persons with images: {with_images} ({100*with_images/len(person_list):.1f}%)")
        
        if birth_years:
            print(f"\n📅 Age Distribution (as of 2025):")
            print(f"   Under 30 years: {under_30} ({100*under_30/len(birth_years):.1f}%)")
            print(f"   30-49 years: {age_30_50} ({100*age_30_50/len(birth_years):.1f}%)")
            print(f"   50+ years: {age_50_plus} ({100*age_50_plus/len(birth_years):.1f}%)")
            print(f"   Average birth year: {int(avg_birth)} (age ~{current_year - int(avg_birth)})")
            print(f"   Range: {oldest} - {youngest}")
        
        print(f"\n🌟 Top 30 most famous Thai persons:")
        for i, person in enumerate(person_list[:30], 1):
            birth_year = person.get('birth_year', 'N/A')
            age = f"age {current_year - birth_year}" if isinstance(birth_year, int) else "N/A"
            print(f"   {i}. {person['label']} ({person['qid']}) - "
                  f"born {birth_year} ({age}), {person['sitelinks']} sitelinks")
    
    # Clean old data
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
            old_manifest = json.load(f)
        for person in old_manifest:
            old_file = os.path.join(OUTPUT_DIR, f"{person['qid']}.json")
            if os.path.exists(old_file):
                os.remove(old_file)

    # Save manifest
    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(person_list, f, ensure_ascii=False, indent=2)
        
    print(f"\n💾 Manifest saved: {MANIFEST_PATH}")
    print("🚀 Next step: Run fetch_data.py and populate_databases.py")

if __name__ == "__main__":
    main()