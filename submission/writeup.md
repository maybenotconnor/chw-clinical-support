# MedGemma-Powered Clinical Decision Support for Community Health Workers

**Kaggle MedGemma Impact Challenge — Main Track + Edge AI Special Award**

*Connor Marsley*

---

## 1. The Problem

Across sub-Saharan Africa, 5.4 million Community Health Workers (CHWs) serve as the primary healthcare contact for over one billion people. These frontline workers operate in settings where reliable internet is scarce and the nearest physician may be hours away. National clinical guidelines exist to standardize care — Uganda's Clinical Guidelines 2023 covers 24 chapters — but at 800+ pages they are impractical to consult during a patient encounter. **CHWs need instant, structured access to the exact guideline content relevant to their clinical question, available offline.**

This project was developed in partnership with WHO (clinical guideline standards), Makerere University IIDMM (clinical validation), and Decanlys (mobile engineering and field deployment). The Uganda Clinical Guidelines 2023 serves as our proof-of-concept, but the pipeline is designed to ingest any structured clinical guideline PDF.

---

## 2. Two-Brain Architecture

We introduce a **Two-Brain architecture** — both brains run fully on-device with zero connectivity required.

**Brain 1: On-Device Retrieval (<400ms).** The query is embedded on-device using MiniLM-L6-v2 (ONNX, 22MB). sqlite-vec performs vector search while FTS5 handles keyword search with BM25 scoring — capturing exact medical terminology (e.g., "amoxicillin 250mg") that semantic search misses. Reciprocal Rank Fusion (k=60) merges both result sets, outperforming either method alone in 95% of test queries. 46 clinically-curated danger signs (convulsions, severe bleeding, eclampsia) are matched against retrieved content, triggering red/amber visual warnings. Brain 1 returns ranked guideline excerpts with section headings and page references in under 400ms on a mid-range phone.

**Brain 2: MedGemma Synthesis (~3 min on-device).** MedGemma 1.5 4B-it (Q4_K_M GGUF, ~2.5GB) runs on-device via llama.cpp to synthesize retrieved chunks into a structured clinical summary. The prompt instructs MedGemma to answer *only* from the provided excerpts, use CHW-appropriate language, include specific dosages/age ranges, and flag danger signs. MedGemma 1.5's improved medical reasoning (69% MedQA vs 64% for 1.0) provides a safety margin — it follows grounding constraints more faithfully than general-purpose models, reducing the risk of fabricated clinical details. The codebase includes a guardrail self-critique pass (evaluating grounding, accuracy, completeness, no-fabrication, and scope), currently disabled on-device due to latency but re-enableable as mobile SoCs improve.

**Graceful Degradation.** Brain 1 always works. If MedGemma is unavailable (low-RAM device), Brain 1 results remain fully accessible. If the guardrail rejects a summary, raw guideline chunks are shown. Every failure mode preserves access to clinical content.

---

## 3. Safety, Performance, and Impact

### Safety by Design

1. **Deterministic high-risk detection**: 46 curated danger signs trigger visual warnings before any LLM output — clinically validated, not model-generated
2. **Retrieval grounding**: MedGemma synthesizes only from retrieved excerpts, never from parametric knowledge; the prompt prohibits fabrication and requires page references
3. **Guardrail validation**: Second MedGemma pass checks grounding, accuracy, completeness, no-fabrication, and scope (active in Python pipeline; disabled on-device pending faster hardware)
4. **Permissive failure**: Brain 2 errors never block Brain 1 results

### Performance

| Metric | Result | Notes |
|--------|--------|-------|
| Brain 1 search latency | ~364ms (Android) / 13–37ms (Python) | Embedding + hybrid search |
| Brain 2 synthesis | ~3 min (Snapdragon 845) / 30–60s (Python) | Q4_K_M, 6GB RAM |
| Embedding inference | ~248ms | ONNX Runtime on ARM |
| Database size | 43MB | Single SQLite file, bundled in APK |
| Hybrid vs single-mode | Hybrid RRF draws from both sources in 95% of queries | See evaluation_results.md |

### Edge AI Readiness

The entire system runs on a **$150 Android phone** with zero cloud dependency. The APK bundles the embedding model, guideline database, and MedGemma GGUF. A CHW installs the app and has immediate access — no setup, no accounts, no connectivity. Tested on a OnePlus 6T (Snapdragon 845, 6GB RAM).

### Impact and Limitations

A CHW in rural Uganda can type "danger signs of malaria in children under 5" and receive structured, guideline-grounded clinical guidance in seconds — offline. The extraction pipeline accepts any clinical guideline PDF, enabling expansion to Kenya, Ethiopia, or any country with national guidelines. Future directions include MedGemma multimodal support for clinical image triage and voice input for hands-free queries.

**Limitations**: On-device synthesis takes ~3 minutes on a 2018 SoC — usable but not ideal for urgent encounters. Context is limited to 1500 characters to keep prefill tractable. The guardrail uses the same model that generated the summary. Current evaluation is automated on a single guideline document; clinical expert review with Makerere IIDMM physicians is planned before field deployment.

---

*Built with MedGemma 1.5 4B-it, Docling, sqlite-vec, and ONNX Runtime. Open source: https://github.com/maybenotconnor/chw-clinical-support*
