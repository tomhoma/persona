#!/bin/bash
set -e

echo "--- Starting Full Project Build ---"

# --- 1. Create Directory Structure ---
echo "Creating directory structure..."
mkdir -p backend
mkdir -p scripts
mkdir -p frontend/src/components
mkdir -p data

# --- 2. Create Backend Files ---
echo "Creating backend files..."

# requirements.txt
cat << 'EOF' > requirements.txt
fastapi
uvicorn[standard]
requests
sqlite3
chromadb
numpy
sentence-transformers
SPARQLWrapper
tqdm
EOF

# backend/main.py
cat << 'EOF' > backend/main.py
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

class Person(BaseModel):
    qid: str
    label: str

class DailyRanking(Person):
    rank: int
    score: float

@app.on_event("startup")
def load_data_into_cache():
    print("INFO: --- Starting Data Loading ---")
    if not os.path.exists(SQLITE_PATH):
        print("ERROR: SQLite database not found.")
        return
    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT qid, label FROM persons")
    for qid, label in cursor.fetchall():
        PERSON_CACHE[qid] = {"qid": qid, "label": label, "factual_qids": set(), "relational_qids": set()}
    cursor.execute("SELECT person_qid, property_qid, type FROM person_properties")
    for person_qid, prop_qid, prop_type in cursor.fetchall():
        if person_qid in PERSON_CACHE:
            if prop_type == 'factual':
                PERSON_CACHE[person_qid]["factual_qids"].add(prop_qid)
            elif prop_type == 'relational':
                PERSON_CACHE[person_qid]["relational_qids"].add(prop_qid)
    conn.close()
    print("INFO: SQLite data loaded.")

    if not os.path.exists(CHROMA_PATH):
        print("ERROR: ChromaDB not found.")
        return
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection(name="narrative_vectors")
    chroma_data = collection.get(include=["embeddings"])
    for i, qid in enumerate(chroma_data['ids']):
        if qid in PERSON_CACHE:
            PERSON_CACHE[qid]['narrative_vector'] = chroma_data['embeddings'][i]
    print(f"INFO: --- Data Loading Complete. Loaded {len(PERSON_CACHE)} persons. ---")

@app.get("/persons", response_model=List[Person], tags=["Game Data"])
async def get_all_persons():
    if not PERSON_CACHE:
        raise HTTPException(status_code=503, detail="Data not loaded.")
    return [{"qid": data["qid"], "label": data["label"]} for data in PERSON_CACHE.values()]

@app.get("/daily_ranking", response_model=List[DailyRanking], tags=["Game Logic"])
async def get_daily_ranking(secret_qid: str):
    if secret_qid not in PERSON_CACHE:
        raise HTTPException(status_code=404, detail="Secret QID not found.")
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
EOF

# --- 3. Create Data Processing Script ---
echo "Creating data processing script..."
cat << 'EOF' > scripts/process_data.py
import sys, os, json, time, requests, sqlite3, chromadb, numpy as np
from SPARQLWrapper import SPARQLWrapper, JSON
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import logging

DB_DIR = "data"
SQLITE_PATH = os.path.join(DB_DIR, "persona.db")
CHROMA_PATH = os.path.join(DB_DIR, "chroma")
WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
MODEL_NAME = 'all-MiniLM-L6-v2'
USER_AGENT = "PersonaGuessApp/1.0"
FACTUAL_PROPERTIES = ["P106", "P27", "P166"]
RELATIONAL_PROPERTIES = ["P737", "P1066", "P800"]
SEED_OCCUPATIONS = ["Q82955", "Q483501", "Q901", "Q36180", "Q33999", "Q2066131", "Q18814623", "Q177220", "Q49757", "Q169470"]
LIMIT_PER_OCCUPATION = 50
MIN_SITELINKS = 25

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
os.makedirs(DB_DIR, exist_ok=True)

