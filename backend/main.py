import sqlite3
import chromadb
import numpy as np
import os
import random
import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional

DB_DIR = "data"
SQLITE_PATH = os.path.join(DB_DIR, "persona.db")
CHROMA_PATH = os.path.join(DB_DIR, "chroma")
W_NARRATIVE = 0.5
W_FACTUAL = 0.3
W_RELATIONAL = 0.2

app = FastAPI(title="PersonaGuess API")
PERSON_CACHE: Dict[str, Dict] = {}
GAME_SESSIONS: Dict[str, Dict] = {}  # Store active game sessions

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

def calculate_ranking_for_secret(secret_qid):
    """Calculate ranking for a specific secret person"""
    if secret_qid not in PERSON_CACHE:
        raise HTTPException(status_code=404, detail="Secret person not found.")
    
    secret_person = PERSON_CACHE[secret_qid]
    all_scores = []
    
    for qid, person_data in PERSON_CACHE.items():
        sim_n = cosine_similarity(person_data.get('narrative_vector', []), secret_person.get('narrative_vector', []))
        sim_f = jaccard_similarity(person_data['factual_qids'], secret_person['factual_qids'])
        sim_r = jaccard_similarity(person_data['relational_qids'], secret_person['relational_qids'])
        final_score = (W_NARRATIVE * sim_n) + (W_FACTUAL * sim_f) + (W_RELATIONAL * sim_r)
        all_scores.append({"qid": qid, "label": person_data["label"], "score": final_score, "sim_narrative": sim_n, "sim_factual": sim_f, "sim_relational": sim_r})
    
    sorted_ranking = sorted(all_scores, key=lambda x: x['score'], reverse=True)
    return [{"qid": item["qid"], "label": item["label"], "rank": i + 1, "score": item["score"], "sim_narrative": item["sim_narrative"], "sim_factual": item["sim_factual"], "sim_relational": item["sim_relational"]} for i, item in enumerate(sorted_ranking)]

class Person(BaseModel): qid: str; label: str
class DailyRanking(Person): rank: int; score: float; sim_narrative: float; sim_factual: float; sim_relational: float

# New models for secure endpoints
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

class MatchDetails(BaseModel):
    factualMatches: List[str]
    factualNonMatches: List[str]
    relationalMatches: List[str]
    relationalNonMatches: List[str]
    narrativeSimilarity: float
    narrativeDetails: NarrativeDetails

class MatchDetailsResponse(BaseModel):
    matchDetails: MatchDetails

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

@app.get("/random_secret", response_model=Person)
async def get_random_secret_person():
    if not PERSON_CACHE: raise HTTPException(status_code=503, detail="Data not loaded.")
    random_qid = random.choice(list(PERSON_CACHE.keys()))
    person_data = PERSON_CACHE[random_qid]
    return {"qid": random_qid, "label": person_data["label"]}

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
        all_scores.append({"qid": qid, "label": person_data["label"], "score": final_score, "sim_narrative": sim_n, "sim_factual": sim_f, "sim_relational": sim_r})
    sorted_ranking = sorted(all_scores, key=lambda x: x['score'], reverse=True)
    return [{"qid": item["qid"], "label": item["label"], "rank": i + 1, "score": item["score"], "sim_narrative": item["sim_narrative"], "sim_factual": item["sim_factual"], "sim_relational": item["sim_relational"]} for i, item in enumerate(sorted_ranking)]

