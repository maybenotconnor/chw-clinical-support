# CHW Clinical Decision Support — MedGemma Impact Challenge

MedGemma-powered clinical decision support for Community Health Workers in low-resource settings. Two-Brain architecture: always-offline retrieval (Brain 1) + on-device MedGemma synthesis (Brain 2).

## Quick Start

### Prerequisites

- **Python 3.10+** with pip
- **Ollama** ([install](https://ollama.com/download)) — for Python pipeline testing only; the Android app runs MedGemma on-device
- **Android Studio** (for the mobile app, optional)
- ~4GB disk space (for MedGemma model + database)

### 1. Clone and Install

```bash
git clone https://github.com/maybenotconnor/chw-clinical-support.git
cd chw-clinical-support

# Python extraction pipeline
cd extraction
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Pull MedGemma

```bash
ollama pull hf.co/unsloth/medgemma-1.5-4b-it-GGUF:Q4_K_M
```

Verify it's running:
```bash
ollama list  # Should show hf.co/unsloth/medgemma-1.5-4b-it-GGUF:Q4_K_M
```

### 3. Run MedGemma Synthesis Pipeline

```bash
# From the project root (with venv activated)

# Run 3 sample queries (quick test)
python -m extraction.src.medgemma_synthesis

# Run a single custom query
python -m extraction.src.medgemma_synthesis --query "danger signs of malaria in children under 5"

# Run all 20 test queries (full validation)
python -m extraction.src.medgemma_synthesis --all

# Brain 1 only (no LLM, no Ollama required)
python -m extraction.src.medgemma_synthesis --search-only --all

# Run ablation study (vector vs keyword vs hybrid — no LLM required)
python -m extraction.src.medgemma_synthesis --ablation
```

Each query outputs: retrieved chunks, high-risk alerts, MedGemma summary, guardrail validation, and timing metrics. The ablation study writes structured results to `submission/evaluation_results.md`.

---

## Project Structure

```
├── extraction/                # Python extraction + synthesis pipeline
│   ├── src/
│   │   ├── medgemma_synthesis.py   # Brain 1 + Brain 2 RAG pipeline
│   │   ├── clinical_prompts.py     # MedGemma prompt templates
│   │   ├── converter.py            # Docling PDF extraction
│   │   ├── chunker.py              # HybridChunker
│   │   ├── embedder.py             # MiniLM-L6-v2 embeddings
│   │   ├── database.py             # SQLite + sqlite-vec
│   │   └── pipeline.py             # End-to-end extraction
│   ├── requirements.txt
│   └── review_ui/app.py            # Streamlit human review UI
│
├── android/                   # Kotlin Android application
│   └── app/src/main/java/org/who/chw/clinical/
│       ├── brain1/            # On-device retrieval
│       ├── brain2/            # MedGemma synthesis
│       ├── data/              # Database access
│       └── ui/                # Jetpack Compose UI
│
├── models/
│   ├── embedding/             # MiniLM-L6-v2 ONNX (quantized)
│   └── medgemma/Modelfile     # Ollama model configuration
│
├── data/
│   └── databases/
│       └── guidelines_v2.db   # Pre-built guideline database (43MB)
│
└── submission/                # Competition deliverables
    ├── writeup.md             # Technical overview
    ├── evaluation_results.md  # Ablation study & per-query results
    ├── video_script.md        # Demo video script
    └── README.md              # This file
```

## Full Extraction Pipeline (from PDF)

To process a new clinical guideline PDF from scratch:

```bash
cd extraction
source venv/bin/activate

# Step 1: Extract PDF with Docling
python -m extraction.src.pipeline --input /path/to/guidelines.pdf

# Step 2: Review extracted content (optional)
streamlit run review_ui/app.py

# Step 3: Run synthesis test
python -m extraction.src.medgemma_synthesis --db data/databases/guidelines_v2.db --all
```

The extraction pipeline handles: PDF parsing (Docling) → tokenization-aware chunking (HybridChunker) → embedding generation (MiniLM-L6-v2) → SQLite + sqlite-vec database creation → FTS5 indexing → high-risk term population.

## Android App

```bash
cd android

# Build
./gradlew assembleDebug

# Install on connected device/emulator
./gradlew installDebug

# Run tests
./gradlew test
```

The Android app requires:
- `guidelines_v2.db` in `app/src/main/assets/databases/`
- `minilm-l6-v2-quantized.onnx` in `app/src/main/assets/models/` (source: `models/embedding/minilm-l6-v2-quantized.onnx`)
- `vocab.txt` in `app/src/main/assets/models/tokenizer/` (source: `models/embedding/tokenizer/vocab.txt`)
- `medgemma-1.5-4b-it-Q4_K_M.gguf` in `app/src/main/assets/models/` (~2.5GB, download from HuggingFace — see below)

**MedGemma runs fully on-device** — no Ollama or network server required. Both Brain 1 and Brain 2 work offline.

```bash
# Download MedGemma GGUF for on-device inference
huggingface-cli download unsloth/medgemma-1.5-4b-it-GGUF \
    medgemma-1.5-4b-it-Q4_K_M.gguf \
    --local-dir android/app/src/main/assets/models/
```

**Note**: The bundled GGUF makes the APK ~2.7GB. This is suitable for sideloading and demo purposes. On first launch, the model is extracted to cache (~10-30s), after which subsequent launches load in ~7s. Synthesis takes ~3 minutes on a Snapdragon 845 (OnePlus 6T); Brain 1 results are available immediately while Brain 2 generates.

## Architecture

```
┌────────────────────────────────────────────────────────┐
│  Brain 1: On-Device Retrieval (Always Offline)         │
│                                                        │
│  Query → MiniLM-L6-v2 ONNX → Embedding                │
│            ↓                                           │
│  sqlite-vec (Vector) + FTS5 (Keyword) → RRF Fusion     │
│            ↓                                           │
│  Ranked Results + High-Risk Alerts → Display           │
├────────────────────────────────────────────────────────┤
│  Brain 2: On-Device MedGemma Synthesis (Also Offline)  │
│                                                        │
│  Retrieved Chunks → Clinical Prompt → MedGemma 1.5 4B  │
│  (via llama.cpp / Llamatik)            ↓               │
│  Summary → Streaming Display                           │
└────────────────────────────────────────────────────────┘
```

## Key Technologies

| Component | Technology | Purpose |
|-----------|-----------|---------|
| PDF Extraction | Docling (IBM) | Layout analysis, table extraction, OCR |
| Chunking | HybridChunker | Tokenization-aware, structure-preserving |
| Embeddings | MiniLM-L6-v2 ONNX | On-device 384-dim embeddings |
| Vector DB | sqlite-vec | Single-file vector search |
| Keyword Search | FTS5 BM25 | Medical terminology matching |
| Fusion | Reciprocal Rank Fusion | Combines vector + keyword results |
| LLM Synthesis | MedGemma 1.5 4B-it (on-device via llama.cpp) | Clinical summary generation (~3 min on SD845) |
| Safety | Retrieval grounding + high-risk detection | Prompt-constrained synthesis, 46 curated danger signs |
| Android | Kotlin + Jetpack Compose | Mobile application |

## Tests

```bash
# Run Python test suite (33 tests)
python -m pytest extraction/tests/ -v
```

## Test Queries

The 20-query test suite covers:
- Pediatric emergencies (malaria danger signs, dehydration, pneumonia)
- Maternal health (pregnancy danger signs, PMTCT)
- Chronic diseases (hypertension, diabetes, HIV, TB)
- Acute conditions (snake bite, chest pain, seizures)
- Nutritional emergencies (severe malnutrition)
- Drug dosing (amoxicillin for pneumonia)
- Referral criteria (when to refer to hospital)

## License

Open source. Built with MedGemma, Docling, sqlite-vec, and ONNX Runtime.

Partnership: WHO / Makerere University IIDMM / Decanlys