def setup_databases():
    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS persons (qid TEXT PRIMARY KEY, label TEXT, enwiki_title TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS person_properties (person_qid TEXT, property_qid TEXT, type TEXT, PRIMARY KEY (person_qid, property_qid))")
    conn.commit()
    conn.close()
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(name="narrative_vectors")
    logging.info("Databases initialized.")
    return client, collection

def fetch_single_occupation(occupation_qid, sparql):
    query = f"SELECT ?item ?itemLabel ?enwiki_title WHERE {{ ?item wdt:P106/wdt:P279* wd:{occupation_qid}. ?item wikibase:sitelinks ?sitelinkCount. ?enwiki schema:about ?item; schema:isPartOf <https://en.wikipedia.org/>; schema:name ?enwiki_title. FILTER(?sitelinkCount > {MIN_SITELINKS}) }} LIMIT {LIMIT_PER_OCCUPATION}"
    try:
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()["results"]["bindings"]
        return [{"qid": r["item"]["value"].split("/")[-1], "label": r["itemLabel"]["value"], "enwiki_title": r["enwiki_title"]["value"]} for r in results]
    except Exception as e:
        logging.error(f"Failed to fetch {occupation_qid}: {e}")
        return []

def get_wikipedia_summary(title, session):
    params = {"action":"query", "format":"json", "titles":title, "prop":"extracts", "exintro":True, "explaintext":True, "redirects":1}
    try:
        r = session.get(WIKIPEDIA_API_URL, params=params, timeout=10)
        r.raise_for_status()
        pages = r.json()["query"]["pages"]
        return next((pages[p].get("extract", "") for p in pages if p != "-1"), "")
    except Exception: return ""

def get_wikidata_details(qid, sparql):
    prop_str = " ".join([f"wdt:{p}" for p in FACTUAL_PROPERTIES + RELATIONAL_PROPERTIES])
    query = f"SELECT ?prop ?value WHERE {{ VALUES ?item {{wd:{qid}}} VALUES ?prop {{ {prop_str} }} ?item ?prop ?value. FILTER(isIRI(?value)) }}"
    try:
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()["results"]["bindings"]
        details = {}
        for r in results:
            prop, val_qid = r['prop']['value'].split('/')[-1], r['value']['value'].split('/')[-1]
            if prop not in details: details[prop] = []
            if val_qid not in details[prop]: details[prop].append(val_qid)
        return details
    except Exception: return {}

def main(job_index):
    chroma_client, narrative_collection = setup_databases()
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    model = SentenceTransformer(MODEL_NAME)
    sparql = SPARQLWrapper(WIKIDATA_SPARQL_URL, agent=USER_AGENT)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    occupation_qid = SEED_OCCUPATIONS[job_index]
    logging.info(f"Processing occupation {job_index+1}/{len(SEED_OCCUPATIONS)}: {occupation_qid}")
    persons = fetch_single_occupation(occupation_qid, sparql)
    if not persons: return

    for person in tqdm(persons, desc=f"Processing {occupation_qid}"):
        qid = person['qid']
        if sqlite_conn.execute("SELECT 1 FROM persons WHERE qid=?", (qid,)).fetchone():
            logging.info(f"Skipping {qid}, already in DB.")
            continue

        summary = get_wikipedia_summary(person['enwiki_title'], session)
        details = get_wikidata_details(qid, sparql)
        narrative_vector = model.encode(summary).tolist() if summary else []
        factual_qids = {qid for p in FACTUAL_PROPERTIES if p in details for qid in details[p]}
        relational_qids = {qid for p in RELATIONAL_PROPERTIES if p in details for qid in details[p]}

        cursor = sqlite_conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO persons (qid, label, enwiki_title) VALUES (?, ?, ?)", (qid, person['label'], person['enwiki_title']))
        prop_data = [(qid, pq, 'factual') for pq in factual_qids] + [(qid, pq, 'relational') for pq in relational_qids]
        cursor.executemany("INSERT OR IGNORE INTO person_properties (person_qid, property_qid, type) VALUES (?, ?, ?)", prop_data)
        if narrative_vector:
            narrative_collection.add(embeddings=[narrative_vector], ids=[qid])
        sqlite_conn.commit()
        logging.info(f"Stored {qid} ({person['label']}).")
        time.sleep(1)

    sqlite_conn.close()
    logging.info("Batch complete.")

if __name__ == "__main__":
    job_index = int(sys.argv[1])
    main(job_index)
EOF

# --- 4. Create Frontend Files ---
echo "Creating frontend files..."

# frontend/package.json
cat << 'EOF' > frontend/package.json
{
  "name": "frontend",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "lint": "eslint . --ext js,jsx --report-unused-disable-directives --max-warnings 0",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "axios": "^1.6.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.15",
    "@types/react-dom": "^18.2.7",
    "@vitejs/plugin-react": "^4.0.3",
    "eslint": "^8.45.0",
    "eslint-plugin-react": "^7.32.2",
    "eslint-plugin-react-hooks": "^4.6.0",
    "eslint-plugin-react-refresh": "^0.4.3",
    "vite": "^4.4.5"
  }
}
EOF

# frontend/vite.config.js
cat << 'EOF' > frontend/vite.config.js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
})
EOF

# frontend/index.html
cat << 'EOF' > frontend/index.html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>PersonaGuess</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
EOF

