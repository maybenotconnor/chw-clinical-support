# Demo Video Script — MedGemma Clinical Decision Support for CHWs

**Duration**: 3 minutes | **Format**: Screen recording + voiceover

---

## Shot 1: Problem & App Intro (0:00–0:25)

**Visual**: Title card → brief CHW/clinic imagery → app on device

**Narration**:
> "5.4 million Community Health Workers across sub-Saharan Africa are often the only point of healthcare contact. When a CHW needs clinical guidance, national guidelines exist — but they're 800 pages long, and there's often no internet. We built an app, with WHO and Makerere University, that puts MedGemma-powered guideline search in a CHW's pocket — fully offline."

---

## Shot 2: Live Demo — Brain 1 + Brain 2 (0:25–1:30)

**Visual**: App on device → type query → results appear → summary streams in

**Demo**: Type **"danger signs of malaria in children under 5"**
- Brain 1 results appear in <400ms — show the speed
- Red high-risk warning banner appears (convulsions, not able to drink...)
- Scroll through guideline excerpts while MedGemma generates in background
- Summary streams in with structured sections: Danger Signs, Treatment, Referral Criteria

**Narration**:
> "The CHW types a clinical question. Brain 1 — running entirely on-device — returns relevant guideline excerpts in under 400 milliseconds. Notice the red warning banner: the system automatically detected danger signs like convulsions and inability to drink. The CHW can read these excerpts immediately while MedGemma works in the background. The AI then synthesizes the retrieved chunks into a structured clinical summary — with specific dosages, age ranges, and referral criteria. Everything is grounded in the Uganda Clinical Guidelines."

---

## Shot 3: Offline & Safety Demo (1:30–2:25)

**Visual**: Toggle airplane mode → repeat search → results + summary appear → show off-topic query

**Demo**:
1. Enable **Airplane Mode** (show toggle clearly)
2. Type: **"treatment of severe dehydration in a child"**
3. Brain 1 results appear immediately — same speed
4. MedGemma summary starts streaming — fully on-device
5. Briefly show off-topic query returning no clinical results

**Narration**:
> "Now I've turned on airplane mode — no internet at all. The same search works identically. Brain 1 returns guideline excerpts in under 400 milliseconds. MedGemma is also running right on the device via llama.cpp — no server, no cloud. Both brains work fully offline.
>
> Safety is built into the architecture. MedGemma only synthesizes from retrieved guideline excerpts — never from parametric knowledge. If Brain 2 fails on a low-RAM device, the CHW still has full access to the guideline excerpts. And an off-topic question correctly returns no clinical results."

---

## Shot 4: Architecture & Close (2:25–3:00)

**Visual**: Brief architecture overlay → return to app → closing card with partner logos

**Narration**:
> "The Two-Brain architecture: Brain 1 embeds the query with MiniLM, searches with both vector and keyword search, fuses results, and flags danger signs — all in under 400 milliseconds. Brain 2 runs MedGemma 1.5 4B on-device to synthesize a clinical summary. Everything runs on a $150 phone.
>
> Built with WHO, Makerere University, and Decanlys — designed to scale to any country's clinical guidelines. MedGemma brings clinical AI to the point of care."

**End card**: Project name, partner logos, "Open Source — Built with MedGemma"

---

## Production Notes

- Screen recording via `scrcpy` or Android Studio emulator (1080p+)
- Record voiceover separately; keep transitions tight to stay under 3:00
- Key moments: sub-400ms search, red danger sign banner, airplane mode working, summary streaming
