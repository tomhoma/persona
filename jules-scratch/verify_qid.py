import sys
from SPARQLWrapper import SPARQLWrapper, JSON

def verify_qid(category_name, qid):
    """Queries Wikidata to get the label and description for a given QID."""
    sparql = SPARQLWrapper("https://query.wikidata.org/sparql", agent="PersonaGuessApp/1.0")
    query = f"""
    SELECT ?itemLabel ?itemDescription WHERE {{
      VALUES ?item {{ wd:{qid} }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    """
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    try:
        results = sparql.query().convert()["results"]["bindings"]
        if results:
            label = results[0].get("itemLabel", {}).get("value", "N/A")
            print(f"Category: {category_name}")
            print(f"Verified QID: wd:{qid}")
            print(f"Verification Result (Label): {label}")
        else:
            print(f"No results for QID: {qid}")
    except Exception as e:
        print(f"Error verifying {qid}: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 2:
        category = sys.argv[1]
        qid_to_check = sys.argv[2].replace("wd:", "")
        verify_qid(category, qid_to_check)
    else:
        print("Please provide a category name and a QID as arguments (e.g., \"Performing Arts\" Q12345).")