# frontend/src/main.jsx
cat << 'EOF' > frontend/src/main.jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
EOF

# frontend/src/index.css
cat << 'EOF' > frontend/src/index.css
:root {
  font-family: Inter, system-ui, Avenir, Helvetica, Arial, sans-serif;
  line-height: 1.5;
  font-weight: 400;

  color-scheme: light dark;
  color: rgba(255, 255, 255, 0.87);
  background-color: #242424;

  font-synthesis: none;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

body {
  margin: 0;
  display: flex;
  place-items: center;
  min-width: 320px;
  min-height: 100vh;
}

#root {
  max-width: 1280px;
  margin: 0 auto;
  padding: 2rem;
  text-align: center;
}
EOF

# frontend/src/App.jsx
cat << 'EOF' > frontend/src/App.jsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import GuessInput from './components/GuessInput';
import GuessList from './components/GuessList';
import './App.css';

const API_URL = import.meta.env.PROD ? '' : 'http://localhost:8000';
const SECRET_PERSON_QID = 'Q307'; // Galileo Galilei

function App() {
  const [allPersons, setAllPersons] = useState([]);
  const [dailyRanking, setDailyRanking] = useState(null);
  const [guesses, setGuesses] = useState([]);
  const [isGameWon, setIsGameWon] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchGameData = async () => {
      try {
        const personsPromise = axios.get(`${API_URL}/persons`);
        const rankingPromise = axios.get(`${API_URL}/daily_ranking?secret_qid=${SECRET_PERSON_QID}`);
        const [personsResponse, rankingResponse] = await Promise.all([personsPromise, rankingPromise]);
        setAllPersons(personsResponse.data);
        const rankingMap = new Map(rankingResponse.data.map(p => [p.qid, p]));
        setDailyRanking(rankingMap);
      } catch (err) {
        setError("Could not connect to the game server.");
      } finally {
        setIsLoading(false);
      }
    };
    fetchGameData();
  }, []);

  const handleGuess = (guessedPerson) => {
    if (isGameWon || !dailyRanking || !guessedPerson) return;
    const result = dailyRanking.get(guessedPerson.qid);
    if (!result) return;
    const newGuesses = [...guesses, result];
    setGuesses(newGuesses.sort((a, b) => a.rank - b.rank));
    if (result.qid === SECRET_PERSON_QID) setIsGameWon(true);
  };

  return (
    <div className="app-container">
      <header className="app-header"><h1>PersonaGuess</h1><p>Guess the secret person of the day!</p></header>
      <main>
        {isLoading && <p>Loading game data...</p>}
        {error && <p className="error-message">{error}</p>}
        {isGameWon && <div className="win-message"><h2>Congratulations!</h2><p>You found the secret person: {dailyRanking.get(SECRET_PERSON_QID).label}</p></div>}
        {!isLoading && !error && (
          <>
            <GuessInput allPersons={allPersons} onGuess={handleGuess} disabled={isGameWon} />
            <GuessList guesses={guesses} />
          </>
        )}
      </main>
    </div>
  );
}
export default App;
EOF

