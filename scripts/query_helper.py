import sqlite3
import chromadb
import numpy as np
from sentence_transformers import SentenceTransformer

class PersonaRelationshipQuery:
    """Helper class to query relationships for the Persona Guess game."""
    
    def __init__(self, sqlite_path="data/persona.db", chroma_path="data/chroma"):
        self.conn = sqlite3.connect(sqlite_path)
        self.chroma_client = chromadb.PersistentClient(path=chroma_path)
        self.collection = self.chroma_client.get_collection("narrative_vectors")
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
    
    def get_person_details(self, qid):
        """Get all details for a specific person."""
        cursor = self.conn.cursor()
        
        # Basic info
        person = cursor.execute(
            "SELECT * FROM persons WHERE qid = ?", (qid,)
        ).fetchone()
        
        if not person:
            return None
        
        # Properties
        properties = cursor.execute(
            "SELECT property_code, property_qid, label, type FROM person_properties WHERE person_qid = ?",
            (qid,)
        ).fetchall()
        
        # Direct relationships
        relationships = cursor.execute("""
            SELECT p2.qid, p2.label, r.relationship_type, r.property_code 
            FROM person_relationships r
            JOIN persons p2 ON r.person2_qid = p2.qid
            WHERE r.person1_qid = ?
        """, (qid,)).fetchall()
        
        # Reverse relationships (people who reference this person)
        reverse_relationships = cursor.execute("""
            SELECT p1.qid, p1.label, r.relationship_type, r.property_code 
            FROM person_relationships r
            JOIN persons p1 ON r.person1_qid = p1.qid
            WHERE r.person2_qid = ?
        """, (qid,)).fetchall()
        
        return {
            'person': person,
            'properties': properties,
            'relationships': relationships,
            'reverse_relationships': reverse_relationships
        }
    
    def calculate_similarity_score(self, person1_qid, person2_qid):
        """
        Calculate comprehensive similarity score between two persons.
        Returns scores for narrative, factual, and relational similarity.
        """
        
        # 1. Narrative Similarity (using ChromaDB vectors)
        narrative_score = self._calculate_narrative_similarity(person1_qid, person2_qid)
        
        # 2. Factual Similarity (shared factual properties)
        factual_score = self._calculate_factual_similarity(person1_qid, person2_qid)
        
        # 3. Relational Similarity (shared relationships and network overlap)
        relational_score = self._calculate_relational_similarity(person1_qid, person2_qid)
        
        # Combined score with weights
        total_score = (
            narrative_score * 0.4 +
            factual_score * 0.3 +
            relational_score * 0.3
        )
        
        return {
            'narrative': narrative_score,
            'factual': factual_score,
            'relational': relational_score,
            'total': total_score,
            'details': {
                'shared_properties': self._get_shared_properties(person1_qid, person2_qid),
                'shared_relationships': self._get_shared_relationships(person1_qid, person2_qid),
                'network_overlap': self._get_network_overlap(person1_qid, person2_qid)
            }
        }
    
    def _calculate_narrative_similarity(self, qid1, qid2):
        """Calculate cosine similarity between narrative vectors."""
        try:
            vec1 = self.collection.get(ids=[qid1], include=['embeddings'])['embeddings'][0]
            vec2 = self.collection.get(ids=[qid2], include=['embeddings'])['embeddings'][0]
            
            # Cosine similarity
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 * norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            return max(0.0, similarity)  # Ensure non-negative
        except:
            return 0.0
    
    def _calculate_factual_similarity(self, qid1, qid2):
        """Calculate similarity based on shared factual properties."""
        cursor = self.conn.cursor()
        
        # Get factual properties for both persons
        props1 = set(cursor.execute(
            "SELECT property_qid FROM person_properties WHERE person_qid = ? AND type = 'factual'",
            (qid1,)
        ).fetchall())
        
        props2 = set(cursor.execute(
            "SELECT property_qid FROM person_properties WHERE person_qid = ? AND type = 'factual'",
            (qid2,)
        ).fetchall())
        
        if not props1 or not props2:
            return 0.0
        
        # Jaccard similarity
        intersection = len(props1.intersection(props2))
        union = len(props1.union(props2))
        
        return intersection / union if union > 0 else 0.0
    
    def _calculate_relational_similarity(self, qid1, qid2):
        """
        Calculate similarity based on relationships.
        Considers: shared connections, similar relationship patterns, network distance.
        """
        cursor = self.conn.cursor()
        
        # Get all connected persons for each
        connections1 = set(cursor.execute("""
            SELECT person2_qid FROM person_relationships WHERE person1_qid = ?
            UNION
            SELECT person1_qid FROM person_relationships WHERE person2_qid = ?
        """, (qid1, qid1)).fetchall())
        
        connections2 = set(cursor.execute("""
            SELECT person2_qid FROM person_relationships WHERE person1_qid = ?
            UNION
            SELECT person1_qid FROM person_relationships WHERE person2_qid = ?
        """, (qid2, qid2)).fetchall())
        
        if not connections1 and not connections2:
            return 0.0
        
        # Check for direct connection
        if (qid2,) in connections1 or (qid1,) in connections2:
            return 1.0  # Directly connected
        
        # Calculate network overlap
        if connections1 and connections2:
            shared = len(connections1.intersection(connections2))
            total = len(connections1.union(connections2))
            
            if total > 0:
                overlap_score = shared / total
                
                # Boost score if they have many shared connections
                if shared >= 2:
                    overlap_score = min(1.0, overlap_score * 1.5)
                
                return overlap_score
        
        return 0.0
    
    def _get_shared_properties(self, qid1, qid2):
        """Get list of shared properties between two persons."""
        cursor = self.conn.cursor()
        
        shared = cursor.execute("""
            SELECT DISTINCT p1.property_code, p1.property_qid, p1.label
            FROM person_properties p1
            JOIN person_properties p2 ON p1.property_qid = p2.property_qid AND p1.property_code = p2.property_code
            WHERE p1.person_qid = ? AND p2.person_qid = ?
        """, (qid1, qid2)).fetchall()
        
        return shared
    
    def _get_shared_relationships(self, qid1, qid2):
        """Find people that both persons are connected to."""
        cursor = self.conn.cursor()
        
        shared = cursor.execute("""
            SELECT DISTINCT p.qid, p.label
            FROM (
                SELECT person2_qid as qid FROM person_relationships WHERE person1_qid = ?
                UNION
                SELECT person1_qid as qid FROM person_relationships WHERE person2_qid = ?
            ) t1
            JOIN (
                SELECT person2_qid as qid FROM person_relationships WHERE person1_qid = ?
                UNION
                SELECT person1_qid as qid FROM person_relationships WHERE person2_qid = ?
            ) t2 ON t1.qid = t2.qid
            JOIN persons p ON p.qid = t1.qid
        """, (qid1, qid1, qid2, qid2)).fetchall()
        
        return shared
    
    def _get_network_overlap(self, qid1, qid2):
        """Calculate the network distance and overlap between two persons."""
        # This could be expanded to calculate shortest path in the relationship graph
        shared_connections = self._get_shared_relationships(qid1, qid2)
        return {
            'shared_count': len(shared_connections),
            'shared_persons': shared_connections[:10]  # Limit for display
        }
    
    def find_similar_persons(self, target_qid, limit=10):
        """Find the most similar persons to a target."""
        cursor = self.conn.cursor()
        
        # Get all person QIDs
        all_persons = cursor.execute("SELECT qid FROM persons WHERE qid != ?", (target_qid,)).fetchall()
        
        similarities = []
        for (other_qid,) in all_persons:
            score = self.calculate_similarity_score(target_qid, other_qid)
            similarities.append({
                'qid': other_qid,
                'scores': score
            })
        
        # Sort by total score
        similarities.sort(key=lambda x: x['scores']['total'], reverse=True)
        
        return similarities[:limit]
    
    def get_game_hints(self, secret_qid, guess_qid):
        """
        Generate hints for the game based on how close the guess is.
        Returns structured hints without revealing the answer.
        """
        similarity = self.calculate_similarity_score(secret_qid, guess_qid)
        details1 = self.get_person_details(secret_qid)
        details2 = self.get_person_details(guess_qid)
        
        hints = []
        
        # Narrative similarity hint
        if similarity['narrative'] > 0.8:
            hints.append("🔥 Very similar narrative/biography!")
        elif similarity['narrative'] > 0.6:
            hints.append("🌟 Similar themes in their stories")
        elif similarity['narrative'] > 0.4:
            hints.append("💫 Some narrative similarities")
        
        # Factual similarity hint
        if similarity['factual'] > 0.7:
            hints.append("✅ Many shared attributes!")
        elif similarity['factual'] > 0.4:
            hints.append("📊 Some shared characteristics")
        
        # Relational similarity hint
        if similarity['relational'] > 0.8:
            hints.append("🔗 Very closely connected!")
        elif similarity['relational'] > 0.5:
            hints.append("🤝 Connected through mutual relationships")
        elif similarity['relational'] > 0.2:
            hints.append("👥 Some network overlap")
        
        # Specific hints based on shared properties
        shared_props = similarity['details']['shared_properties']
        if shared_props:
            prop_types = set(p[0] for p in shared_props)
            if 'P106' in prop_types:
                hints.append("💼 Same profession/occupation")
            if 'P69' in prop_types:
                hints.append("🎓 Attended same institution")
            if 'P54' in prop_types or 'P108' in prop_types:
                hints.append("🏢 Worked for same organization")
        
        # Network distance hint
        shared_connections = similarity['details']['shared_relationships']
        if shared_connections:
            if len(shared_connections) >= 3:
                hints.append(f"👫 Connected through {len(shared_connections)} mutual people")
            else:
                hints.append("🔍 They know some of the same people")
        
        return {
            'hints': hints,
            'similarity_score': similarity['total'],
            'ranking_info': {
                'narrative': f"{similarity['narrative']*100:.1f}%",
                'factual': f"{similarity['factual']*100:.1f}%",
                'relational': f"{similarity['relational']*100:.1f}%"
            }
        }
    
    def close(self):
        """Close database connections."""
        self.conn.close()


# Example usage for testing
if __name__ == "__main__":
    query = PersonaRelationshipQuery()
    
    # Test with a sample person (replace with actual QID from your database)
    test_qid = "Q1234567"  # Replace with real QID
    
    details = query.get_person_details(test_qid)
    if details:
        print(f"Person: {details['person']}")
        print(f"Relationships: {len(details['relationships'])}")
        print(f"Reverse relationships: {len(details['reverse_relationships'])}")
        
        # Find similar persons
        similar = query.find_similar_persons(test_qid, limit=5)
        print("\nMost similar persons:")
        for s in similar:
            print(f"  {s['qid']}: {s['scores']['total']:.3f}")
    
    query.close()