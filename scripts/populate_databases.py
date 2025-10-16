import os
import json
import sqlite3
import chromadb
import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

# --- Configuration ---
DB_DIR = "data"
RAW_DATA_DIR = "data/raw"
SQLITE_PATH = os.path.join(DB_DIR, "persona.db")
CHROMA_PATH = os.path.join(DB_DIR, "chroma")
MODEL_NAME = 'all-MiniLM-L6-v2'
FACTUAL_PROPERTIES = ["P106", "P27", "P166"]
RELATIONAL_PROPERTIES = ["P737", "P1066", "P800", "P108", "P1411", "P19", "P20", "P21", "P22", "P25", "P40", "P1038", "P551", "P3373", "P69", "P1198", "P140", "P937", "P1344", "P106", "P102", "P39", "P54", "P241"]

# --- Database Setup ---
def setup_databases():
    """Initializes SQLite and ChromaDB, creating tables and collections if they don't exist."""
    os.makedirs(DB_DIR, exist_ok=True)

    # SQLite
    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS persons (
            qid TEXT PRIMARY KEY,
            label TEXT,
            thwiki_title TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS person_properties (
            person_qid TEXT,
            property_qid TEXT,
            type TEXT,
            PRIMARY KEY (person_qid, property_qid)
        )
    """)
    conn.commit()
    conn.close()

    # ChromaDB
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(name="narrative_vectors")

    print("Databases initialized.")
    return client, collection

# --- Main Logic ---
def main():
    """
    Populates the databases from the collected raw JSON files.
    - Sets up database connections.
    - Loads the sentence transformer model.
    - Iterates through the manifest to find all person JSON files.
    - For each person, processes and inserts data into SQLite and ChromaDB.
    """
    # 1. Setup
    chroma_client, narrative_collection = setup_databases()
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    model = SentenceTransformer(MODEL_NAME)

    manifest_path = os.path.join(RAW_DATA_DIR, "_manifest.json")
    if not os.path.exists(manifest_path):
        print("Error: Manifest file not found. Please run create_manifest.py first.")
        return

    with open(manifest_path, 'r', encoding='utf-8') as f:
        person_list = json.load(f)

    print(f"Processing {len(person_list)} persons from the manifest.")

    # 2. Process each person
    for person_manifest in tqdm(person_list, desc="Populating databases"):
        qid = person_manifest['qid']
        json_path = os.path.join(RAW_DATA_DIR, f"{qid}.json")

        if not os.path.exists(json_path):
            print(f"Warning: JSON file for {qid} not found. Skipping.")
            continue

        with open(json_path, 'r', encoding='utf-8') as f:
            person_data = json.load(f)

        # Check if person already exists in DB
        if sqlite_conn.execute("SELECT 1 FROM persons WHERE qid=?", (qid,)).fetchone():
            continue

        # 3. Extract and Transform Data
        summary = person_data.get("narrative_summary", "")
        details = person_data.get("details", {})

        # Generate narrative vector
        narrative_vector = model.encode(summary).tolist() if summary else []

        # Extract factual and relational QIDs
        factual_qids = {
            item['qid']
            for prop in FACTUAL_PROPERTIES if prop in details
            for item in details[prop]
        }
        relational_qids = {
            item['qid']
            for prop in RELATIONAL_PROPERTIES if prop in details
            for item in details[prop]
        }

        # 4. Load into Databases
        cursor = sqlite_conn.cursor()

        # Insert into persons table
        cursor.execute(
            "INSERT OR IGNORE INTO persons (qid, label, thwiki_title) VALUES (?, ?, ?)",
            (qid, person_data['label'], person_data['thwiki_title'])
        )

        # Insert into person_properties table
        prop_data = (
            [(qid, pq, 'factual') for pq in factual_qids] +
            [(qid, pq, 'relational') for pq in relational_qids]
        )
        cursor.executemany(
            "INSERT OR IGNORE INTO person_properties (person_qid, property_qid, type) VALUES (?, ?, ?)",
            prop_data
        )

        # Add to ChromaDB
        if narrative_vector:
            narrative_collection.add(
                embeddings=[narrative_vector],
                ids=[qid]
            )

        sqlite_conn.commit()

    # 5. Cleanup
    sqlite_conn.close()
    print("Database population complete.")

if __name__ == "__main__":
    main()
