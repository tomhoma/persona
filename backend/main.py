import sqlite3
import chromadb
import numpy as np
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict

DB_DIR = "data"
SQLITE_PATH = os.path.join(DB_DIR, "persona.db")
CHROMA_PATH = os.path.join(DB_DIR, "chroma")
W_NARRATIVE = 0.5
W_FACTUAL = 0.3
W_RELATIONAL = 0.2

app = FastAPI(title="PersonaGuess API")
PERSON_CACHE: Dict[str, Dict] = {}

def jaccard_similarity(set1, set2):
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union if union != 0 else 0

def cosine_similarity(vec1, vec2):
    if not isinstance(vec1, np.ndarray): vec1 = np.array(vec1)
    if not isinstance(vec2, np.ndarray): vec2 = np.array(vec2)
    if vec1.shape != vec2.shape or np.linalg.norm(vec1) == 0 or np.linalg.norm(vec2) == 0:
        return 0.0
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

class Person(BaseModel): qid: str; label: str
class DailyRanking(Person): rank: int; score: float

@app.on_event("startup")
def load_data_into_cache():
    print("INFO: --- Starting Data Loading ---")
    if not os.path.exists(SQLITE_PATH):
        print(f"ERROR: SQLite database not found at {SQLITE_PATH}.")
        return
    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT qid, label FROM persons")
    for qid, label in cursor.fetchall():
        PERSON_CACHE[qid] = {"qid": qid, "label": label, "factual_qids": set(), "relational_qids": set(), "narrative_vector": []}
    cursor.execute("SELECT person_qid, property_qid, type FROM person_properties")
    for person_qid, prop_qid, prop_type in cursor.fetchall():
        if person_qid in PERSON_CACHE:
            if prop_type == 'factual': PERSON_CACHE[person_qid]["factual_qids"].add(prop_qid)
            elif prop_type == 'relational': PERSON_CACHE[person_qid]["relational_qids"].add(prop_qid)
    conn.close()
    print("INFO: SQLite data loaded.")

    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(name="narrative_vectors")
    chroma_data = collection.get(include=["embeddings"])
    for i, qid in enumerate(chroma_data['ids']):
        if qid in PERSON_CACHE:
            PERSON_CACHE[qid]['narrative_vector'] = chroma_data['embeddings'][i]
    print(f"INFO: --- Data Loading Complete. Loaded {len(PERSON_CACHE)} persons. ---")

@app.get("/persons", response_model=List[Person])
async def get_all_persons():
    if not PERSON_CACHE: raise HTTPException(status_code=503, detail="Data not loaded.")
    return [{"qid": data["qid"], "label": data["label"]} for data in PERSON_CACHE.values()]

@app.get("/daily_ranking", response_model=List[DailyRanking])
async def get_daily_ranking(secret_qid: str):
    if secret_qid not in PERSON_CACHE: raise HTTPException(status_code=404, detail="Secret QID not found.")
    secret_person = PERSON_CACHE[secret_qid]
    all_scores = []
    for qid, person_data in PERSON_CACHE.items():
        sim_n = cosine_similarity(person_data.get('narrative_vector', []), secret_person.get('narrative_vector', []))
        sim_f = jaccard_similarity(person_data['factual_qids'], secret_person['factual_qids'])
        sim_r = jaccard_similarity(person_data['relational_qids'], secret_person['relational_qids'])
        final_score = (W_NARRATIVE * sim_n) + (W_FACTUAL * sim_f) + (W_RELATIONAL * sim_r)
        all_scores.append({"qid": qid, "label": person_data["label"], "score": final_score})
    sorted_ranking = sorted(all_scores, key=lambda x: x['score'], reverse=True)
    return [{"qid": item["qid"], "label": item["label"], "rank": i + 1, "score": item["score"]} for i, item in enumerate(sorted_ranking)]
