# CLAUDE.md - CHW Clinical Decision Support System

## Project Overview

This is a **CHW Clinical Decision Support Application** - a healthcare mobile app providing Community Health Workers (CHWs) in low-resource settings with rapid, offline-first access to clinical guidelines. Built in partnership with WHO, Makerere IIDMM, and Decanlys.

**Repository**: https://github.com/maybenotconnor/chw-clinical-support

## Architecture: Two-Brain Approach

The system uses a **Two-Brain architecture** — both brains run fully on-device:

### Brain 1: On-Device Retrieval (Always Offline)
- Local SQLite database with sqlite-vec for vector search
- On-device embedding generation (MiniLM-L6-v2 quantized ONNX, 384d)
- Hybrid search: Vector + BM25 keyword search with RRF fusion (k=60)
- High-risk term detection (46 clinically-curated danger signs) with visual warnings
- **Always returns results regardless of connectivity or Brain 2 status**

### Brain 2: On-Device MedGemma Synthesis (Also Offline)
- **MedGemma 1.5 4B-it** (Q4_K_M GGUF, ~2.5GB) runs on-device via llama.cpp (Llamatik wrapper)
- Synthesizes retrieved chunks into structured clinical summaries
- Guardrail self-critique: second MedGemma inference pass validates grounding, accuracy, completeness, no-fabrication, and scope
- Gracefully degrades — if MedGemma unavailable or guardrail fails, Brain 1 results remain accessible

## Project Components

### 1. Extraction Pipeline (Python)
**Purpose**: Process clinical guideline PDFs into a searchable SQLite database + run MedGemma synthesis

**Location**: `extraction/`

**Key Files**:
- `src/medgemma_synthesis.py` — Brain 1 + Brain 2 RAG pipeline (main entry point)
- `src/clinical_prompts.py` — MedGemma prompt templates (synthesis + guardrail)
- `src/converter.py` — Docling PDF extraction
- `src/chunker.py` — HybridChunker (tokenization-aware)
- `src/embedder.py` — MiniLM-L6-v2 embedding generation
- `src/database.py` — SQLite + sqlite-vec operations
- `src/pipeline.py` — End-to-end extraction pipeline
- `review_ui/app.py` — Streamlit human review UI

### 2. Android Application (Kotlin)
**Purpose**: Mobile clinical decision support app for CHWs

**Location**: `android/`

**Key Technologies**:
- **Kotlin** with Jetpack Compose
- **requery/sqlite-android**: Custom SQLite build with extension loading
- **sqlite-vec**: Vector search (bundled as native .so)
- **ONNX Runtime**: On-device MiniLM-L6-v2 embedding inference
- **Llamatik**: llama.cpp wrapper for on-device MedGemma inference
- **Material 3**: UI components

**Target Specs**:
- Target API: 34 (Android 15), Min SDK: 26 (Android 8.0)
- Database size: ≤500MB (actual: 43MB)
- Search latency: <2s offline
- MedGemma synthesis: 30-60s on-device

## Directory Structure

```
├── extraction/                # Python extraction + synthesis pipeline
│   ├── src/
│   ├── tests/                 # 33 tests (pytest)
│   ├── review_ui/
│   └── requirements.txt
│
├── android/                   # Kotlin Android app
│   ├── app/src/main/
│   │   ├── java/org/who/chw/clinical/
│   │   │   ├── brain1/       # Retrieval engine
│   │   │   ├── brain2/       # MedGemma synthesis (on-device)
│   │   │   ├── ui/           # Jetpack Compose UI
│   │   │   └── data/         # Database access
│   │   ├── jniLibs/          # sqlite-vec native libraries
│   │   └── res/
│   └── build.gradle.kts
│
├── models/
│   ├── embedding/            # MiniLM-L6-v2 ONNX (not in git)
│   └── medgemma/Modelfile    # Ollama model config
│
├── data/
│   └── databases/            # Generated SQLite files (not in git)
│
└── submission/               # MedGemma Impact Challenge deliverables
    ├── writeup.md
    ├── evaluation_results.md
    ├── video_script.md
    └── README.md
```

## Database Schema

```sql
-- Core content
chunks (chunk_id, doc_id, content, contextualized_text, chunk_type, page_number)
chunk_metadata (chunk_id, headings_json, bbox_json, element_label)

-- Vector search (via sqlite-vec)
embeddings (chunk_id, embedding_vector)

-- Full-text search
chunks_fts (FTS5 virtual table on content)

-- Document tracking
documents (doc_id, filename, title, version, extraction_date, approval_status, docling_json)

-- Safety features
high_risk_terms (term_id, term, category, severity)
```

## Development Commands

### Extraction Pipeline (Python)
```bash
# Setup
cd extraction
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run MedGemma synthesis (requires Ollama for dev testing)
cd ..  # back to project root
python -m extraction.src.medgemma_synthesis --query "malaria danger signs in children"
python -m extraction.src.medgemma_synthesis --all          # all 20 test queries
python -m extraction.src.medgemma_synthesis --search-only   # Brain 1 only, no LLM
python -m extraction.src.medgemma_synthesis --ablation       # search ablation study

# Run extraction from PDF
python -m extraction.src.pipeline --input /path/to/guidelines.pdf

# Run review UI
streamlit run extraction/review_ui/app.py

# Run tests
python -m pytest extraction/tests/ -v
```

### Android App
```bash
cd android
./gradlew assembleDebug
./gradlew test
./gradlew installDebug
```

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| PDF extraction | Docling | Built-in layout AI, table extraction, VLM support |
| Chunking | HybridChunker | Tokenization-aware, preserves structure |
| Embedding model | MiniLM-L6-v2 (ONNX) | Small (22MB), fast, good quality for 384d |
| Vector DB | sqlite-vec | Single-file, embedded, Android-compatible |
| Search fusion | RRF (k=60) | Simple, proven effective, no model required |
| LLM synthesis | MedGemma 1.5 4B-it | Medical domain pretraining, runs on-device via llama.cpp |
| Guardrail | Second MedGemma pass | 5-criteria self-critique (grounding, accuracy, completeness, no-fabrication, scope) |
| High-risk detection | Keyword matching | Fast, deterministic, 46 clinically curated terms |
| On-device LLM runtime | Llamatik (llama.cpp) | Android-native, Q4_K_M quantization |

## Large Files (not in git)

These files are required but excluded from git due to size. See README.md for download/generation instructions:

- `data/databases/guidelines_v2.db` — 43MB, generated by extraction pipeline
- `models/embedding/` — MiniLM-L6-v2 ONNX model + tokenizer
- `android/app/src/main/assets/models/medgemma-1.5-4b-it-Q4_K_M.gguf` — ~2.5GB MedGemma GGUF
- `android/app/src/main/assets/databases/` — copy of guidelines DB for Android
- `data/guidelines/*.pdf` — source guideline PDFs

## Safety Features

1. **High-risk term detection**: 46 curated danger signs matched deterministically
2. **Visual warnings**: Red/amber banners for high-risk conditions
3. **Guardrail validation**: Second MedGemma pass checks grounding, accuracy, completeness, no-fabrication, scope
4. **Graceful degradation**: Brain 1 always works; Brain 2 failures never block results
5. **No parametric knowledge**: MedGemma synthesizes only from retrieved guideline excerpts
