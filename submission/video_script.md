# Demo Video Script — MedGemma Clinical Decision Support for CHWs

**Duration**: 3 minutes (max)
**Format**: Screen recording + voiceover narration
**Tools**: Android emulator or device, terminal for pipeline demo

---

## Shot 1: Problem Context (0:00–0:30)

**Visual**: Title card → stock footage/slides of CHWs in rural clinics → UCG 2023 PDF cover → map of Uganda

**Narration**:
> "Five point four million Community Health Workers across sub-Saharan Africa are the first — and often only — point of healthcare contact for over a billion people. When a mother brings a febrile child to a village health post, the CHW must make triage decisions quickly. National clinical guidelines exist, but they're 800 pages long, and there's often no internet.
>
> We built a clinical decision support app — in partnership with the WHO, Makerere University, and Decanlys — that puts MedGemma-powered guideline search in a CHW's pocket."

**Transition**: Cut to app on device/emulator

---

## Shot 2: Live Demo — Brain 1 + Brain 2 (0:30–1:15)

**Visual**: App open on SearchScreen → type query → results appear → summary streams

**Action sequence**:
1. Show the app home screen (clean Material 3 UI)
2. Type: **"danger signs of malaria in children under 5"**
3. Brain 1 results appear in **<2 seconds** — highlight the timing indicator
4. **Red high-risk warning banner** appears at top: "DANGER SIGNS DETECTED: convulsions, not able to drink..."
5. Scroll through retrieved guideline chunks — show page references and heading paths
6. MedGemma summary starts streaming below the results
7. Summary completes with structured sections: Danger Signs, Immediate Actions, Treatment, Referral Criteria

**Narration**:
> "The CHW types their clinical question. Brain 1 — running entirely on-device — returns relevant guideline excerpts in under 200 milliseconds. Notice the red warning banner: the system automatically detected danger signs in the content, like convulsions and inability to drink.
>
> Meanwhile, MedGemma synthesizes the retrieved chunks into a structured clinical summary — with specific dosages, age ranges, and clear referral criteria. Everything is grounded in the Uganda Clinical Guidelines."

---

## Shot 3: Safety Demo — Guardrail Failure + Fallback (1:15–1:45)

**Visual**: Show guardrail validation → show a failure case → show Brain 1 fallback

**Action sequence**:
1. Point out the guardrail validation checkmark on the previous summary
2. Briefly show/mention the 5 criteria: GROUNDING, ACCURACY, COMPLETENESS, NO_FABRICATION, APPROPRIATE_SCOPE
3. Show a query where the guardrail flags an issue — or demonstrate that when MedGemma generates content beyond the guidelines, the guardrail catches it and the summary is marked as unvalidated
4. Highlight: **even when the summary fails validation, the CHW still has full access to the retrieved guideline excerpts** — Brain 1 results are never blocked
5. Briefly show an off-topic query: **"What is the best restaurant in Kampala?"** — system returns no relevant clinical results

**Narration**:
> "Every MedGemma summary passes through a guardrail — a second inference pass that validates grounding, accuracy, and safety. Watch what happens when MedGemma's summary goes beyond the source guidelines — the guardrail catches it. But critically, the CHW still sees the raw guideline excerpts. Brain 1 results are never blocked by a guardrail failure.
>
> And an off-topic question? The system correctly recognizes this isn't a clinical query. Safety first."

---

## Shot 4: Offline Demo — Airplane Mode (1:45–2:15)

**Visual**: Toggle airplane mode → repeat a search → results AND summary appear

**Action sequence**:
1. Open device settings, enable **Airplane Mode** (show the toggle clearly)
2. Return to the app
3. Type: **"treatment of severe dehydration in a child"**
4. Brain 1 results appear immediately — same speed, same quality
5. MedGemma summary starts streaming — **fully on-device, no internet needed**
6. Highlight: high-risk warnings still work, guardrail validation still runs

**Narration**:
> "Now here's the critical part. I've turned on airplane mode — no internet whatsoever. The CHW types the same kind of clinical question, and Brain 1 still returns guideline excerpts in under 2 seconds. But watch — MedGemma is also running, right on the device, via llama.cpp. The AI summary streams in, the guardrail validates it, all completely offline.
>
> Both brains work without connectivity. This is true edge AI — the entire clinical decision support system runs on a phone with no server, no cloud, no internet."

---

## Shot 5: Architecture Walkthrough (2:15–2:35)

**Visual**: Architecture diagram (slide or overlay)

**Diagram to show**:
```
┌─────────────────────────────────────────────────────┐
│  Brain 1 (On-Device Retrieval)                       │
│  Query → MiniLM ONNX → sqlite-vec + FTS5 → RRF      │
│                                        ↓             │
│  Brain 2 (On-Device Synthesis)   Ranked Results      │
│  MedGemma 1.5 4B via llama.cpp → Guardrail → Summary │
└─────────────────────────────────────────────────────┘
          ▲ Everything runs on-device — zero cloud ▲
```

**Narration**:
> "The Two-Brain architecture: Brain 1 embeds the query, searches locally with both vector and keyword search, fuses results, and flags danger signs. Brain 2 runs MedGemma 1.5 4B via llama.cpp to synthesize a validated summary. Everything — embedding, retrieval, synthesis, guardrail — runs on-device. There is no connectivity boundary."

---

## Shot 6: Impact & Close (2:35–3:00)

**Visual**: Return to app → closing title card with partner logos

**Narration**:
> "Built with WHO, Makerere University, and Decanlys, this system is designed to scale. The extraction pipeline works on any clinical guideline PDF — from Uganda to Kenya to any country with national guidelines.
>
> MedGemma brings clinical AI to the point of care — where it matters most."

**End card**: Project name, partner logos, "Open Source — Built with MedGemma"

---

## Production Notes

- **Screen recording**: Use Android Studio emulator or physical device with `scrcpy`
- **Resolution**: 1920x1080 or higher
- **Voiceover**: Record separately, clean audio
- **B-roll**: Optional stock footage of CHWs, rural clinics (royalty-free)
- **Timing**: Each section is tight — rehearse transitions to stay under 3:00
- **Key moments to emphasize**: (1) sub-200ms search latency, (2) red danger sign banner, (3) airplane mode still working, (4) guardrail validation