# New secure endpoints
@app.post("/start_game", response_model=StartGameResponse)
async def start_game():
    if not PERSON_CACHE:
        raise HTTPException(status_code=503, detail="Data not loaded.")
    
    # Generate a random secret person
    secret_qid = random.choice(list(PERSON_CACHE.keys()))
    
    # Generate session ID
    session_id = str(uuid.uuid4())
    
    # Store session data (don't calculate ranking yet to avoid exposure)
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
    
    # Calculate ranking for this secret person (on-demand)
    ranking = calculate_ranking_for_secret(secret_qid)
    
    # Find the result for the guessed person
    guessed_result = next((item for item in ranking if item["qid"] == guessed_qid), None)
    if not guessed_result:
        raise HTTPException(status_code=404, detail="Could not calculate result for guessed person.")
    
    result = guessed_result
    
    # Check if guess is correct
    is_correct = guessed_qid == secret_qid
    if is_correct:
        session["is_game_won"] = True
    
    session["guesses"].append(result)
    
    return {
        "isCorrect": is_correct,
        "result": result,
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
    
    # Calculate ranking for this secret person (on-demand)
    ranking = calculate_ranking_for_secret(secret_qid)
    
    # Find the result for the secret person (should be rank 1)
    secret_result = next((item for item in ranking if item["qid"] == secret_qid), None)
    if not secret_result:
        raise HTTPException(status_code=500, detail="Could not calculate result for secret person.")
    
    result = secret_result
    
    session["is_resigned"] = True
    
    return {
        "secretPerson": secret_person,
        "result": result
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
    
    # Only allow getting ranking when game is finished
    if not session["is_game_won"] and not session["is_resigned"]:
        raise HTTPException(status_code=403, detail="Game not finished yet.")
    
    secret_qid = session["secret_qid"]
    ranking = calculate_ranking_for_secret(secret_qid)
    
    return {"dailyRanking": ranking}

@app.post("/get_match_details", response_model=MatchDetailsResponse)
async def get_match_details(request: MatchDetailsRequest):
    """Get detailed match information for a specific person"""
    if not PERSON_CACHE:
        raise HTTPException(status_code=503, detail="Data not loaded.")
    
    session_id = request.sessionId
    if session_id not in GAME_SESSIONS:
        raise HTTPException(status_code=404, detail="Game session not found.")
    
    session = GAME_SESSIONS[session_id]
    
    # Only allow getting match details when game is finished
    if not session["is_game_won"] and not session["is_resigned"]:
        raise HTTPException(status_code=403, detail="Game not finished yet.")
    
    secret_qid = session["secret_qid"]
    person_qid = request.personQid
    
    if secret_qid not in PERSON_CACHE or person_qid not in PERSON_CACHE:
        raise HTTPException(status_code=404, detail="Person not found.")
    
    secret_person = PERSON_CACHE[secret_qid]
    person_data = PERSON_CACHE[person_qid]
    
    print(f"DEBUG: Secret person {secret_qid} has {len(secret_person['factual_qids'])} factual properties and {len(secret_person['relational_qids'])} relational properties")
    print(f"DEBUG: Person {person_qid} has {len(person_data['factual_qids'])} factual properties and {len(person_data['relational_qids'])} relational properties")
    
    # Get factual matches and non-matches
    factual_matches = list(secret_person['factual_qids'].intersection(person_data['factual_qids']))
    # For different properties, show what the secret person has that this person doesn't have
    factual_non_matches = list(secret_person['factual_qids'] - person_data['factual_qids'])
    
    # Get relational matches and non-matches
    relational_matches = list(secret_person['relational_qids'].intersection(person_data['relational_qids']))
    # For different relations, show what the secret person has that this person doesn't have
    relational_non_matches = list(secret_person['relational_qids'] - person_data['relational_qids'])
    
    print(f"DEBUG: Found {len(factual_matches)} factual matches, {len(factual_non_matches)} factual non-matches")
    print(f"DEBUG: Factual matches QIDs: {factual_matches}")
    print(f"DEBUG: Factual non-matches QIDs: {factual_non_matches}")
    print(f"DEBUG: Found {len(relational_matches)} relational matches, {len(relational_non_matches)} relational non-matches")
    print(f"DEBUG: Relational matches QIDs: {relational_matches}")
    print(f"DEBUG: Relational non-matches QIDs: {relational_non_matches}")
    
    # Calculate narrative similarity and details
    person_vector = person_data.get('narrative_vector', [])
    secret_vector = secret_person.get('narrative_vector', [])
    narrative_similarity = cosine_similarity(person_vector, secret_vector)
    
    # Calculate detailed narrative information
    narrative_details = {
        "similarity": narrative_similarity,
        "vectorDimensions": len(person_vector) if len(person_vector) > 0 else 0,
        "magnitude1": float(np.linalg.norm(person_vector)) if len(person_vector) > 0 else 0.0,
        "magnitude2": float(np.linalg.norm(secret_vector)) if len(secret_vector) > 0 else 0.0,
        "cosineDistance": 1.0 - narrative_similarity,
        "explanation": get_narrative_explanation(narrative_similarity)
    }
    
    # Convert QIDs to labels for display
    def get_labels(qids):
        labels = []
        for qid in qids:
            if qid in PERSON_CACHE:
                labels.append(PERSON_CACHE[qid]['label'])
            else:
                # If it's not a person QID, just use the QID itself
                labels.append(f"Property: {qid}")
        return labels
    
    match_details = {
        "factualMatches": get_labels(factual_matches),
        "factualNonMatches": get_labels(factual_non_matches),
        "relationalMatches": get_labels(relational_matches),
        "relationalNonMatches": get_labels(relational_non_matches),
        "narrativeSimilarity": narrative_similarity,
        "narrativeDetails": narrative_details
    }
    
    return {"matchDetails": match_details}
