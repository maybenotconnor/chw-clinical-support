# MedGemma-Powered Clinical Decision Support for Community Health Workers

**Kaggle MedGemma Impact Challenge — Main Track + Edge AI Special Award**

*Connor Marsley — WHO / Makerere University IIDMM / Decanlys Partnership*

---

## 1. The Problem: Clinical Guidelines at the Point of Care

Across sub-Saharan Africa, **5.4 million Community Health Workers (CHWs)** serve as the primary healthcare contact for over one billion people (WHO Guideline on Health Policy and System Support to Optimize Community Health Worker Programmes, 2018). These frontline workers operate in rural and peri-urban settings where reliable internet is scarce, electricity is intermittent, and the nearest physician may be hours away. When a mother presents with a febrile child at a village health post, the CHW must make rapid triage decisions — often relying on memory alone.

National clinical guidelines exist to standardize care. Uganda's Clinical Guidelines 2023 (UCG 2023), published by the Ministry of Health, covers 24 chapters spanning emergencies, infectious diseases, maternal health, and chronic conditions. But at **800+ pages**, these guidelines are impractical to consult during a patient encounter. Paper copies deteriorate, keyword searches are impossible, and the prescriptive treatment protocols — with specific dosages by age, weight, and severity — demand precision that recall alone cannot guarantee.

**The gap is clear**: CHWs need instant, structured access to the exact guideline content relevant to their clinical question, presented in actionable language, available with or without connectivity.

This project was developed in partnership with the **World Health Organization (WHO)** (clinical guideline standards and digital health strategy), **Makerere University's Institute of Infectious Disease and Molecular Medicine (IIDMM)** (clinical validation expertise and local deployment knowledge), and **Decanlys** (mobile application engineering and field deployment). The Uganda Clinical Guidelines 2023 serves as our proof-of-concept document, but the pipeline is designed to ingest **any** structured clinical guideline PDF from any country.

---

## 2. MedGemma-Powered Two-Brain Architecture

We introduce a **Two-Brain architecture** that separates always-available retrieval (Brain 1) from AI-enhanced synthesis (Brain 2), ensuring CHWs always receive guideline content regardless of connectivity.

### Brain 1: On-Device Retrieval (Always Offline)

Brain 1 runs entirely on-device with zero network dependency:

- **Embedding**: MiniLM-L6-v2 quantized to ONNX (22MB, 384 dimensions), executed via ONNX Runtime on Android
- **Vector Search**: sqlite-vec extension enables approximate nearest neighbor search within a single SQLite file — no external database server required
- **Keyword Search**: FTS5 full-text search with BM25 scoring captures exact medical terminology that semantic search may miss (e.g., "amoxicillin 250mg")
- **Hybrid Fusion**: Reciprocal Rank Fusion (RRF, k=60) merges vector and keyword results, consistently outperforming either method alone
- **High-Risk Detection**: 46 clinically-curated danger signs (convulsions, severe bleeding, eclampsia) are matched against retrieved content, triggering red/amber visual warnings

Brain 1 returns ranked guideline excerpts with section headings and page references in **under 2 seconds** on a mid-range Android device.

### Brain 2: MedGemma Clinical Synthesis

**MedGemma 1.5 4B-it** runs on-device via llama.cpp to synthesize retrieved chunks into a structured clinical summary — no server or connectivity required:

```
User Query → Brain 1 Retrieval → Prompt Construction → MedGemma 1.5 4B-it → Summary
                                                                    ↓
                                                          Guardrail Validation
                                                          (Second MedGemma Pass)
```

**Why MedGemma 1.5?** MedGemma 1.5's enhanced medical domain pretraining provides a significant safety margin: it scores 69% on MedQA (vs 64% for 1.0), with +18% improvement on lab report interpretation and substantially improved medical text reasoning. Its clinical knowledge helps it follow grounding constraints more faithfully than general-purpose models, reducing the risk of plausible-sounding but fabricated clinical details. Standard LLMs frequently hallucinate dosages or invent treatment protocols — catastrophic errors in clinical settings. Combined with our retrieval-augmented approach and guardrail validation, MedGemma 1.5 produces summaries that are both grounded in the source guidelines and clinically coherent.

**Prompt Design**: Our synthesis prompt instructs MedGemma to answer *only* from the provided guideline excerpts, use CHW-appropriate language, structure responses with clear sections, include specific dosages and age ranges, and prominently flag danger signs. High-risk alerts detected by Brain 1 are injected into the prompt, forcing MedGemma to address them.

**Guardrail Self-Critique**: Every generated summary undergoes a second MedGemma inference pass evaluating five criteria:

| Criterion | Purpose |
|-----------|---------|
| **GROUNDING** | Every claim supported by source guidelines |
| **ACCURACY** | Dosages and treatment steps exactly match sources |
| **COMPLETENESS** | Critical safety information not omitted |
| **NO_FABRICATION** | No clinical information absent from sources |
| **APPROPRIATE_SCOPE** | Within CHW scope of practice |

If any criterion fails, the summary is flagged — but Brain 1 results remain accessible. **The system never blocks access to guideline content.**

### Extraction Pipeline

The upstream extraction pipeline processes any clinical guideline PDF into the searchable database:

1. **Docling** (IBM Research) handles PDF parsing with layout analysis, table structure recognition, and OCR
2. **HybridChunker** produces tokenization-aware chunks (1024 tokens) that preserve document structure
3. **Human review** via Streamlit UI validates extracted content before deployment
4. **MiniLM-L6-v2** generates embeddings for all chunks
5. The final SQLite database (~43MB for UCG 2023) is packaged into the Android APK

### Graceful Degradation

