# Groww Mutual Fund FAQ Assistant – Phase-wise Architecture (Facts-Only RAG)

This document describes the detailed phase-wise architecture for a Retrieval-Augmented Generation (RAG) chatbot that answers factual questions about selected schemes of PPFAS Mutual Fund using only official public pages hosted on Groww. 

**Target Audience & Context**: Product Management Portfolio Project demonstrating AI model integration (Google Gemini API), product sense, system guardrails, and rapid free-tier prototyping capabilities in a Python 3.12 environment.

The assistant answers facts such as expense ratio, exit load, minimum SIP, lock-in (ELSS), riskometer category, and benchmark. It does not provide investment advice, does not process PII, and does not compute or compare returns. Every answer includes exactly one official source link and a freshness indicator.

---

## 1. Product Dimensions & KPIs

### Core Product Philosophy
* **Factual Integrity**: Output derived 100% from structured Groww sources.
* **Ethics & Compliance Base**: Immediate rejection of PII or advisory queries.
* **Traceability**: "Last updated from sources" with the exact anchor link appended to every output.

### Success Metrics (Portfolio Highlights)
* **Response Accuracy**: 95%+ precision on factual questions utilizing retrieved context.
* **Guardrail Reliability**: 100% rejection rate against explicitly injected PII / financial advice queries.
* **Cost Efficiency**: $0.00 Operating Cost (utilizing Google Gemini's generous free-tier APIs and open-source tooling like ChromaDB).

---

## High-level RAG flow (Target End State)

* **Ingest**: Crawl official Groww AMC/scheme pages → Extract structured fund attributes → Store JSON records.
* **Index**: Create atomic chunks → Embed using local open-source models → Index in ChromaDB.
* **Retrieve**: User query → Guardrails (PII + Advisory detection) → Embed query → Similarity search → Top-k factual chunks.
* **Generate**: Query + Retrieved chunks → Constrained Gemini Prompt → Answer (≤3 sentences).
* **Cite**: Backend appends exactly one official Groww source URL and "Last updated from sources: \<link\>".
* **Deliver**: Streamlit Frontend → FastAPI Backend → Google Gemini API.
* **Scheduler**: Periodically re-runs ingest → re-index so the assistant reflects the latest data.

---

## Phase 1: Data Ingestion from groww.in (PPFAS AMC)

**Goal**: Reliably collect structured factual data for selected PPFAS schemes.

### 1.1 Target AMC and scheme URLs (Strict Boundary)

**AMC Page**
* [PPFAS Mutual Fund Overview](https://groww.in/mutual-funds/amc/ppfas-mutual-funds)

**Scheme Pages (Direct Growth Variants)**
* [Parag Parikh Long Term Value Fund](https://groww.in/mutual-funds/parag-parikh-long-term-value-fund-direct-growth)
* [Parag Parikh ELSS Tax Saver Fund](https://groww.in/mutual-funds/parag-parikh-elss-tax-saver-fund-direct-growth)
* [Parag Parikh Conservative Hybrid Fund](https://groww.in/mutual-funds/parag-parikh-conservative-hybrid-fund-direct-growth)
* [Parag Parikh Liquid Fund](https://groww.in/mutual-funds/parag-parikh-liquid-fund-direct-growth)
* [Parag Parikh Arbitrage Fund](https://groww.in/mutual-funds/parag-parikh-arbitrage-fund-direct-growth)
* [Parag Parikh Dynamic Asset Allocation Fund](https://groww.in/mutual-funds/parag-parikh-dynamic-asset-allocation-fund-direct-growth)
* [Parag Parikh Large Cap Fund](https://groww.in/mutual-funds/parag-parikh-large-cap-fund-direct-growth)

*Constraint*: Only these official public URLs are valid data sources. No third-party blogs or platforms.

### 1.2 Data to extract (Schema)
To support factual queries, the ingestion must capture at minimum:
* `scheme_id` (Slug), `scheme_name`, `amc_name`, `fund_category`
* `expense_ratio`, `minimum_sip`, `minimum_lumpsum`
* `exit_load`, `lock_in_period`
* `riskometer_category`, `benchmark_index`
* `source_url`, `last_updated`

### 1.3 Technical approach for Phase 1
**Stack**: `Playwright` Headless Browser (for client-rendered React pages).
* **Crawl**: Seed URLs & save raw HTML snapshots in `data/raw/`.
* **Parse**: Parse with Playwright locators/BeautifulSoup.
* **Validate**: Fail ingestion if mandatory fields (`scheme_id`, `expense_ratio`, etc.) sit empty.
* **Export**: Output as standard `data/structured/ppfas_schemes.json`. Idempotent writes.

---

## Phase 2: Chunking, Embeddings, and Vector Store

**Goal**: Convert structured records into precise retrievable factual units.

### 2.1 Chunking strategy
*Do not use arbitrary character-based splitting.* Create atomic factual chunks answering one attribute at a time.
*Example chunk:* "The expense ratio of Parag Parikh Large Cap Fund – Direct Growth is 0.61%."

### 2.2 Embedding model
Use local open-source embeddings: `sentence-transformers/all-MiniLM-L6-v2`
**Reason**: Free, lightweight, lightning-fast for offline FAQ semantic retrieval natively within Python.

### 2.3 Vector store
Use **ChromaDB** running locally in persistent mode. Indexing script reads structured JSON, applies the local embedding model, and pushes embedded chunks into the database with attached metadata (`scheme_id`, `field_type`, `source_url`).

---

## Phase 3: Guardrails (Query Controller Layer)

**Goal**: Ensure the assistant remains strictly compliant dynamically.

* **3.1 PII Filter**: Python `re` matching logic blocking PAN, Aadhaar, Phone numbers, Email addresses. Return: *"Personal financial information cannot be processed."* 
* **3.2 Advisory Detection**: Block intent patterns ("Should I invest?", "Is this fund good?"). Return: *"This assistant provides factual information only. For investment guidance, consult official educational resources."* Include the AMC URL.
* **3.3 Factual Queries**: Only valid metrics queries (expense ratio, exit load, SIP) proceed to Vector Search.

---

## Phase 4: Retrieval and Gemini Generation

**Goal**: Answer strictly using retrieved context combined with a powerful free LLM tier.

### 4.1 Retrieval flow
1. User question → embed → top-k similarity search (k=3) in ChromaDB.
2. Select the best matching factual semantic chunk context.

### 4.2 LLM generation (Google Gemini API)
**Model**: `Google Gemini API` (`gemini-2.5-flash` using `google-genai` Python library).
**System prompt constraints**:
*"You are a mutual fund facts assistant. Use ONLY the provided context. Answer in maximum 3 sentences. Do not provide advice. If the information is not present, clearly state that it is not available in the official source."*

### 4.3 Citation enforcement
The Gemini API handles natural language generation only.
**Backend Python logic**:
* Extract `source_url` from retrieved chunk metadata.
* Append dynamically: *"Last updated from sources: \<source_url\>"*

---

## Phase 5: Backend API Layer

**Goal**: Provide a clean, robust, reusable API.
**Stack**: `FastAPI` + `Uvicorn` (Python 3.12).
* `POST /query`: Accepts JSON question payload, routes through guardrails → ChromaDB → Gemini API → Response logic.
* `GET /health`: Displays Vector DB status, last ingestion timestamp.

---

## Phase 6: Frontend (Minimal UI)

**Goal**: Deliver a transparent Product FAQ interface.
**Stack**: `Streamlit`.
* **Welcome Message**: Outlines AI limits and strictly factual nature.
* **Buttons**: 3 click-to-query examples (e.g., "What is the exit load of the Liquid Fund?").
* **Chat Logic**: Displays generation wrapped beautifully with exact hyperlink citations at the end of every message.

---

## Phase 7: Scheduler (Data Refresh Pipeline)
* **Trigger**: Scheduled cron job logic to maintain freshness.
* **Flow**: Runs Phase 1 ingestion → Re-indexes Vector Database atomically → Validates health.

---

## Phase 8: Operational Guardrails & Constraints Summary
* **Hard Limitations**: Public Groww pages only. No screenshots, no third-party blogs. No user PII storage under any circumstances.
* **Formatting Limits**: Maximum 3 sentences per output, guaranteed appending of precisely one verified source anchor link.
