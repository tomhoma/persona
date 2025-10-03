import os
import json
import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import logging

# --- Configuration ---
RAW_DATA_DIR = "data/raw"
PROCESSED_DATA_DIR = "data/processed"
MODEL_NAME = 'all-MiniLM-L6-v2'

# Define which properties are factual vs. relational
# P106: occupation, P27: country of citizenship, P166: award received
FACTUAL_PROPERTIES = ["P106", "P27", "P166"]
# P737: influenced by, P1066: student of, P800: notable work (can link people)
RELATIONAL_PROPERTIES = ["P737", "P1066", "P800"]


# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Ensure output directory exists ---
os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)


def generate_narrative_vector(text, model):
    """Generates a sentence embedding for the given text."""
    if not text or not isinstance(text, str) or len(text.strip()) == 0:
        return np.zeros(model.get_sentence_embedding_dimension()).tolist()

    try:
        vector = model.encode(text, convert_to_numpy=True)
        return vector.tolist()
    except Exception as e:
        logging.error(f"Error encoding text: {e}")
        return np.zeros(model.get_sentence_embedding_dimension()).tolist()

def process_properties(details):
    """
    Separates Wikidata properties into factual and relational sets of QIDs.
    """
    factual_qids = set()
    relational_qids = set()

    for prop_code, values in details.items():
        for item in values:
            qid = item.get("qid")
            if not qid:
                continue

            if prop_code in FACTUAL_PROPERTIES:
                factual_qids.add(qid)
            elif prop_code in RELATIONAL_PROPERTIES:
                relational_qids.add(qid)

    return list(factual_qids), list(relational_qids)


def main():
    """
    Main function to process raw data and generate all 3 vector components.
    """
    logging.info(f"Loading Sentence Transformer model: {MODEL_NAME}")
    try:
        model = SentenceTransformer(MODEL_NAME)
    except Exception as e:
        logging.error(f"Failed to load model '{MODEL_NAME}'. Error: {e}")
        return

    raw_files = [f for f in os.listdir(RAW_DATA_DIR) if f.endswith('.json') and not f.startswith('_')]

    logging.info(f"Found {len(raw_files)} raw data files to process.")

    for filename in tqdm(raw_files, desc="Generating Vectors"):
        raw_path = os.path.join(RAW_DATA_DIR, filename)
        processed_path = os.path.join(PROCESSED_DATA_DIR, filename)

        if os.path.exists(processed_path):
            # Check if the existing file is already processed with all keys
            with open(processed_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            if "factual_qids" in existing_data and "relational_qids" in existing_data:
                 continue # Skip if fully processed

        try:
            with open(raw_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # --- 1. Narrative Vector ---
            summary = data.get("narrative_summary", "")
            narrative_vector = generate_narrative_vector(summary, model)

            # --- 2. Factual and 3. Relational Vectors (as QID sets) ---
            details = data.get("details", {})
            factual_qids, relational_qids = process_properties(details)

            processed_data = {
                "qid": data["qid"],
                "label": data["label"],
                "narrative_vector": narrative_vector,
                "factual_qids": factual_qids,
                "relational_qids": relational_qids,
            }

            with open(processed_path, 'w', encoding='utf-8') as f:
                json.dump(processed_data, f, ensure_ascii=False, indent=2)

        except json.JSONDecodeError:
            logging.warning(f"Skipping invalid JSON file: {filename}")
        except Exception as e:
            logging.error(f"An error occurred while processing {filename}: {e}")

    logging.info("Vector generation process completed.")


if __name__ == "__main__":
    main()