The architecture's key principle: **both brains always work.** With MedGemma running on-device via llama.cpp, the CHW gets both retrieval and synthesis fully offline. If the device lacks sufficient RAM for MedGemma (~4GB required), Brain 1 still provides ranked guideline excerpts with high-risk warnings. If the guardrail rejects a summary, the raw chunks remain visible. Every failure mode preserves access to the underlying clinical content.

---

## 3. Safety, Performance, and Impact

### Safety by Design

Clinical decision support demands a higher safety bar than general-purpose AI. Our multi-layered approach:

1. **Deterministic high-risk detection**: 46 curated danger signs trigger visual warnings before any LLM output. Terms span categories including neurological (convulsions, unconsciousness), pediatric (not able to drink, severe malnutrition), respiratory (chest indrawing, stridor), and maternal (vaginal bleeding, eclampsia). These are clinically validated, not model-generated.

2. **Retrieval grounding**: MedGemma synthesizes only from retrieved guideline excerpts — never from parametric knowledge alone. The prompt explicitly prohibits fabrication and requires page references.

3. **Guardrail validation**: The second inference pass catches grounding failures, dosage errors, and scope violations before the summary reaches the CHW.

4. **Permissive failure**: Guardrail errors or MedGemma unavailability never block Brain 1 results. The system defaults to showing the raw guideline content.

### Performance

| Metric | Target | Achieved (Python Pipeline) | Notes |
|--------|--------|---------------------------|-------|
| Search latency (Brain 1) | <2s | 13–37ms | Android target: <200ms |
| Synthesis + guardrail (Brain 2) | <60s | 30–60s | MedGemma 1.5 4B on-device via llama.cpp |
| Cold start | <5s | <5s | |
| Embedding inference | <500ms | <500ms | |
| Database size | <500MB | 43MB | |

**Search ablation study** (20 clinical queries, Python reference pipeline):

| Search Mode | Avg Latency | Behavior |
|-------------|-------------|----------|
| Vector-only (MiniLM-L6-v2) | 6ms | Captures semantic meaning (e.g., "febrile child" matches malaria sections) |
| Keyword-only (FTS5 BM25) | 5ms | Captures exact terminology (e.g., "amoxicillin", specific ICD codes) |
| Hybrid RRF (k=60) | 7ms | Draws from both sources in **19/20 queries (95%)** |

Vector and keyword search frequently retrieve different top results — for example, "snake bite first aid and antivenom treatment" returns generic "Management" via vector search but the specific "Snakebites" section via keyword search, while hybrid RRF surfaces "Criteria for referral for administration of antivenom" by combining both signal types. See `evaluation_results.md` for per-query details.

### Edge AI Readiness

The entire system runs on a **$150 Android phone** with zero cloud dependency:

- **On-device embedding**: ONNX Runtime runs MiniLM-L6-v2 inference on ARM processors
- **Single-file database**: sqlite-vec requires no external services — the entire guideline database is a single 43MB file
- **On-device MedGemma**: MedGemma 1.5 4B-it Q4_K_M (~2.5GB GGUF) runs on-device via llama.cpp (Llamatik wrapper) on devices with 4GB+ RAM. Both Brain 1 retrieval and Brain 2 synthesis work fully offline — no server, no cloud, no connectivity required
- **Complete offline operation**: The bundled APK contains the embedding model, guideline database, and MedGemma GGUF — a CHW can install and use the app immediately with no setup

### Reproducibility

The complete pipeline is open-source and reproducible:

```bash
# 1. Extract guidelines from any PDF
python -m extraction.src.pipeline --input guidelines.pdf

# 2. Run MedGemma synthesis (Python pipeline — requires Ollama for development testing)
ollama pull hf.co/unsloth/medgemma-1.5-4b-it-GGUF:Q4_K_M
python -m extraction.src.medgemma_synthesis --all

# 3. Download MedGemma GGUF for Android on-device inference
huggingface-cli download unsloth/medgemma-1.5-4b-it-GGUF \
    medgemma-1.5-4b-it-Q4_K_M.gguf \
    --local-dir android/app/src/main/assets/models/

# 4. Build Android app (MedGemma runs on-device — no Ollama needed)
cd android && ./gradlew assembleDebug
```

### Impact and Future Directions

**Immediate impact**: A CHW in rural Uganda can type "danger signs of malaria in children under 5" and receive structured, guideline-grounded clinical guidance in seconds — offline.

**Scalability**: The extraction pipeline accepts any clinical guideline PDF. Expanding to Kenya Clinical Guidelines, Ethiopia IMNCI protocols, or WHO IMCI guidelines requires only running the pipeline on the new document.

**Future with MedGemma**:
- **MedGemma multimodal**: Image analysis for clinical triage (skin conditions, wound assessment) — our `ImageAnalysisService` is already implemented
- **MedASR voice input**: Speech-to-text for hands-free clinical queries during patient encounters
- **Multi-guideline fusion**: Cross-referencing multiple national guidelines for harmonized clinical recommendations

MedGemma brings clinical AI to the point of care — where it matters most.

### Limitations & Future Work

This system has important limitations we are actively addressing. The guardrail validation uses the same model (MedGemma) that generated the summary — a self-grading approach that provides useful but not independent safety verification. We plan to supplement this with an NLI-based validator for stronger safety guarantees. The current evaluation uses automated metrics on a single guideline document (UCG 2023); clinical expert review with Makerere IIDMM physicians is planned before any field deployment. Additionally, while the extraction pipeline is designed to generalize to any clinical guideline PDF, it has only been validated end-to-end on the Uganda Clinical Guidelines, which is among the most structurally complex examples.

---

*Built with MedGemma 1.5 4B-it (Q4_K_M GGUF), Docling, sqlite-vec, and ONNX Runtime. Source code and reproduction instructions: https://github.com/maybenotconnor/chw-clinical-support*
