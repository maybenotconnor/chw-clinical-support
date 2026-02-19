# Evaluation Results: Ablation Study & Per-Query Analysis

**Methodology**: Each of the 20 test queries was run through three search configurations:
- **Vector-only**: MiniLM-L6-v2 semantic search via sqlite-vec
- **Keyword-only**: BM25 full-text search via FTS5
- **Hybrid RRF**: Reciprocal Rank Fusion (k=60) combining both methods

All measurements taken on the Python reference pipeline (not Android device).

---

## Summary Statistics

| Metric | Vector-Only | Keyword-Only | Hybrid RRF |
|--------|-------------|--------------|------------|
| Queries with top-3 results | 20/20 | 20/20 | 20/20 |
| Avg search latency | 13ms | 5ms | 9ms |
| Hybrid draws from both sources | — | — | 19/20 (95%) |

**Key finding**: Hybrid RRF retrieves from both vector and keyword sources in 19/20 queries, capturing semantic matches that keyword search misses and exact terminology that vector search misses.

---

## Per-Query Results

| # | Query | Vector Top-1 Heading | Keyword Top-1 Heading | Hybrid Top-1 Heading | Alerts (V/K/H) | Hybrid Diverse |
|---|-------|---------------------|----------------------|---------------------|----------------|----------------|
| 1 | What are the danger signs of malaria in children u... | 2.5.2.1 Uncomplicated Malaria  | Education messages to mothers  | 2.5.2.1 Uncomplicated Malaria  | 2/6/6 | Yes |
| 2 | How do you treat severe dehydration in a child? | 1.1.3.1 Dehydration in Childre | 17.3.12.2  Assessing Appetite  | Classify and treat as below | 3/1/3 | Yes |
| 3 | Management of hypertension in adults | Hypertension | Prevention | Prevention | 0/3/0 | Yes |
| 4 | What are the symptoms of tuberculosis? | Pulmonary TB | 17.3.12.2  Assessing Appetite  | Differential diagnosis | 1/1/1 | Yes |
| 5 | First aid for snake bite | Management | 1.2.1.1  Snakebites | 1.2.1.1  Snakebites | 0/4/1 | Yes |
| 6 | Danger signs in pregnancy that require immediate r... | Advise mother on danger signs  | Then counsel the mother on | Then counsel the mother on | 7/7/7 | Yes |
| 7 | How to manage pneumonia in children | 5.2.9.1 Pneumonia in an Infant | 5.2.9.4  Pneumonia by Speci/un | 5.2.9.1 Pneumonia in an Infant | 3/2/3 | Yes |
| 8 | Treatment of uncomplicated malaria | Treatment of uncomplicated mal | Treatment of uncomplicated mal | Treatment of uncomplicated mal | 2/1/2 | Yes |
| 9 | Signs and management of severe malnutrition | 19.2.1.2  Assessing Malnutriti | Differential diagnosis | Differential diagnosis | 1/3/5 | No |
| 10 | HIV testing and counseling guidelines | Check for HIV infection | Check for HIV infection | Check for HIV infection | 1/0/3 | Yes |
| 11 | Management of diabetes mellitus type 2 | Management of Type 2 Diabetes | 8.1.4 Diabetic Ketoacidosis (D | Causes | 0/1/0 | Yes |
| 12 | How to assess a patient with chest pain | Clinical Investigation | 5.3.1.3 Post-TB patient manage | Clinical Investigation | 4/1/2 | Yes |
| 13 | What are the danger signs in a newborn? | Then counsel the mother on | Advise mother on danger signs  | Then counsel the mother on | 9/8/9 | Yes |
| 14 | Snake bite first aid and antivenom treatment | Management | 1.2.1.1  Snakebites | Criteria for referral for admi | 0/3/1 | Yes |
| 15 | When should a CHW refer a patient to hospital? | Look | Principles of Management | Management | 3/3/3 | Yes |
| 16 | Dosage of amoxicillin for pneumonia in children un... | Management of pneumonia | Management of pneumonia | Management of pneumonia | 3/2/7 | Yes |
| 17 | How to prevent mother to child transmission of HIV | 3.1.9 Mother-to-Child Transmis | Management | Management | 0/0/0 | Yes |
| 18 | Management of severe acute malnutrition in childre... | If the child has moderate acut | Weight for-Height/Length | Weight for-Height/Length | 2/3/3 | Yes |
| 19 | Treatment of uncomplicated urinary tract infection | TREATMENT | 7.2 UROLOGICAL DISEASES | 7.2 UROLOGICAL DISEASES | 1/0/0 | Yes |
| 20 | Epilepsy seizure management and first aid | Management | 9.1.1 Epilepsy ICD10 CODE: G40 | General principles | 2/0/2 | Yes |

---

## Latency Breakdown

| # | Query | Vector (ms) | Keyword (ms) | Hybrid (ms) |
|---|-------|-------------|--------------|-------------|
| 1 | What are the danger signs of malaria in children u... | 159 | 27 | 10 |
| 2 | How do you treat severe dehydration in a child? | 7 | 4 | 9 |
| 3 | Management of hypertension in adults | 6 | 4 | 13 |
| 4 | What are the symptoms of tuberculosis? | 6 | 5 | 10 |
| 5 | First aid for snake bite | 5 | 3 | 7 |
| 6 | Danger signs in pregnancy that require immediate r... | 6 | 3 | 8 |
| 7 | How to manage pneumonia in children | 5 | 4 | 7 |
| 8 | Treatment of uncomplicated malaria | 5 | 3 | 8 |
| 9 | Signs and management of severe malnutrition | 5 | 4 | 8 |
| 10 | HIV testing and counseling guidelines | 6 | 3 | 8 |
| 11 | Management of diabetes mellitus type 2 | 5 | 4 | 9 |
| 12 | How to assess a patient with chest pain | 5 | 4 | 9 |
| 13 | What are the danger signs in a newborn? | 4 | 4 | 8 |
| 14 | Snake bite first aid and antivenom treatment | 5 | 3 | 8 |
| 15 | When should a CHW refer a patient to hospital? | 5 | 3 | 8 |
| 16 | Dosage of amoxicillin for pneumonia in children un... | 5 | 4 | 8 |
| 17 | How to prevent mother to child transmission of HIV | 5 | 5 | 10 |
| 18 | Management of severe acute malnutrition in childre... | 5 | 4 | 10 |
| 19 | Treatment of uncomplicated urinary tract infection | 6 | 4 | 8 |
| 20 | Epilepsy seizure management and first aid | 5 | 3 | 8 |

---

## Failure Analysis

### Queries where vector and keyword returned different top results

These cases illustrate why hybrid search matters:

**Query**: "What are the danger signs of malaria in children under 5?"
- Vector retrieved: 2.5.2.1 Uncomplicated Malaria ICD 10 CODE: B50.9
- Keyword retrieved: Education messages to mothers and the community
- Hybrid retrieved: 2.5.2.1 Uncomplicated Malaria ICD 10 CODE: B50.9
- Vector found 3 unique chunks not in keyword results; keyword found 3 unique chunks not in vector results

**Query**: "How do you treat severe dehydration in a child?"
- Vector retrieved: 1.1.3.1 Dehydration in Children under 5 years
- Keyword retrieved: 17.3.12.2  Assessing Appetite and Feeding
- Hybrid retrieved: Classify and treat as below
- Vector found 5 unique chunks not in keyword results; keyword found 5 unique chunks not in vector results

**Query**: "Management of hypertension in adults"
- Vector retrieved: Hypertension
- Keyword retrieved: Prevention
- Hybrid retrieved: Prevention
- Vector found 4 unique chunks not in keyword results; keyword found 4 unique chunks not in vector results

---

## Limitations

1. **Self-evaluation**: These results use automated heading matching, not clinical expert review. We plan independent clinical validation with Makerere IIDMM physicians before deployment.
2. **Single document**: All queries are evaluated against the Uganda Clinical Guidelines 2023. Generalization to other guideline PDFs requires additional testing.
3. **Guardrail self-grading**: The guardrail uses the same model (MedGemma) that generated the summary and is currently disabled on-device due to inference time constraints (~3 min per pass on Snapdragon 845). An independent NLI-based validator would provide stronger safety guarantees.
4. **Python pipeline latency**: Timings reflect the Python reference implementation. Measured on-device (OnePlus 6T, Snapdragon 845): Brain 1 search ~364ms, Brain 2 synthesis ~3 min.
