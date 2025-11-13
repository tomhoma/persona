import sqlite3
import chromadb
import numpy as np
import os
import random
import uuid
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
from contextlib import asynccontextmanager

# Import improved similarity module
try:
    from improved_similarity import (
        calculate_improved_narrative_similarity,
        get_improved_narrative_explanation,
        calculate_simple_narrative_similarity
    )
    IMPROVED_SIMILARITY_AVAILABLE = True
except ImportError:
    IMPROVED_SIMILARITY_AVAILABLE = False
    print("Warning: improved_similarity module not found, using simple similarity")

DB_DIR = "data"
SQLITE_PATH = os.path.join(DB_DIR, "persona.db")
CHROMA_PATH = os.path.join(DB_DIR, "chroma")
NARRATIVE_EMBEDDINGS_DIR = os.path.join(DB_DIR, "narrative_embeddings")

# Adjusted weights - narrative gets more weight with improved system
W_NARRATIVE = 0.5
W_FACTUAL = 0.3
W_RELATIONAL = 0.2

PERSON_CACHE: Dict[str, Dict] = {}
GAME_SESSIONS: Dict[str, Dict] = {}
IMPROVED_EMBEDDINGS_CACHE: Dict[str, Dict] = {}  # Cache for improved embeddings

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

def get_narrative_explanation(similarity):
    """Generate human-readable explanation for narrative similarity"""
    if similarity >= 0.9:
        return "Extremely high similarity - narratives are nearly identical in themes and context"
    elif similarity >= 0.8:
        return "Very high similarity - narratives share strong thematic and contextual similarities"
    elif similarity >= 0.7:
        return "High similarity - narratives have significant thematic overlap and similar contexts"
    elif similarity >= 0.6:
        return "Moderate similarity - narratives share some common themes and contexts"
    elif similarity >= 0.5:
        return "Low similarity - narratives have limited thematic overlap"
    elif similarity >= 0.3:
        return "Very low similarity - narratives share few common elements"
    else:
        return "Minimal similarity - narratives are largely unrelated"

def calculate_narrative_similarity(person_qid, secret_qid):
    """
    Calculate narrative similarity with improved method if available.
    Falls back to simple cosine similarity if improved embeddings not available.
    """
    if IMPROVED_SIMILARITY_AVAILABLE and person_qid in IMPROVED_EMBEDDINGS_CACHE and secret_qid in IMPROVED_EMBEDDINGS_CACHE:
        # Use improved multi-aspect similarity
        result = calculate_improved_narrative_similarity(
            IMPROVED_EMBEDDINGS_CACHE[person_qid],
            IMPROVED_EMBEDDINGS_CACHE[secret_qid]
        )
        return result['overall_score']
    else:
        # Fallback to simple similarity
        person_vec = PERSON_CACHE[person_qid].get('narrative_vector', [])
        secret_vec = PERSON_CACHE[secret_qid].get('narrative_vector', [])
        return cosine_similarity(person_vec, secret_vec)


def calculate_ranking_for_secret(secret_qid):
    """Calculate ranking for a specific secret person with improved narrative similarity"""
    if secret_qid not in PERSON_CACHE:
        raise HTTPException(status_code=404, detail="Secret person not found.")

    secret_person = PERSON_CACHE[secret_qid]
    all_scores = []

    for qid, person_data in PERSON_CACHE.items():
        # Use improved narrative similarity
        sim_n = calculate_narrative_similarity(qid, secret_qid)

        # Factual and relational remain the same
        sim_f = jaccard_similarity(person_data['factual_qids'], secret_person['factual_qids'])
        sim_r = jaccard_similarity(person_data['relational_qids'], secret_person['relational_qids'])

        final_score = (W_NARRATIVE * sim_n) + (W_FACTUAL * sim_f) + (W_RELATIONAL * sim_r)
        all_scores.append({
            "qid": qid,
            "label": person_data["label"],
            "score": final_score,
            "sim_narrative": sim_n,
            "sim_factual": sim_f,
            "sim_relational": sim_r
        })

    sorted_ranking = sorted(all_scores, key=lambda x: x['score'], reverse=True)
    return [{
        "qid": item["qid"],
        "label": item["label"],
        "rank": i + 1,
        "score": item["score"],
        "sim_narrative": item["sim_narrative"],
        "sim_factual": item["sim_factual"],
        "sim_relational": item["sim_relational"]
    } for i, item in enumerate(sorted_ranking)]

