import os
import sys
import pickle
from typing import List, Dict, Any

try:
    import faiss # type: ignore
    import numpy as np # type: ignore
    from sentence_transformers import SentenceTransformer # type: ignore
    from google import genai # type: ignore
    from google.genai import types # type: ignore
    from dotenv import load_dotenv # type: ignore
except ImportError:
    print("Error: Missing required packages. Please run:")
    print("pip install -r phase4_rag/requirements.txt")
    sys.exit(1)

# Ensure Windows terminal doesn't crash on standard print statements
sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # type: ignore

# Add Phase 3 to path so we can import the Guardrails
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
from phase3_guardrails.controller import QueryGuardrail

# Path configurations
FAISS_DB_DIR = os.path.join(BASE_DIR, "phase2_indexing", "faiss_db")
INDEX_PATH = os.path.join(FAISS_DB_DIR, "ppfas_index.faiss")
METADATA_PATH = os.path.join(FAISS_DB_DIR, "ppfas_metadata.pkl")

# Load environment variables (for GEMINI_API_KEY)
load_dotenv()


class RAGEngine:
    def __init__(self):
        """Initialize FAISS, Sentence Transformers, and the Gemini Client."""
        if not os.path.exists(INDEX_PATH) or not os.path.exists(METADATA_PATH):
            raise FileNotFoundError(f"FAISS vector store not found at {FAISS_DB_DIR}. Please run Phase 2 indexer first.")

        # 1. Load FAISS Array & Metadata
        self.index = faiss.read_index(INDEX_PATH)
        with open(METADATA_PATH, "rb") as f:
            self.metadata: List[Dict[str, Any]] = pickle.load(f)

        # 2. Load Embedding Model
        self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

        # 3. Initialize Gemini
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is missing. Please set it in a .env file.")
        
        self.ai_client = genai.Client(api_key=api_key)
        self.model_id = "gemini-2.5-flash"

        # System Rules for Gemini (Strict Phase 4 Requirements)
        self.system_instruction = (
            "You are a mutual fund facts assistant for PPFAS Mutual Fund. "
            "Use ONLY the provided context to answer the user's question. "
            "Answer in maximum 3 sentences. Do not provide financial advice. "
            "If the information is not present in the context, clearly state "
            "'I cannot find this information in the official source'. "
            "Do not hallucinate external knowledge."
        )


    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Embeds query and retrieves top K semantic chunks from FAISS."""
        
        query_emb = self.embedding_model.encode([query])
        faiss.normalize_L2(query_emb)
        
        # FAISS search returns distances (scores) and indices
        distances, indices = self.index.search(query_emb, k=top_k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx != -1:
                chunk = self.metadata[int(idx)]
                chunk["score"] = float(distances[0][i])
                results.append(chunk)

        return results


    def generate_answer(self, query: str) -> dict:
        """
        End-to-end RAG flow: 
        1. Guardrails -> 2. Retrieval -> 3. Gemini Generation -> 4. Citation formatting
        """
        
        # Step 1: Guardrails
        guard_check = QueryGuardrail.validate_query(query)
        if not guard_check["is_valid"]:
            # If PII or Advisory intent detected, break chain immediately
            return {
                "answer": guard_check["message"],
                "sources": []
            }

        # Step 2: Retrieve Context
        top_chunks = self.retrieve(query, top_k=3)
        if not top_chunks:
            return {
                "answer": "I don't have enough information in my database to answer that.",
                "sources": []
            }

        # Build context string
        context_str = "\\n---\\n".join([f"Fact: {c['text']}" for c in top_chunks])
        
        # Determine the primary source URL (taking the top #1 hit as the main citation)
        primary_source = top_chunks[0]["metadata"]["source_url"]

        # Step 3: Call Gemini with strict prompt
        prompt = f"Context:\\n{context_str}\\n\\nUser Question: {query}"
        
        try:
            # Attempt primary model
            response = self.ai_client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_instruction,
                    temperature=0.1 # Low temperature for factual consistency
                )
            )
            raw_answer = response.text.strip()
        except Exception as e:
            # Check for Rate Limit / Quota Exceeded (HTTP 429)
            if "429" in str(e) or "exhausted" in str(e).lower():
                print(f"\\n[Warning] {self.model_id} quota exceeded. Falling back to gemini-2.0-flash...")
                try:
                    fallback_response = self.ai_client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=self.system_instruction,
                            temperature=0.1
                        )
                    )
                    raw_answer = fallback_response.text.strip()
                except Exception as fallback_e:
                    print(f"\\n[Warning] gemini-2.0-flash failed. Falling back to tier-3: gemini-2.5-flash-lite...")
                    try:
                        lite_response = self.ai_client.models.generate_content(
                            model="gemini-2.5-flash-lite",
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                system_instruction=self.system_instruction,
                                temperature=0.1
                            )
                        )
                        raw_answer = lite_response.text.strip()
                    except Exception as lite_e:
                        return {
                            "answer": f"Error: All three AI models failed (Quota/Network). {str(lite_e)}",
                            "sources": []
                        }
            else:
                return {
                    "answer": f"Error calling Google Gemini API: {str(e)}",
                    "sources": []
                }

        # Step 4: Append Citation (Architecture requirement Phase 4.3)
        # We pass the sources cleanly in the JSON response so the frontend can format them.
        primary_last_updated = top_chunks[0]["metadata"].get("last_updated", "Unknown time")
        
        if "cannot find this information" in raw_answer.lower() or "don't have enough information" in raw_answer.lower():
            primary_source = None
            primary_last_updated = None

        final_answer = raw_answer

        return {
            "answer": final_answer,
            "sources": [primary_source] if primary_source else [],
            "last_updated": primary_last_updated,
            "retrieved_context": top_chunks # For debugging
        }


if __name__ == "__main__":
    print("Initializing Phase 4 RAG Engine... (Loading Embeddings & FAISS)")
    
    try:
        rag = RAGEngine()
        
        test_queries = [
            "What is the exit load for the Liquid Fund?",
            "What is the minimum sip for Parag Parikh Flexi Cap?",
            "Should I invest my money in the Conservative Hybrid fund?", # Should hit guardrails
            "What is the capital city of France?" # Should hit "not in context" fallback
        ]
        
        print("\\n🧪 Running Phase 4 LLM Generation Tests:\\n")
        for q in test_queries:
            print(f"\\033[94mUser:\\033[0m {q}")
            result = rag.generate_answer(q)
            print(f"\\033[92mAssistant:\\033[0m {result['answer']}\\n")
            
    except Exception as e:
        print(f"Initialization Error: {e}")
