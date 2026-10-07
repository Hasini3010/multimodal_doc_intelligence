# How to run Multimodal Document Intelligence

Step-by-step guide to install, configure, start the app, upload your own PDFs, and reproduce the demo.

## Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for the Next.js UI)
- An **LLM API key** (NVIDIA NIM free tier by default, or Gemini — see [Configure](#configure-environment))
- Optional: [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) for better scanned pages

## 1. Clone and install

From the repository root:

**Windows (recommended)**

```powershell
.\scripts\setup.ps1
```

**Manual**

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r backend\requirements.txt
copy .env.example .env
cd frontend
npm install
cd ..
```

Generate synthetic sample PDFs and build the search index (needed for demo questions):

```powershell
.\.venv\Scripts\python scripts\make_test_pack.py
.\.venv\Scripts\python scripts\ingest_all.py
```

The first `ingest_all.py` run downloads embedding models (~1–2 GB) and can take several minutes.

## 2. Configure environment

Copy `.env.example` to `.env` and edit:

| Variable | Purpose |
| --- | --- |
| `LLM_PROVIDER` | `nvidia` (default) or `gemini` |
| `NVIDIA_API_KEY` | Required when `LLM_PROVIDER=nvidia` — from [build.nvidia.com](https://build.nvidia.com/) |
| `GEMINI_API_KEY` | Required when `LLM_PROVIDER=gemini` — from [Google AI Studio](https://aistudio.google.com/apikey) |
| `BACKEND_URL` | Where Next.js proxies API calls (default `http://127.0.0.1:8000`) |

**Important for upload in the UI:** leave `NEXT_PUBLIC_API_URL` **unset** (or commented out) so the browser uses the same-origin `/api` proxy. If you set `NEXT_PUBLIC_API_URL=http://localhost:8000`, uploads can fail due to browser CORS unless you also set `CORS_ORIGINS` to match your UI URL.

## 3. Start the system

**One command (backend + frontend)**

```powershell
.\scripts\start.ps1
```

- UI: [http://localhost:3000](http://localhost:3000)
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

**Two terminals**

Terminal A — API:

```powershell
cd backend
..\.venv\Scripts\uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Terminal B — UI:

```powershell
cd frontend
npm run dev
```

Confirm the header shows **API Online**. If it shows **API Offline**, the backend is not reachable on port 8000.

## 4. Upload your own PDFs

1. Open [http://localhost:3000](http://localhost:3000).
2. Click **Upload PDF** (top right).
3. Select a `.pdf` file. Ingestion and indexing run on the server; large files or first-time embedding download can take 1–3 minutes.
4. When finished, a green banner confirms the upload and the document appears in the dropdown. Page previews load from the indexed pages.
5. Ask a question in the chat panel. Answers include citations; click a citation to jump to the page and highlight the source region.

Upload via API (optional):

```powershell
curl.exe -F "file=@C:\path\to\your.pdf" http://localhost:8000/ingest
```

Uploaded files are stored under `data/uploads/`; parsed content under `data/index/<doc_id>/`.

## 5. Reproduce the demonstrated results

### UI demo (Q2 vs Q4)

1. Complete steps 1–3 above with a valid LLM key in `.env`.
2. Ensure sample docs are ingested (`scripts\ingest_all.py`).
3. Start the app and open the UI.
4. Use the suggested **Q2 vs Q4 production efficiency** question (or type it in the chat).
5. Verify: answer text, evidence panel with claims/citations, page viewer jumps to cited pages.

### CLI demo

```powershell
.\.venv\Scripts\python scripts\run_demo.py
```

### Evaluation (metrics for README)

Retrieval-only (no LLM key):

```powershell
.\.venv\Scripts\python eval\run_eval.py --retrieval-only
```

Full pipeline (uses LLM quota):

```powershell
.\.venv\Scripts\python eval\run_eval.py --fast
```

Results are written to `eval/results.md`.

### Example request/response

See [sample_run.md](./sample_run.md) for a captured `/ask` JSON shape.

## 6. Troubleshooting

| Symptom | Fix |
| --- | --- |
| **API Offline** in UI | Start uvicorn on port 8000; check firewall. |
| Upload fails immediately | Remove `NEXT_PUBLIC_API_URL` from `.env`, restart `npm run dev`. |
| Upload hangs then errors | Wait for first embedding model download; check backend terminal logs. |
| Questions return 503 | Set `NVIDIA_API_KEY` or `GEMINI_API_KEY` and matching `LLM_PROVIDER`. |
| Empty document list | Run `scripts\ingest_all.py` or upload a PDF successfully. |

## 7. Tests

```powershell
.\.venv\Scripts\python -m pytest backend\tests -m "not slow" -q
```

For more architecture detail, see [architecture.md](./architecture.md) and the root [README.md](../README.md).
