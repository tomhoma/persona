#!/usr/bin/env python3
"""
Preview script that demonstrates the PersonaGuess game logic.
Simulates the backend ranking system locally.
"""
import sqlite3
import chromadb
import numpy as np
import os
import random
from typing import Dict, List

# Configuration (matching backend)
DB_DIR = "data"
SQLITE_PATH = os.path.join(DB_DIR, "persona.db")
CHROMA_PATH = os.path.join(DB_DIR, "chroma")
W_NARRATIVE = 0.5
W_FACTUAL = 0.3
W_RELATIONAL = 0.2

PERSON_CACHE: Dict[str, Dict] = {}

def jaccard_similarity(set1, set2):
    """Calculate Jaccard similarity between two sets."""
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union if union != 0 else 0

def cosine_similarity(vec1, vec2):
    """Calculate cosine similarity between two vectors."""
    if not isinstance(vec1, np.ndarray): 
        vec1 = np.array(vec1)
    if not isinstance(vec2, np.ndarray): 
        vec2 = np.array(vec2)
    if vec1.shape != vec2.shape or np.linalg.norm(vec1) == 0 or np.linalg.norm(vec2) == 0:
        return 0.0
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

def load_data_into_cache():
    """Load all person data into cache (same as backend startup)."""
    print("🔄 Loading data into cache...")
    
    if not os.path.exists(SQLITE_PATH):
        print(f"❌ ERROR: SQLite database not found at {SQLITE_PATH}")
        return False
    
    # Load from SQLite
    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.cursor()
    
    # Load basic person info
    cursor.execute("SELECT qid, label FROM persons")
    for qid, label in cursor.fetchall():
        PERSON_CACHE[qid] = {
            "qid": qid, 
            "label": label, 
            "factual_qids": set(), 
            "relational_qids": set(), 
            "narrative_vector": []
        }
    
    # Load properties
    cursor.execute("SELECT person_qid, property_qid, type FROM person_properties")
    for person_qid, prop_qid, prop_type in cursor.fetchall():
        if person_qid in PERSON_CACHE:
            if prop_type == 'factual':
                PERSON_CACHE[person_qid]["factual_qids"].add(prop_qid)
            elif prop_type == 'relational':
                PERSON_CACHE[person_qid]["relational_qids"].add(prop_qid)
    
    conn.close()
    print(f"✅ SQLite data loaded.")
    
    # Load narrative vectors from ChromaDB
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(name="narrative_vectors")
    chroma_data = collection.get(include=["embeddings"])
    
    for i, qid in enumerate(chroma_data['ids']):
        if qid in PERSON_CACHE:
            PERSON_CACHE[qid]['narrative_vector'] = chroma_data['embeddings'][i]
    
    print(f"✅ ChromaDB vectors loaded.")
    print(f"✅ Total persons loaded: {len(PERSON_CACHE)}")
    return True

def calculate_ranking(secret_qid: str):
    """Calculate ranking of all persons by similarity to secret person."""
    if secret_qid not in PERSON_CACHE:
        print(f"❌ Secret QID {secret_qid} not found.")
        return []
    
    secret_person = PERSON_CACHE[secret_qid]
    all_scores = []
    
    for qid, person_data in PERSON_CACHE.items():
        # Calculate narrative similarity (cosine of embeddings)
        sim_n = cosine_similarity(
            person_data.get('narrative_vector', []), 
            secret_person.get('narrative_vector', [])
        )
        
        # Calculate factual similarity (Jaccard of properties)
        sim_f = jaccard_similarity(
            person_data['factual_qids'], 
            secret_person['factual_qids']
        )
        
        # Calculate relational similarity (Jaccard of relationships)
        sim_r = jaccard_similarity(
            person_data['relational_qids'], 
            secret_person['relational_qids']
        )
        
        # Weighted final score
        final_score = (W_NARRATIVE * sim_n) + (W_FACTUAL * sim_f) + (W_RELATIONAL * sim_r)
        
        all_scores.append({
            "qid": qid, 
            "label": person_data["label"], 
            "score": final_score,
            "sim_narrative": sim_n,
            "sim_factual": sim_f,
            "sim_relational": sim_r
        })
    
    # Sort by score descending
    sorted_ranking = sorted(all_scores, key=lambda x: x['score'], reverse=True)
    
    # Add ranks
    for i, item in enumerate(sorted_ranking):
        item['rank'] = i + 1
    
    return sorted_ranking

