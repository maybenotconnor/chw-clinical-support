# CLAUDE.md - CHW Clinical Decision Support System

## Project Overview

This is a **CHW Clinical Decision Support Application** - a healthcare mobile app providing Community Health Workers (CHWs) in low-resource settings with rapid, offline-first access to clinical guidelines. Built in partnership with WHO, Makerere IIDMM, and Decanlys.

## Architecture: Two-Brain Approach

The system uses a **Two-Brain architecture**:

### Brain 1: On-Device Retrieval (Always Offline)
- Local SQLite database with sqlite-vec for vector search
- On-device embedding generation (MiniLM-L6-v2 quantized, 384d)
- Hybrid search: Vector + BM25 keyword search with RRF fusion
- High-risk term detection with visual warnings
- **Always returns results regardless of connectivity**

### Brain 2: Cloud-Based Synthesis (Requires Online)
- Cloud LLM generates summaries from retrieved chunks
- Guardrail critique validates grounding and safety
- Can refuse summary (but Brain 1 results remain accessible)
- Gracefully degrades when offline

## Project Components

This project separates into **two distinct components**:

### 1. Extraction Pipeline (Python)
**Purpose**: Process clinical guideline PDFs into a searchable SQLite database

**Location**: `extraction/`

**Key Technologies**:
- **Docling**: IBM's PDF extraction toolkit (layout analysis, table extraction, OCR)
- **HybridChunker**: Tokenization-aware document chunking
- **sentence-transformers**: Embedding generation
- **sqlite-vec**: Vector storage and search
- **Streamlit**: Human review UI for extracted content

**Workflow**:
1. Configure Docling for PDF extraction
2. Run DocumentConverter on guideline PDFs
3. Human review in Streamlit UI
4. Run HybridChunker for tokenization-aware chunking
5. Generate embeddings for all chunks
6. Insert into SQLite with sqlite-vec
7. Package database for Android app

### 2. Android Application (Kotlin)
**Purpose**: Mobile clinical decision support app for CHWs

**Location**: `android/`

**Key Technologies**:
- **Kotlin** with Jetpack Compose
- **requery/sqlite-android**: Custom SQLite build with extension loading
- **sqlite-vec**: Vector search (bundled via custom SQLite)
- **ONNX Runtime**: On-device embedding inference
- **OkHttp3**: HTTP client for Brain 2 API calls
- **Material 3**: UI components

**Target Specs**:
- Target API: 34 (Android 15), Min SDK: 26 (Android 8.0)
- Database size: ≤500MB
- Query latency: <2s offline, <8s with summary
- Battery: <15% per hour active use

## Directory Structure

```
chw-clinical-support/
├── extraction/                    # Python extraction pipeline
│   ├── src/
│   │   ├── converter.py          # Docling PDF extraction
│   │   ├── chunker.py            # HybridChunker
│   │   ├── embedder.py           # Embedding generation
│   │   └── database.py           # SQLite operations
│   ├── review_ui/
│   │   └── app.py                # Streamlit review UI
│   └── tests/
│
├── android/                       # Kotlin Android app
│   ├── app/src/main/
│   │   ├── java/org/who/chw/clinical/
│   │   │   ├── brain1/           # Retrieval engine
│   │   │   ├── brain2/           # Synthesis engine
│   │   │   ├── ui/               # UI components
│   │   │   └── data/             # Database access
│   │   └── res/
│   └── build.gradle.kts
│
├── models/                        # ML models
│   ├── embedding/                # Quantized embedding models
│   └── stt/                      # Voice models (Phase 4)
│
├── data/
│   ├── guidelines/               # Source PDFs (e.g., UCG 2023)
│   ├── databases/                # Generated SQLite files
│   └── test_queries/             # Test datasets
│
└── docs/                          # Documentation
```

## Key Documentation Files

| File | Description |
|------|-------------|
| `CHW_Clinical_RAG_SRD_v1.4.md` | Full system requirements document |
| `CHW_Dev_Environment_Setup.md` | Development environment setup guide |
| `CHW_Phased_Implementation_Plan_v1.md` | 5-phase implementation roadmap |
| `UCGDocumentProfile.md` | Uganda Clinical Guidelines document profile |
| `compass_artifact_wf-*.md` | sqlite-vec Android integration guide |

## Example Document: Uganda Clinical Guidelines 2023

The UCG 2023 PDF is included as an example for the extraction pipeline. Key characteristics:

- **Structure**: Highly structured disease monographs (Definition → Causes → Features → Diagnosis → Management → Prevention)
- **Special Elements**: Treatment tables with LOC (Level of Care), dosing grids, caution boxes, flowcharts
- **Complexity**: This is the most complex document - other guidelines will be simpler
- **Location**: `UCG-2023-Publication-Final-PDF-Version-1.pdf`

## Database Schema

```sql
-- Core content
chunks (chunk_id, doc_id, content, contextualized_text, chunk_type, page_number)
chunk_metadata (chunk_id, headings_json, bbox_json, element_label)

-- Vector search (via sqlite-vec)
embeddings (chunk_id, embedding_vector)

-- Document tracking
documents (doc_id, filename, title, version, extraction_date, approval_status, docling_json)

-- Safety features
high_risk_terms (term_id, term, category, severity)
```

## Implementation Phases

1. **Phase 1 - Foundation MVP** (3-4 weeks): Core RAG end-to-end
2. **Phase 2 - Search Quality** (2-3 weeks): Hybrid search + high-risk detection
3. **Phase 3 - Brain 2 Integration** (3-4 weeks): Cloud LLM + guardrails
4. **Phase 4 - Voice & Interaction** (2-3 weeks): STT/TTS + follow-ups
5. **Phase 5 - Production Hardening** (3-4 weeks): Audit logging, optimization, security

## Development Commands

### Extraction Pipeline (Python)
```bash
# Setup
cd extraction
python -m venv venv
source venv/bin/activate
pip install docling sentence-transformers sqlite-vec streamlit

# Run extraction
python src/converter.py --input data/guidelines/UCG-2023.pdf

# Run review UI
streamlit run review_ui/app.py

# Generate embeddings
python src/embedder.py --database data/databases/guidelines.db
```

### Android App
```bash
# Build
cd android
./gradlew assembleDebug

# Run tests
./gradlew test

# Install on device
./gradlew installDebug
```

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| PDF extraction | Docling | Built-in layout AI, table extraction, VLM support |
| Chunking | HybridChunker | Tokenization-aware, preserves structure |
| Vector DB | sqlite-vec | Single-file, embedded, Android-compatible |
| Search fusion | RRF | Simple, proven effective, no model required |
| High-risk detection | Keyword matching | Fast, deterministic, clinically curated |

## Pending Decisions (TBD)

- Embedding model: MiniLM-L6-v2 vs BGE-small vs EmbeddingGemma
- Cloud LLM: Claude vs OpenAI vs Azure vs Gemini
- Guardrail method: Second LLM call vs NLI model
- STT engine: Android built-in vs Whisper vs cloud

## Performance Targets

- Query to results: <2 seconds (offline)
- Query to summary: <8 seconds (online)
- Cold start: <5 seconds
- Embedding latency: <500ms
- Vector search: <200ms
- Battery: <15% per hour active use

## Safety Features

1. **High-risk term detection**: Keyword matching against curated danger signs
2. **Visual warnings**: Red/amber banners for high-risk conditions
3. **Guardrail validation**: Verify summaries are grounded in retrieved content
4. **Graceful degradation**: Brain 1 always works; Brain 2 failures don't block results
