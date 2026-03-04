import json
import os
import pickle
import sys
from typing import List, Dict, Any

sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # type: ignore

try:
    import faiss     # type: ignore
    import numpy as np # type: ignore
    from sentence_transformers import SentenceTransformer  # type: ignore
except ImportError:
    print("Error: Missing required packages. Please run:")
    print("pip install -r phase2_indexing/requirements.txt")
    exit(1)


# Path configurations
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STRUCTURED_DATA_PATH = os.path.join(BASE_DIR, "phase1_ingestion", "data", "structured", "ppfas_schemes.json")
FAISS_DB_DIR = os.path.join(BASE_DIR, "phase2_indexing", "faiss_db")
INDEX_PATH = os.path.join(FAISS_DB_DIR, "ppfas_index.faiss")
METADATA_PATH = os.path.join(FAISS_DB_DIR, "ppfas_metadata.pkl")


class SchemeChunker:
    """Converts structured JSON scheme data into atomic semantic sentences for retrieval."""
    
    @staticmethod
    def generate_chunks(scheme: Dict[str, Any]) -> List[Dict[str, Any]]:
        chunks = []
        s_name = scheme["scheme_name"]
        
        # Define atomic sentence templates for each factual attribute
        mapping = [
            ("expense_ratio", f"The expense ratio of {s_name} is {scheme.get('expense_ratio')}."),
            ("minimum_sip", f"The minimum SIP investment for {s_name} is {scheme.get('minimum_sip')}."),
            ("minimum_lumpsum", f"The minimum lumpsum investment for {s_name} is {scheme.get('minimum_lumpsum')}."),
            ("exit_load", f"The exit load structure for {s_name} is as follows: {scheme.get('exit_load')}."),
            ("lock_in_period", f"The lock-in period for {s_name} is {scheme.get('lock_in_period')}."),
            ("riskometer_category", f"The risk category (riskometer) of {s_name} is {scheme.get('riskometer_category')} Risk."),
            ("benchmark_index", f"The benchmark index for {s_name} is the {scheme.get('benchmark_index')}."),
            ("fund_category", f"{s_name} belongs to the {scheme.get('fund_category')} mutual fund category.")
        ]
        
        for field_name, sentence in mapping:
            # Skip building chunks for empty or "Not specified" data to prevent answering with null values
            val = scheme.get(field_name)
            if not val or val == "Not specified":
                continue
                
            chunks.append({
                "id": f"{scheme['scheme_id']}_{field_name}",
                "text": sentence,
                "metadata": {
                    "scheme_id": scheme["scheme_id"],
                    "scheme_name": s_name,
                    "field_type": field_name,
                    "source_url": scheme["source_url"],
                    "last_updated": scheme.get("last_updated", "Unknown")
                }
            })
            
        return chunks


def build_vector_store():
    print(f"Loading data from {STRUCTURED_DATA_PATH}...")
    
    if not os.path.exists(STRUCTURED_DATA_PATH):
        print("Error: Structured JSON data not found. Run Phase 1 scraper first.")
        return
        
    with open(STRUCTURED_DATA_PATH, "r", encoding="utf-8") as f:
        schemes = json.load(f)
        
    print(f"Loaded {len(schemes)} schemes. Generating atomic chunks...")
    
    all_chunks = []
    for scheme in schemes:
        chunks = SchemeChunker.generate_chunks(scheme)
        all_chunks.extend(chunks)
        
    print(f"Generated {len(all_chunks)} factual chunks.")

    print("Loading embedding model (sentence-transformers/all-MiniLM-L6-v2) ...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    
    print("Embedding chunks (this may take a few seconds)...")
    texts = [c["text"] for c in all_chunks]
    
    # Generate embeddings and normalize them for Cosine Similarity inside FAISS IP (Inner Product) index
    embeddings = model.encode(texts, show_progress_bar=True)
    faiss.normalize_L2(embeddings)
    
    print(f"Initializing FAISS at {FAISS_DB_DIR}...")
    os.makedirs(FAISS_DB_DIR, exist_ok=True)
    
    # MiniLM-L6-v2 outputs 384-dimensional vectors
    dimension = embeddings.shape[1]
    
    # IndexFlatIP calculates inner product, which equals cosine similarity when vectors are normalized
    index = faiss.IndexFlatIP(dimension)
    
    print(f"Inserting {len(all_chunks)} records into FAISS...")
    index.add(embeddings)
    
    # Save the index to disk
    faiss.write_index(index, INDEX_PATH)
    
    # Save the chunk strings and metadata in a parallel array to disk
    with open(METADATA_PATH, "wb") as f:
        pickle.dump(all_chunks, f)
        
    validate_collection(index, all_chunks)


def validate_collection(index: Any, meta_array: List[Dict[str, Any]]) -> None:
    count = index.ntotal
    print(f"\n✅ Vector Store build successful! Index contains {count} chunks.")
    if count != len(meta_array):
        print(f"⚠️ Warning: Index length ({count}) does not match metadata length ({len(meta_array)}).")
        
    # Quick semantic test query
    test_query = "What is the exit load for Parag Parikh Liquid Fund?"
    print(f"\n🧪 Running semantic validation test:\nQuery: '{test_query}'")
    
    model = SentenceTransformer("all-MiniLM-L6-v2")
    query_emb = model.encode([test_query])
    faiss.normalize_L2(query_emb)
    
    # Search for top 1 result
    distances, indices = index.search(query_emb, k=1)
    
    if len(indices) > 0 and indices[0][0] != -1:
        best_idx = int(indices[0][0])
        match = meta_array[best_idx]
        print(f"Top result (Score: {distances[0][0]:.4f}): {match['text']}")
        print(f"Source: {match['metadata']['source_url']}")
    else:
        print("Test failed: No results returned.")


if __name__ == "__main__":
    build_vector_store()