# frontend/src/App.css
cat << 'EOF' > frontend/src/App.css
.app-container { max-width: 600px; margin: auto; }
.app-header { text-align: center; margin-bottom: 2rem; }
.app-header h1 { color: #646cff; }
.guess-input-container { margin-bottom: 1.5rem; position: relative; }
.guess-input { width: 100%; padding: 0.75rem; font-size: 1rem; border-radius: 8px; border: 1px solid #555; background-color: #333; color: #fff; box-sizing: border-box; }
.autocomplete-suggestions { list-style: none; padding: 0; margin: 0; background-color: #333; border: 1px solid #444; border-top: none; border-radius: 0 0 8px 8px; max-height: 200px; overflow-y: auto; position: absolute; width: 100%; z-index: 10; }
.autocomplete-suggestions li { padding: 0.75rem; text-align: left; cursor: pointer; }
.autocomplete-suggestions li:hover { background-color: #535bf2; }
.guess-list-header, .guess-list-item { display: grid; grid-template-columns: 80px 1fr; padding: 0.5rem 1rem; text-align: left; }
.guess-list-header { font-weight: bold; background-color: #333; }
.item-rank { font-weight: bold; }
.rank-gold { background-color: #ffd700; color: #333; }
.rank-green { background-color: #2f9e44; }
.rank-yellow { background-color: #fcc419; color: #333; }
.rank-red { background-color: #c92a2a; }
.error-message { color: #e03131; }
.win-message { padding: 1rem; background-color: #2f9e44; border-radius: 8px; margin-bottom: 1.5rem; }
EOF

# frontend/src/components/GuessInput.jsx
cat << 'EOF' > frontend/src/components/GuessInput.jsx
import React, { useState } from 'react';
const GuessInput = ({ allPersons, onGuess, disabled }) => {
  const [inputValue, setInputValue] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const handleInputChange = (e) => {
    const value = e.target.value;
    setInputValue(value);
    if (value.length > 1 && !disabled) {
      setSuggestions(allPersons.filter((p) => p.label.toLowerCase().includes(value.toLowerCase())).slice(0, 10));
    } else {
      setSuggestions([]);
    }
  };
  const handleSuggestionClick = (person) => {
    setInputValue('');
    setSuggestions([]);
    onGuess(person);
  };
  return (
    <div className="guess-input-container">
      <input type="text" placeholder={disabled ? "You found it!" : "Enter a person's name..."} className="guess-input" value={inputValue} onChange={handleInputChange} disabled={disabled} />
      {suggestions.length > 0 && (
        <ul className="autocomplete-suggestions">
          {suggestions.map((p) => (<li key={p.qid} onClick={() => handleSuggestionClick(p)}>{p.label}</li>))}
        </ul>
      )}
    </div>
  );
};
export default GuessInput;
EOF

# frontend/src/components/GuessList.jsx
cat << 'EOF' > frontend/src/components/GuessList.jsx
import React from 'react';
const getRankColor = (rank) => {
  if (rank === 1) return 'rank-gold';
  if (rank <= 300) return 'rank-green';
  if (rank <= 1500) return 'rank-yellow';
  return 'rank-red';
};
const GuessList = ({ guesses }) => {
  return (
    <div className="guess-list-container">
      <div className="guess-list-header"><div>Rank</div><div>Name</div></div>
      <div className="guess-list-body">
        {guesses.length === 0 ? (<div className="guess-list-empty">Your guesses will appear here.</div>) : (
          guesses.map((guess) => (
            <div key={guess.qid} className={`guess-list-item ${getRankColor(guess.rank)}`}>
              <div className="item-rank">{guess.rank}</div>
              <div className="item-label">{guess.label}</div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
export default GuessList;
EOF

# --- 5. Create Docker and Documentation Files ---
echo "Creating Docker and documentation files..."

# backend.Dockerfile
cat << 'EOF' > backend.Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ /app/backend/
COPY scripts/ /app/scripts/
COPY data/ /app/data/
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

# frontend.Dockerfile
cat << 'EOF' > frontend.Dockerfile
# Stage 1: Build
FROM node:18-alpine AS build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# Stage 2: Serve
FROM nginx:1.21-alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
EOF

# docker-compose.yml
cat << 'EOF' > docker-compose.yml
version: '3.8'
services:
  backend:
    build:
      context: .
      dockerfile: backend.Dockerfile
    restart: always
    volumes:
      - ./data:/app/data
    ports:
      - "8000:8000"
  frontend:
    build:
      context: .
      dockerfile: frontend.Dockerfile
    restart: always
    ports:
      - "80:80"
    depends_on:
      - backend
EOF

# README.md
cat << 'EOF' > README.md
# PersonaGuess
A daily guessing game to find a secret famous person based on contextual similarity.
See [DEPLOY.md](DEPLOY.md) for deployment instructions.

## Local Development
1. `pip install -r requirements.txt`
2. `cd frontend && npm install && cd ..`
3. Build the database: `for i in {0..9}; do python3 scripts/process_data.py $i; done`
4. Run backend: `uvicorn backend.main:app --host 0.0.0.0 --port 8000`
5. In a new terminal, run frontend: `cd frontend && npm run dev`
EOF

# DEPLOY.md
cat << 'EOF' > DEPLOY.md
# Production Deployment Guide (VPS with Docker)
1. Install Docker & Docker Compose on your VPS.
2. Copy all project files to your VPS.
3. **Build the database on the VPS:** `for i in {0..9}; do python3 scripts/process_data.py $i; done`
4. **Build and run containers:** `sudo docker-compose up --build -d`
5. Access the game at your VPS IP address.
EOF

# .gitignore
cat << 'EOF' > .gitignore
# Data
data/
# Python
__pycache__/
*.pyc
venv/
env/
# Node
frontend/node_modules/
frontend/dist/
# Logs
*.log
# IDE
.idea/
.vscode/
*.DS_Store
EOF

echo "--- Project Build Complete ---"
echo "Next steps:"
echo "1. Run './build_project.sh' to create all files."
echo "2. Run 'chmod +x build_project.sh' if needed."
echo "3. Follow instructions in README.md and DEPLOY.md"