def simulate_game():
    """Simulate a game round with random secret person."""
    print("\n" + "=" * 80)
    print("🎮 PERSONA GUESS GAME SIMULATION")
    print("=" * 80)
    
    # Pick a random secret person
    secret_qid = random.choice(list(PERSON_CACHE.keys()))
    secret_person = PERSON_CACHE[secret_qid]
    
    print(f"\n🎯 Secret Person: {secret_person['label']} ({secret_qid})")
    print(f"   Factual properties: {len(secret_person['factual_qids'])}")
    print(f"   Relational properties: {len(secret_person['relational_qids'])}")
    print(f"   Has narrative vector: {len(secret_person['narrative_vector']) > 0}")
    
    # Calculate rankings
    print(f"\n⏳ Calculating similarity scores for all {len(PERSON_CACHE)} persons...")
    ranking = calculate_ranking(secret_qid)
    
    # Show top 10 most similar
    print(f"\n🏆 TOP 10 MOST SIMILAR PERSONS:")
    print(f"{'Rank':<6} {'Score':<8} {'Narrative':<10} {'Factual':<10} {'Relational':<12} {'Name'}")
    print("-" * 80)
    
    for item in ranking[:10]:
        print(f"{item['rank']:<6} {item['score']:.4f}   "
              f"{item['sim_narrative']:.4f}     "
              f"{item['sim_factual']:.4f}     "
              f"{item['sim_relational']:.4f}      "
              f"{item['label']}")
    
    # Show some random guesses at different ranks
    print(f"\n🎲 SAMPLE GUESSES AT DIFFERENT RANKS:")
    sample_ranks = [50, 100, 500, 1000, 1500]
    
    for target_rank in sample_ranks:
        if target_rank <= len(ranking):
            item = ranking[target_rank - 1]
            print(f"\n   Rank #{item['rank']}: {item['label']}")
            print(f"   Score: {item['score']:.4f} (Narrative: {item['sim_narrative']:.4f}, "
                  f"Factual: {item['sim_factual']:.4f}, Relational: {item['sim_relational']:.4f})")
    
    # Show bottom 5 (least similar)
    print(f"\n❌ BOTTOM 5 LEAST SIMILAR PERSONS:")
    print(f"{'Rank':<6} {'Score':<8} {'Name'}")
    print("-" * 50)
    
    for item in ranking[-5:]:
        print(f"{item['rank']:<6} {item['score']:.4f}   {item['label']}")

def interactive_mode():
    """Interactive mode to test specific guesses."""
    print("\n" + "=" * 80)
    print("🎮 INTERACTIVE GAME MODE")
    print("=" * 80)
    
    # Pick a random secret person
    secret_qid = random.choice(list(PERSON_CACHE.keys()))
    secret_person = PERSON_CACHE[secret_qid]
    
    print(f"\n🤫 Secret person selected! (Hidden from player)")
    print(f"   Try to guess by entering person names or QIDs")
    print(f"   Type 'reveal' to see the answer, 'quit' to exit\n")
    
    # Calculate rankings once
    ranking = calculate_ranking(secret_qid)
    rank_map = {item['qid']: item for item in ranking}
    label_map = {item['label'].lower(): item for item in ranking}
    
    attempts = 0
    
    while True:
        guess = input("👉 Your guess (name or QID): ").strip()
        
        if guess.lower() == 'quit':
            print("\n👋 Thanks for playing!")
            break
        
        if guess.lower() == 'reveal':
            print(f"\n🎯 The secret person was: {secret_person['label']} ({secret_qid})")
            print(f"   Total attempts: {attempts}")
            break
        
        attempts += 1
        
        # Try to find the guess
        guess_item = None
        if guess in rank_map:
            guess_item = rank_map[guess]
        elif guess.lower() in label_map:
            guess_item = label_map[guess.lower()]
        else:
            # Partial match
            matches = [item for item in ranking if guess.lower() in item['label'].lower()]
            if matches:
                print(f"\n   Found {len(matches)} matches:")
                for i, match in enumerate(matches[:5], 1):
                    print(f"   {i}. {match['label']} ({match['qid']})")
                if len(matches) > 5:
                    print(f"   ... and {len(matches) - 5} more")
                continue
            else:
                print(f"   ❌ Person not found. Try again.")
                continue
        
        # Show result
        if guess_item['qid'] == secret_qid:
            print(f"\n   🎉 CORRECT! You guessed it in {attempts} attempts!")
            print(f"   The answer was: {secret_person['label']}")
            break
        else:
            print(f"\n   📊 Rank: #{guess_item['rank']} out of {len(ranking)}")
            print(f"   Similarity: {guess_item['score']:.4f}")
            
            # Give hints based on rank
            if guess_item['rank'] <= 10:
                print(f"   🔥 Very close! You're in the top 10!")
            elif guess_item['rank'] <= 50:
                print(f"   👍 Getting warmer! Top 50!")
            elif guess_item['rank'] <= 200:
                print(f"   🤔 You're in the top 200")
            elif guess_item['rank'] <= 500:
                print(f"   ❄️  Getting colder... top 500")
            else:
                print(f"   🥶 Very far away!")

def main():
    import sys
    
    print("\n🎮 PERSONA GUESS - Game Logic Preview\n")
    
    # Load data
    if not load_data_into_cache():
        return
    
    # Run simulation
    simulate_game()
    
    # Check if running interactively
    if sys.stdin.isatty():
        # Ask if user wants to play
        print("\n" + "=" * 80)
        play = input("\n🎮 Would you like to play interactively? (y/n): ").strip().lower()
        
        if play == 'y':
            interactive_mode()
    else:
        print("\n💡 Run this script directly in terminal for interactive mode!")
    
    print("\n✅ Preview complete!")

if __name__ == "__main__":
    main()

