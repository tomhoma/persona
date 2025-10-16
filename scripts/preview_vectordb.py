#!/usr/bin/env python3
"""
Script to preview and explore the ChromaDB vector database.
"""
import chromadb
import sqlite3
import json

# Configuration
DB_DIR = "data"
SQLITE_PATH = f"{DB_DIR}/persona.db"
CHROMA_PATH = f"{DB_DIR}/chroma"

def preview_chromadb():
    """Preview ChromaDB collection contents."""
    print("=" * 80)
    print("CHROMADB VECTOR DATABASE PREVIEW")
    print("=" * 80)
    
    # Connect to ChromaDB
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    
    # List all collections
    collections = chroma_client.list_collections()
    print(f"\n📁 Available collections: {[c.name for c in collections]}")
    
    if not collections:
        print("   ⚠️  No collections found!")
        return None
    
    # Use the first collection or look for narrative_summaries
    collection_name = "narrative_summaries"
    if collection_name in [c.name for c in collections]:
        collection = chroma_client.get_collection(collection_name)
    else:
        print(f"   Using collection: {collections[0].name}")
        collection = collections[0]
    
    # Get collection stats
    count = collection.count()
    print(f"\n📊 Collection Statistics:")
    print(f"   Total documents: {count}")
    
    # Get a few sample documents
    print(f"\n📝 Sample Documents (first 5):")
    results = collection.get(limit=5, include=['documents', 'metadatas'])
    
    for i, (doc_id, doc, metadata) in enumerate(zip(results['ids'], results['documents'], results['metadatas']), 1):
        print(f"\n   {i}. QID: {doc_id}")
        if metadata:
            print(f"      Label: {metadata.get('label', 'N/A')}")
        if doc:
            print(f"      Summary: {doc[:200]}..." if len(doc) > 200 else f"      Summary: {doc}")
        else:
            print(f"      Summary: (empty)")
    
    return collection

def preview_sqlite():
    """Preview SQLite database contents."""
    print("\n" + "=" * 80)
    print("SQLITE DATABASE PREVIEW")
    print("=" * 80)
    
    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.cursor()
    
    # Get table info
    print(f"\n📊 Database Statistics:")
    
    # Count persons
    cursor.execute("SELECT COUNT(*) FROM persons")
    person_count = cursor.fetchone()[0]
    print(f"   Total persons: {person_count}")
    
    # Count properties
    cursor.execute("SELECT COUNT(*) FROM person_properties")
    prop_count = cursor.fetchone()[0]
    print(f"   Total property relationships: {prop_count}")
    
    # Property type breakdown
    cursor.execute("SELECT type, COUNT(*) FROM person_properties GROUP BY type")
    print(f"\n   Property breakdown:")
    for prop_type, count in cursor.fetchall():
        print(f"      {prop_type}: {count}")
    
    # Sample persons
    print(f"\n📝 Sample Persons (first 5):")
    cursor.execute("SELECT qid, label, thwiki_title FROM persons LIMIT 5")
    for i, (qid, label, wiki_title) in enumerate(cursor.fetchall(), 1):
        print(f"\n   {i}. {label}")
        print(f"      QID: {qid}")
        print(f"      Thai Wikipedia: {wiki_title}")
        
        # Get their properties
        cursor.execute("""
            SELECT property_qid, type 
            FROM person_properties 
            WHERE person_qid = ?
        """, (qid,))
        props = cursor.fetchall()
        if props:
            factual = [p[0] for p in props if p[1] == 'factual']
            relational = [p[0] for p in props if p[1] == 'relational']
            if factual:
                print(f"      Factual properties: {', '.join(factual)}")
            if relational:
                print(f"      Relational properties: {', '.join(relational)}")
    
    conn.close()

def test_similarity_search(collection):
    """Test vector similarity search."""
    print("\n" + "=" * 80)
    print("VECTOR SIMILARITY SEARCH TEST")
    print("=" * 80)
    
    test_queries = [
        "นักร้องเพลงป๊อป",  # Pop singer
        "นักการเมือง",      # Politician
        "นักแสดง",           # Actor
    ]
    
    for query in test_queries:
        print(f"\n🔍 Query: '{query}'")
        results = collection.query(
            query_texts=[query],
            n_results=3,
            include=['documents', 'metadatas', 'distances']
        )
        
        print(f"   Top 3 similar people:")
        for i, (doc_id, metadata, distance) in enumerate(zip(
            results['ids'][0], 
            results['metadatas'][0],
            results['distances'][0]
        ), 1):
            label = metadata.get('label', 'N/A') if metadata else 'N/A'
            print(f"      {i}. {label} (QID: {doc_id})")
            print(f"         Similarity score: {1 - distance:.4f}")

def main():
    print("\n🔍 Exploring Vector Database\n")
    
    try:
        # Preview ChromaDB
        collection = preview_chromadb()
        
        # Preview SQLite
        preview_sqlite()
        
        # Test similarity search
        if collection:
            test_similarity_search(collection)
        else:
            print("\n⚠️  Skipping similarity search (no collection available)")
        
        print("\n" + "=" * 80)
        print("✅ Preview complete!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

