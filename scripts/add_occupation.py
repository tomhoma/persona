import sys
import json
import requests
from SPARQLWrapper import SPARQLWrapper, JSON

QIDS_FILE = "scripts/qids.json"

def search_occupation_qid(occupation_name):
    """
    Searches for the Wikidata QID of a given occupation name.
    """
    # Wikidata API endpoint
    url = "https://www.wikidata.org/w/api.php"

    # Parameters for the API request
    params = {
        "action": "wbsearchentities",
        "format": "json",
        "language": "en",
        "type": "item",
        "search": occupation_name
    }

    # Headers with a user agent
    headers = {
        "User-Agent": "PersonaGuessApp/1.0 (https://github.com/your-repo; your-email@example.com)"
    }

    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        search_results = response.json()

        if "search" in search_results and search_results["search"]:
            # Find the most likely match (usually the first result)
            for result in search_results["search"]:
                # Check if the result has a description and if it contains "occupation"
                if "description" in result and "occupation" in result["description"].lower():
                    return result["id"]
            # If no result with "occupation" in the description is found, return the first result
            return search_results["search"][0]["id"]

    except requests.exceptions.RequestException as e:
        print(f"Error searching for occupation: {e}")
        return None

def verify_occupation_qid(qid):
    """
    Queries Wikidata to count the number of people associated with a given
    occupation QID.
    """
    sparql = SPARQLWrapper("https://query.wikidata.org/sparql", agent="PersonaGuessApp/1.0")

    # Query to count people with the specified occupation
    query = f"""
    SELECT (COUNT(?person) as ?count) WHERE {{
      ?person wdt:P106 wd:{qid}.
    }}
    """

    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)

    try:
        results = sparql.query().convert()
        count = int(results["results"]["bindings"][0]["count"]["value"])
        return count

    except Exception as e:
        print(f"Error verifying {qid}: {e}")
        return 0

def update_qids_file(occupation_name, qid):
    """
    Updates the qids.json file with the new occupation and QID.
    """
    try:
        with open(QIDS_FILE, 'r') as f:
            qids_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        qids_data = {}

    occupation_key = occupation_name.lower().replace(" ", "_")

    if occupation_key in qids_data:
        print(f"Occupation '{occupation_name}' already exists in {QIDS_FILE}.")
        return

    qids_data[occupation_key] = qid

    with open(QIDS_FILE, 'w') as f:
        json.dump(qids_data, f, indent=2)

    print(f"Added '{occupation_name}' (Q{qid}) to {QIDS_FILE}.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        occupation_name = sys.argv[1]
        qid = search_occupation_qid(occupation_name)
        if qid:
            print(f"Found QID for '{occupation_name}': {qid}")
            count = verify_occupation_qid(qid)
            print(f"Verifying '{occupation_name}' ({qid})...")
            print(f"Found {count} people with this occupation.")
            if count > 100:
                print(f"'{occupation_name}' is a valid occupation.")
                update_qids_file(occupation_name, qid)
            else:
                print(f"'{occupation_name}' may not be a valid occupation (low count).")
        else:
            print(f"Could not find QID for '{occupation_name}'.")
    else:
        print("Please provide an occupation name as an argument.")