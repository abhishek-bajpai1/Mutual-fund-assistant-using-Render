import re
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # type: ignore

class QueryGuardrail:
    """
    Implements Phase 3 Guardrails to ensure strictly factual queries.
    Blocks any Personal Identifiable Information (PII) or financial advisory intent.
    """
    
    # Standard Indian PII Regex patterns
    PII_PATTERNS = {
        "PAN": r"[A-Z]{5}[0-9]{4}[A-Z]{1}",
        "Aadhaar": r"\b\d{4}\s?\d{4}\s?\d{4}\b",
        "Phone": r"\+?\d{1,3}[-.\s]?\(?\d{1,3}\)?[-.\s]?\d{3,4}[-.\s]?\d{4}",
        "Email": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
        "Bank_Account": r"\b\d{9,18}\b" # Generic 9-18 digit account numbers
    }
    
    # Heuristics for advisory intent
    ADVISORY_PATTERNS = [
        r"\bshould i invest\b",
        r"\bis this a good\b",
        r"\bwill i make money\b",
        r"\bgive me advice\b",
        r"\bwhich fund is best\b",
        r"\bbetter to invest in\b",
        r"\brecommend.*fund\b",
        r"\bwhat should i buy\b",
        r"\bwhere to put my money\b",
        r"\bsuggest me\b",
        r"\bportfolio review\b",
        r"\bhighest return\b",
    ]

    @classmethod
    def check_pii(cls, query: str) -> bool:
        """Returns True if PII is detected in the query."""
        for pattern_name, regex in cls.PII_PATTERNS.items():
            if re.search(regex, query, re.IGNORECASE):
                return True
        return False

    @classmethod
    def check_advisory_intent(cls, query: str) -> bool:
        """Returns True if financial advisory intent is detected."""
        for pattern in cls.ADVISORY_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                return True
        return False

    @classmethod
    def validate_query(cls, query: str) -> dict:
        """
        Main controller gate.
        Returns: {"is_valid": bool, "message": str}
        """
        
        # 3.1 PII Filter
        if cls.check_pii(query):
            return {
                "is_valid": False,
                "message": "Personal financial information (PII) cannot be processed. Please remove account numbers, emails, or IDs from your query."
            }
            
        # 3.2 Advisory Detection
        if cls.check_advisory_intent(query):
            return {
                "is_valid": False,
                "message": "This assistant provides factual information about mutual fund schemes only. For investment guidance, consult official educational resources at https://groww.in/mutual-funds/amc/ppfas-mutual-funds"
            }
            
        # Valid Query
        return {
            "is_valid": True,
            "message": "OK"
        }

if __name__ == "__main__":
    # Test suite
    test_queries = [
        "What is the exit load for the Liquid Fund?", # Valid
        "Tell me the expense ratio of Parag Parikh Flexi Cap.", # Valid
        "Is 9324567890 an okay minimum SIP?", # Block (Phone/Bank)
        "Should I invest my 10,000 rupees in ELSS or Hybrid?", # Block (Advisory)
        "My PAN is ABCDE1234F, can I invest?", # Block (PII)
        "Which fund is best for high returns?", # Block (Advisory)
    ]
    
    print("🧪 Running Phase 3 Guardrail Tests:\\n")
    for q in test_queries:
        result = QueryGuardrail.validate_query(q)
        status = "✅ PASS" if result["is_valid"] else "❌ BLOCKED"
        print(f"Query: '{q}'")
        print(f"Result: {status} -> {result['message']}\\n")