def load_improved_embeddings():
    """Load improved narrative embeddings if available."""
    if not os.path.exists(NARRATIVE_EMBEDDINGS_DIR):
        print("INFO: Improved embeddings directory not found. Using simple embeddings.")
        return

    try:
        embedding_files = [f for f in os.listdir(NARRATIVE_EMBEDDINGS_DIR)
                          if f.endswith('.json') and not f.startswith('_')]

        for filename in embedding_files:
            filepath = os.path.join(NARRATIVE_EMBEDDINGS_DIR, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                qid = data['qid']
                IMPROVED_EMBEDDINGS_CACHE[qid] = data

        print(f"INFO: Loaded {len(IMPROVED_EMBEDDINGS_CACHE)} improved narrative embeddings.")
    except Exception as e:
        print(f"WARNING: Could not load improved embeddings: {e}")


def load_data_into_cache():
    """Load data with enhanced relationship support and improved embeddings"""
    print("INFO: --- Starting Data Loading ---")
    if not os.path.exists(SQLITE_PATH):
        print(f"ERROR: SQLite database not found at {SQLITE_PATH}.")
        return

    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.cursor()

    # Load persons
    cursor.execute("SELECT qid, label FROM persons")
    for qid, label in cursor.fetchall():
        PERSON_CACHE[qid] = {
            "qid": qid,
            "label": label, 
            "factual_qids": set(), 
            "relational_qids": set(), 
            "narrative_vector": [],
            "direct_relationships": [],
            "shared_contexts": []
        }
    
    # Load properties
    cursor.execute("SELECT person_qid, property_qid, type, label FROM person_properties")
    for person_qid, prop_qid, prop_type, prop_label in cursor.fetchall():
        if person_qid in PERSON_CACHE:
            if prop_type == 'factual':
                PERSON_CACHE[person_qid]["factual_qids"].add(prop_qid)
            elif prop_type == 'relational':
                PERSON_CACHE[person_qid]["relational_qids"].add(prop_qid)
    
    # Load direct relationships
    cursor.execute("""
        SELECT r.person1_qid, r.person2_qid, r.relationship_type, p.label
        FROM person_relationships r
        JOIN persons p ON r.person2_qid = p.qid
    """)
    for person1_qid, person2_qid, rel_type, person2_label in cursor.fetchall():
        if person1_qid in PERSON_CACHE:
            PERSON_CACHE[person1_qid]["direct_relationships"].append({
                "qid": person2_qid,
                "label": person2_label,
                "relationship_type": rel_type
            })
    
    # Load shared contexts
    cursor.execute("""
        SELECT s.person1_qid, s.person2_qid, s.context_type, s.context_label, p.label
        FROM shared_contexts s
        JOIN persons p ON s.person2_qid = p.qid
    """)
    for person1_qid, person2_qid, context_type, context_label, person2_label in cursor.fetchall():
        if person1_qid in PERSON_CACHE:
            PERSON_CACHE[person1_qid]["shared_contexts"].append({
                "qid": person2_qid,
                "label": person2_label,
                "context_type": context_type,
                "context_label": context_label
            })
    
    conn.close()
    print("INFO: SQLite data loaded with relationships.")

    # Load narrative vectors
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(name="narrative_vectors")
    chroma_data = collection.get(include=["embeddings"])
    for i, qid in enumerate(chroma_data['ids']):
        if qid in PERSON_CACHE:
            PERSON_CACHE[qid]['narrative_vector'] = chroma_data['embeddings'][i]
    
    print(f"INFO: --- Data Loading Complete. Loaded {len(PERSON_CACHE)} persons. ---")

    # Statistics
    total_direct_rels = sum(len(p["direct_relationships"]) for p in PERSON_CACHE.values())
    total_shared = sum(len(p["shared_contexts"]) for p in PERSON_CACHE.values())
    print(f"INFO: Total direct relationships: {total_direct_rels}")
    print(f"INFO: Total shared contexts: {total_shared}")

    # Load improved narrative embeddings if available
    load_improved_embeddings()
    if IMPROVED_EMBEDDINGS_CACHE:
        print(f"INFO: Using improved multi-aspect narrative similarity for {len(IMPROVED_EMBEDDINGS_CACHE)} persons.")
    else:
        print("INFO: Using simple cosine similarity for narrative comparison.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    load_data_into_cache()
    yield
    # Shutdown (if needed)

app = FastAPI(title="PersonaGuess API", lifespan=lifespan)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class Person(BaseModel): 
    qid: str
    label: str

class DailyRanking(Person): 
    rank: int
    score: float
    sim_narrative: float
    sim_factual: float
    sim_relational: float

class StartGameResponse(BaseModel):
    sessionId: str

class MakeGuessRequest(BaseModel):
    sessionId: str
    qid: str

class MakeGuessResponse(BaseModel):
    isCorrect: bool
    result: DailyRanking
    gameWon: bool

class ResignGameRequest(BaseModel):
    sessionId: str

class ResignGameResponse(BaseModel):
    secretPerson: Person
    result: DailyRanking

class GetRankingRequest(BaseModel):
    sessionId: str

class GetRankingResponse(BaseModel):
    dailyRanking: List[DailyRanking]

class MatchDetailsRequest(BaseModel):
    sessionId: str
    personQid: str

class NarrativeDetails(BaseModel):
    similarity: float
    vectorDimensions: int
    magnitude1: float
    magnitude2: float
    cosineDistance: float
    explanation: str

class DirectRelationship(BaseModel):
    qid: str
    label: str
    relationship_type: str

class SharedContext(BaseModel):
    qid: str
    label: str
    context_type: str
    context_label: str

class MatchDetails(BaseModel):
    factualMatches: List[str]
    factualNonMatches: List[str]
    relationalMatches: List[str]
    relationalNonMatches: List[str]
    narrativeSimilarity: float
    narrativeDetails: NarrativeDetails
    directRelationships: List[DirectRelationship]  # NEW
    sharedContexts: List[SharedContext]  # NEW

class MatchDetailsResponse(BaseModel):
    matchDetails: MatchDetails

# Endpoints
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "persons_loaded": len(PERSON_CACHE),
        "active_sessions": len(GAME_SESSIONS)
    }

@app.get("/persons", response_model=List[Person])
async def get_all_persons():
    if not PERSON_CACHE:
        raise HTTPException(status_code=503, detail="Data not loaded.")
    return [{"qid": data["qid"], "label": data["label"]} for data in PERSON_CACHE.values()]

@app.get("/random_secret", response_model=Person)
async def get_random_secret_person():
    if not PERSON_CACHE:
        raise HTTPException(status_code=503, detail="Data not loaded.")
    random_qid = random.choice(list(PERSON_CACHE.keys()))
    person_data = PERSON_CACHE[random_qid]
    return {"qid": random_qid, "label": person_data["label"]}

@app.get("/daily_ranking", response_model=List[DailyRanking])
async def get_daily_ranking(secret_qid: str):
    if secret_qid not in PERSON_CACHE:
        raise HTTPException(status_code=404, detail="Secret QID not found.")
    return calculate_ranking_for_secret(secret_qid)

@app.post("/start_game", response_model=StartGameResponse)
async def start_game():
    if not PERSON_CACHE:
        raise HTTPException(status_code=503, detail="Data not loaded.")
    
    secret_qid = random.choice(list(PERSON_CACHE.keys()))
    session_id = str(uuid.uuid4())
    
    GAME_SESSIONS[session_id] = {
        "secret_qid": secret_qid,
        "guesses": [],
        "is_game_won": False,
        "is_resigned": False,
        "ranking_calculated": False
    }
    
    return {"sessionId": session_id}

@app.post("/make_guess", response_model=MakeGuessResponse)
async def make_guess(request: MakeGuessRequest):
    if not PERSON_CACHE:
        raise HTTPException(status_code=503, detail="Data not loaded.")
    
    session_id = request.sessionId
    if session_id not in GAME_SESSIONS:
        raise HTTPException(status_code=404, detail="Game session not found.")
    
    session = GAME_SESSIONS[session_id]
    if session["is_game_won"] or session["is_resigned"]:
        raise HTTPException(status_code=400, detail="Game already finished.")
    
    secret_qid = session["secret_qid"]
    guessed_qid = request.qid
    
    if guessed_qid not in PERSON_CACHE:
        raise HTTPException(status_code=404, detail="Person not found.")
    
    ranking = calculate_ranking_for_secret(secret_qid)
    guessed_result = next((item for item in ranking if item["qid"] == guessed_qid), None)
    
    if not guessed_result:
        raise HTTPException(status_code=404, detail="Could not calculate result for guessed person.")
    
    is_correct = guessed_qid == secret_qid
    if is_correct:
        session["is_game_won"] = True
    
    session["guesses"].append(guessed_result)
    
    return {
        "isCorrect": is_correct,
        "result": guessed_result,
        "gameWon": is_correct
    }

@app.post("/resign_game", response_model=ResignGameResponse)
async def resign_game(request: ResignGameRequest):
    if not PERSON_CACHE:
        raise HTTPException(status_code=503, detail="Data not loaded.")
    
    session_id = request.sessionId
    if session_id not in GAME_SESSIONS:
        raise HTTPException(status_code=404, detail="Game session not found.")
    
    session = GAME_SESSIONS[session_id]
    if session["is_game_won"] or session["is_resigned"]:
        raise HTTPException(status_code=400, detail="Game already finished.")
    
    secret_qid = session["secret_qid"]
    secret_person_data = PERSON_CACHE[secret_qid]
    secret_person = {"qid": secret_qid, "label": secret_person_data["label"]}
    
    ranking = calculate_ranking_for_secret(secret_qid)
    secret_result = next((item for item in ranking if item["qid"] == secret_qid), None)
    
    if not secret_result:
        raise HTTPException(status_code=500, detail="Could not calculate result for secret person.")
    
    session["is_resigned"] = True
    
    return {
        "secretPerson": secret_person,
        "result": secret_result
    }

@app.post("/get_ranking", response_model=GetRankingResponse)
async def get_ranking(request: GetRankingRequest):
    """Get full ranking only when game is finished"""
    if not PERSON_CACHE:
        raise HTTPException(status_code=503, detail="Data not loaded.")
    
    session_id = request.sessionId
    if session_id not in GAME_SESSIONS:
        raise HTTPException(status_code=404, detail="Game session not found.")
    
    session = GAME_SESSIONS[session_id]
    
    if not session["is_game_won"] and not session["is_resigned"]:
        raise HTTPException(status_code=403, detail="Game not finished yet.")
    
    secret_qid = session["secret_qid"]
    ranking = calculate_ranking_for_secret(secret_qid)
    
    return {"dailyRanking": ranking}

@app.post("/get_match_details", response_model=MatchDetailsResponse)
async def get_match_details(request: MatchDetailsRequest):
    """Get detailed match information including relationships"""
    if not PERSON_CACHE:
        raise HTTPException(status_code=503, detail="Data not loaded.")
    
    session_id = request.sessionId
    if session_id not in GAME_SESSIONS:
        raise HTTPException(status_code=404, detail="Game session not found.")
    
    session = GAME_SESSIONS[session_id]
    
    if not session["is_game_won"] and not session["is_resigned"]:
        raise HTTPException(status_code=403, detail="Game not finished yet.")
    
    secret_qid = session["secret_qid"]
    person_qid = request.personQid
    
    if secret_qid not in PERSON_CACHE or person_qid not in PERSON_CACHE:
        raise HTTPException(status_code=404, detail="Person not found.")
    
    secret_person = PERSON_CACHE[secret_qid]
    person_data = PERSON_CACHE[person_qid]
    
    # Get factual and relational matches
    factual_matches = list(secret_person['factual_qids'].intersection(person_data['factual_qids']))
    factual_non_matches = list(secret_person['factual_qids'] - person_data['factual_qids'])
    relational_matches = list(secret_person['relational_qids'].intersection(person_data['relational_qids']))
    relational_non_matches = list(secret_person['relational_qids'] - person_data['relational_qids'])
    
    # Get labels from database
    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.cursor()
    
    def get_labels(qids):
        labels = []
        for qid in qids:
            if qid in PERSON_CACHE:
                labels.append(PERSON_CACHE[qid]['label'])
            else:
                cursor.execute("SELECT label FROM person_properties WHERE property_qid = ? LIMIT 1", (qid,))
                result = cursor.fetchone()
                if result:
                    labels.append(result[0])
                else:
                    labels.append(f"Unknown: {qid}")
        return labels
    
    # Check if guessed person has direct relationship with secret person
    direct_relationships = []
    for rel in person_data.get("direct_relationships", []):
        if rel["qid"] == secret_qid:
            direct_relationships.append(rel)
    
    # Check if they share contexts
    shared_contexts = []
    secret_context_map = {(sc["qid"], sc["context_type"]): sc for sc in secret_person.get("shared_contexts", [])}
    
    for sc in person_data.get("shared_contexts", []):
        key = (sc["qid"], sc["context_type"])
        if key in secret_context_map:
            # They both share context with the same person
            if sc["qid"] != secret_qid and sc["qid"] != person_qid:
                shared_contexts.append(sc)
    
    # Calculate narrative similarity
    person_vector = person_data.get('narrative_vector', [])
    secret_vector = secret_person.get('narrative_vector', [])
    narrative_similarity = cosine_similarity(person_vector, secret_vector)
    
    narrative_details = {
        "similarity": narrative_similarity,
        "vectorDimensions": len(person_vector) if len(person_vector) > 0 else 0,
        "magnitude1": float(np.linalg.norm(person_vector)) if len(person_vector) > 0 else 0.0,
        "magnitude2": float(np.linalg.norm(secret_vector)) if len(secret_vector) > 0 else 0.0,
        "cosineDistance": 1.0 - narrative_similarity,
        "explanation": get_narrative_explanation(narrative_similarity)
    }
    
    match_details = {
        "factualMatches": get_labels(factual_matches),
        "factualNonMatches": get_labels(factual_non_matches),
        "relationalMatches": get_labels(relational_matches),
        "relationalNonMatches": get_labels(relational_non_matches),
        "narrativeSimilarity": narrative_similarity,
        "narrativeDetails": narrative_details,
        "directRelationships": direct_relationships,
        "sharedContexts": shared_contexts[:10]  # Limit to top 10 to avoid overwhelming
    }
    
    conn.close()
    
    return {"matchDetails": match_details}