# Sample run: Q2 vs Q4 efficiency (demo question)

**Input question**

```text
Compare production efficiency between Q2 and Q4, identify the three biggest reasons for the change, and show me the proof
```

**Prerequisites:** `GEMINI_API_KEY` in `.env`, index built via `python scripts/ingest_all.py`.

**Command**

```powershell
.\.venv\Scripts\python scripts\run_demo.py
```

The first demo question is the one above. Below is a **representative** structured response shape from `POST /ask` (field names match `backend/app/schemas.py`). Numeric values align with synthetic ground truth in `scripts/test_pack_data.py` (Q2 **84.0%**, Q4 **89.2%**, Δ **5.2** pp).

```json
{
  "answer": "Production efficiency rose from 84.0% in Q2 to 89.2% in Q4 (+5.2 percentage points). The report cites three drivers: predictive maintenance reducing downtime, operator cross-training for faster changeovers, and a supplier quality program lowering defect rates.",
  "reasoning_summary": "Table values for Q2/Q4 efficiency plus narrative paragraph listing three causes; bar/line charts support the trend.",
  "claims": [
    {
      "text": "Q2 efficiency was 84.0% and Q4 was 89.2%.",
      "citations": [
        {
          "doc_id": "b3ba0321a36f0f0c",
          "doc_name": "quarterly_report_2025.pdf",
          "page": 1,
          "section": "Production summary (table)",
          "element_id": "...",
          "bbox": { "x0": 0.1, "y0": 0.2, "x1": 0.9, "y1": 0.35 },
          "quote": "Q2"
        }
      ]
    },
    {
      "text": "Three reasons for Q2–Q4 improvement are listed in the narrative section.",
      "citations": [
        {
          "doc_name": "quarterly_report_2025.pdf",
          "page": 1,
          "section": "Drivers of Q2–Q4 efficiency change",
          "quote": "Predictive maintenance rollout"
        }
      ]
    }
  ],
  "calculations": [
    {
      "name": "efficiency_delta_q2_q4",
      "formula": "q4 - q2",
      "inputs": { "q4": 89.2, "q2": 84.0 },
      "result": 5.2
    }
  ],
  "confidence": 0.82,
  "abstained": false
}
```

**UI:** Open `http://localhost:3000` after `.\scripts\start.ps1`. Click a citation in the evidence panel to jump to the page and show the bbox highlight on the rendered page image.

**Regenerate this file:** Run `python scripts/run_demo.py` with a valid API key and paste the first JSON block from the console output here.
