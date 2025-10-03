import sqlite3
import chromadb
import numpy as np
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict

# --- Configuration ---
DB_DIR = "data"
SQLITE_PATH = os.path.join(DB_DIR, "persona.db")
CHROMA_PATH = os.path.join(DB_DIR, "chroma")

# --- Weights for Final Score ---
W_NARRATIVE = 0.5
W_FACTUAL = 0.3
W_RELATIONAL = 0.2

# --- FastAPI App ---
app = FastAPI(
    title="PersonaGuess API",
    description="API for the PersonaGuess game engine.",
    version="1.0.0",
)

# --- In-Memory Data Store ---
# This cache will be populated on startup
PERSON_CACHE: Dict[str, Dict] = {}

# --- Helper Functions ---
def jaccard_similarity(set1, set2):
    """Calculates Jaccard similarity between two sets."""
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union if union != 0 else 0

def cosine_similarity(vec1, vec2):
    """Calculates cosine similarity between two numpy arrays."""
    if not isinstance(vec1, np.ndarray): vec1 = np.array(vec1)
    if not isinstance(vec2, np.ndarray): vec2 = np.array(vec2)

    dot_product = np.dot(vec1, vec2)
    norm_a = np.linalg.norm(vec1)
    norm_b = np.linalg.norm(vec2)

    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)

# --- Pydantic Models ---
class Person(BaseModel):
    qid: str
    label: str

class SimilarityScore(BaseModel):
    narrative_sim: float
    factual_sim: float
    relational_sim: float
    final_score: float

class GuessResult(Person):
    scores: SimilarityScore

class DailyRanking(Person):
    rank: int
    score: float


# --- Database Loading on Startup ---
@app.on_event("startup")
def load_data_into_cache():
    """Load all person data from SQLite and ChromaDB into memory."""
    print("INFO: --- Starting Data Loading ---")

    # 1. Load metadata and properties from SQLite
    if not os.path.exists(SQLITE_PATH):
        print("ERROR: SQLite database not found. Cannot start.")
        return

    print("INFO: Connecting to SQLite and loading metadata...")
    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT qid, label FROM persons")
    persons = cursor.fetchall()
    for qid, label in persons:
        PERSON_CACHE[qid] = {"qid": qid, "label": label, "factual_qids": set(), "relational_qids": set()}

    print(f"INFO: Loaded {len(persons)} person records from 'persons' table.")

    cursor.execute("SELECT person_qid, property_qid, type FROM person_properties")
    properties = cursor.fetchall()
    for person_qid, prop_qid, prop_type in properties:
        if person_qid in PERSON_CACHE:
            if prop_type == 'factual':
                PERSON_CACHE[person_qid]["factual_qids"].add(prop_qid)
            elif prop_type == 'relational':
                PERSON_CACHE[person_qid]["relational_qids"].add(prop_qid)

    conn.close()
    print("INFO: SQLite data loaded and connection closed.")

    # 2. Load narrative vectors from ChromaDB
    if not os.path.exists(CHROMA_PATH):
        print("ERROR: ChromaDB not found. Cannot start.")
        return

    print("INFO: Connecting to ChromaDB and loading narrative vectors...")
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection(name="narrative_vectors")

    # Fetch all embeddings from Chroma
    print("INFO: Fetching all vector embeddings from Chroma. This may take a moment...")
    chroma_data = collection.get(include=["embeddings"])
    print(f"INFO: Retrieved {len(chroma_data['ids'])} vectors from ChromaDB.")

    for i, qid in enumerate(chroma_data['ids']):
        if qid in PERSON_CACHE:
            PERSON_CACHE[qid]['narrative_vector'] = chroma_data['embeddings'][i]

    print(f"INFO: --- Data Loading Complete. Successfully loaded {len(PERSON_CACHE)} persons into cache. ---")


# --- API Endpoints ---
@app.get("/", tags=["Status"])
async def root():
    return {"message": "PersonaGuess API is running."}

@app.get("/persons", response_model=List[Person], tags=["Game Data"])
async def get_all_persons():
    """Returns a list of all available persons for autocomplete."""
    if not PERSON_CACHE:
        raise HTTPException(status_code=503, detail="Data is not loaded yet. Please try again later.")
    return [{"qid": data["qid"], "label": data["label"]} for data in PERSON_CACHE.values()]


@app.get("/find_similar", response_model=GuessResult, tags=["Core Engine"])
async def find_similar(guess_qid: str, secret_qid: str):
    """Calculates the similarity between a guessed person and the secret person."""
    if guess_qid not in PERSON_CACHE or secret_qid not in PERSON_CACHE:
        raise HTTPException(status_code=404, detail="One or both QIDs not found in cache.")

    guess_person = PERSON_CACHE[guess_qid]
    secret_person = PERSON_CACHE[secret_qid]

    # Calculate similarities
    sim_n = cosine_similarity(guess_person['narrative_vector'], secret_person['narrative_vector'])
    sim_f = jaccard_similarity(guess_person['factual_qids'], secret_person['factual_qids'])
    sim_r = jaccard_similarity(guess_person['relational_qids'], secret_person['relational_qids'])

    # Calculate final score
    final_score = (W_NARRATIVE * sim_n) + (W_FACTUAL * sim_f) + (W_RELATIONAL * sim_r)

    return {
        "qid": guess_person["qid"],
        "label": guess_person["label"],
        "scores": {
            "narrative_sim": sim_n,
            "factual_sim": sim_f,
            "relational_sim": sim_r,
            "final_score": final_score,
        }
    }

@app.get("/daily_ranking", response_model=List[DailyRanking], tags=["Game Logic"])
async def get_daily_ranking(secret_qid: str):
    """
    Calculates the full similarity ranking for all persons against a secret QID.
    This is computationally intensive and should be cached by the frontend.
    """
    if secret_qid not in PERSON_CACHE:
        raise HTTPException(status_code=404, detail="Secret QID not found in cache.")

    secret_person = PERSON_CACHE[secret_qid]
    all_scores = []

    for qid, person_data in PERSON_CACHE.items():
        sim_n = cosine_similarity(person_data['narrative_vector'], secret_person['narrative_vector'])
        sim_f = jaccard_similarity(person_data['factual_qids'], secret_person['factual_qids'])
        sim_r = jaccard_similarity(person_data['relational_qids'], secret_person['relational_qids'])
        final_score = (W_NARRATIVE * sim_n) + (W_FACTUAL * sim_f) + (W_RELATIONAL * sim_r)
        all_scores.append({"qid": qid, "label": person_data["label"], "score": final_score})

    # Sort by score descending
    sorted_ranking = sorted(all_scores, key=lambda x: x['score'], reverse=True)

    # Add rank
    response = []
    for i, item in enumerate(sorted_ranking):
        response.append({
            "qid": item["qid"],
            "label": item["label"],
            "rank": i + 1,
            "score": item["score"]
        })

    return response