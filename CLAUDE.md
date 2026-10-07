You are building HNX26PSI01: Multimodal Document Intelligence, a working submission for a hackathon. Work autonomously end-to-end, but follow the phases and gates below. FIRST ACTION: save this entire brief as ./CLAUDE.md, then proceed.

# 1. PROBLEM
Build a system that ingests mixed PDFs (text, tables, charts, graphs, images, scanned pages, multi-column, messy layouts, poor-quality or damaged files) and answers questions about them. Every answer must cite where it came from: document, page, section (plus bbox for UI highlighting). An answer with no source scores zero. If a chart or table is needed, the visual itself must be analyzed as an image, not just its text extraction.

Example query the system must handle: "Compare production efficiency between Q2 and Q4, identify the three biggest reasons for the change, and show me the proof" (needs text + table + chart combined).

# 2. SCORING (optimize and measure for these)
1. Accuracy on questions mixing text + tables + charts + images
2. Evidence correctness: cited source must actually support the answer
3. Cross-document questions
4. Math and number handling
5. Tricky documents: scans, multi-column, messy layouts
6. Robustness: poor-quality or damaged documents

# 3. SUBMISSION REQUIREMENTS (must all exist in the final repo)
- Working system runnable end-to-end; public Git repo
- README with: what the project does, technologies/libraries/models, install deps, configure and run, how to reproduce the demonstrated results
- Data pipeline description (collect -> process -> index -> answer) with a diagram (mermaid in README)
- Core model/reasoning explanation
- Evidence and explanation outputs: citations, confidence scores, intermediate outputs (e.g., chart-to-data extraction), math formulas
- At least one full sample input -> output example (docs/sample_run.md)
- Scope Note: clearly separate MVP implemented vs stretch goals attempted
- Live demo readiness: one command to start everything; sample documents included; a script that runs the demo questions
- No PPT needed

# 4. HARD CONSTRAINTS
- 100% free: no paid services. LLM/VLM = Gemini API free tier via the google-genai SDK, key from env GEMINI_API_KEY. Everything else open source and local.
- Model names MUST come from config (.env: GEMINI_MODEL_FAST, GEMINI_MODEL_PRO, GEMINI_MODEL_LITE). Check current Gemini docs for valid model IDs before choosing defaults. Implement a fallback chain PRO -> FAST -> LITE on 429/quota errors with exponential backoff and jitter.
- Free-tier rate limits are tight: do all expensive VLM work ONCE at ingestion and cache by file content hash (and by crop hash). Query time should use at most ~3 to 5 Gemini calls.
- Never commit secrets. Provide .env.example, add .env and data caches to .gitignore. Scan git history before final commit.
- Only public or synthetic documents in the repo.
- Never fabricate evaluation numbers. All metrics in README must come from actually running eval/run_eval.py; paste real output. Do not claim 99%; report the measured results per question type honestly.
- The LLM must NEVER do arithmetic itself (see math tool).
- If evidence is insufficient, the system must answer "not found in the provided documents" rather than guess.

# 5. TECH STACK
Backend: Python 3.11, FastAPI, Uvicorn, Pydantic v2, python-dotenv
PDF: PyMuPDF (render + text + coordinates), pikepdf (repair), Docling (layout/tables/figures; if too heavy or failing, fall back gracefully to PyMuPDF blocks + Gemini page-image reading and note it in logs)
Scans: OpenCV (deskew, denoise, upscale, contrast), PaddleOCR or Tesseract (choose whichever installs cleanly; abstract behind an OCR interface with a second-engine fallback)
Retrieval: BAAI/bge-m3 (sentence-transformers, local CPU) for embeddings, rank-bm25, hybrid score fusion (RRF), bge-reranker-base for reranking, ChromaDB or Qdrant local mode for vectors
Tables: parse to pandas DataFrames; store markdown + CSV + crop image
LLM/VLM: google-genai (Gemini free tier)
Frontend: Next.js (App Router) + Tailwind + react-pdf
Eval/tests: pytest, custom eval runner
Test data generation: reportlab, matplotlib, Pillow, OpenCV

# 6. REPO STRUCTURE
/backend
  app/{main.py, config.py, schemas.py}
  ingestion/{repair.py, render.py, layout.py, ocr.py, tables.py, figures.py, pipeline.py}
  indexing/{embed.py, bm25.py, store.py}
  retrieval/{hybrid.py, rerank.py}
  agent/{planner.py, answerer.py, verifier.py, prompts.py, gemini_client.py}
  tools/{calc.py}
  tests/
/frontend  (Next.js: chat panel + PDF viewer with bbox highlight + evidence panel)
/data/{sample_docs, degraded, gold_questions.json}
/scripts/{make_test_pack.py, ingest_all.py, run_demo.py}
/eval/{run_eval.py, results.md}
/docs/{architecture.md, sample_run.md}
README.md, CLAUDE.md, .env.example, Makefile (make setup / ingest / eval / demo)

# 7. ARCHITECTURE
## 7.1 Ingestion (per PDF, idempotent, cached by SHA-256)
1. Repair with pikepdf; if a page is unreadable, skip it, log it in an ingestion report, never crash.
2. Render each page at ~200 DPI.
3. Detect missing/garbled text layer -> preprocess with OpenCV and OCR (with confidence score per block; if low, retry with second OCR engine or send page image to Gemini for transcription).
4. Layout analysis -> elements of type text | table | figure | caption | heading, each with metadata: element_id, doc_id, doc_name, page, bbox (normalized 0-1), section (nearest preceding heading), type, source_method (text-layer|ocr|vlm), confidence.
5. Tables: markdown + CSV + DataFrame + cropped image. Also ask Gemini (once, with the crop image) to verify/repair the table structure when the extracted table looks malformed (e.g., merged cells, scanned).
6. Charts/figures/images: crop, send to Gemini once; store JSON: caption, chart_type, axes labels/units, series, extracted data points (best effort), key trends. Keep the crop on disk. Index caption+data text, but ALSO keep the image so it can be passed to the VLM at answer time.
7. Persist everything under data/index/ as JSON + crops; build the embedding + BM25 indexes.

## 7.2 Query pipeline
1. Planner (Gemini FAST, JSON mode): decompose the question into sub-questions with expected modality (text/table/chart/any) and whether math is needed.
2. Retrieve per sub-question across ALL documents (optional doc filter): hybrid (dense + BM25, RRF) top 20 -> rerank top 6 to 8. Always include the page image for chart/figure hits.
3. Answerer (Gemini PRO with FAST fallback): receives retrieved text, table markdown, and the actual chart/table/page IMAGES. Must return strict JSON per schema: answer, reasoning_summary, claims[] each with {text, citations[{doc, page, section, element_id, bbox, quote}]}, calculations[], confidence.
4. Math tool: the model emits calculation requests as expressions over named values (each value linked to a cited element); tools/calc.py evaluates them in a restricted safe evaluator (ast-based, no eval/exec of arbitrary code, supports + - * / % pow, round, units/percent handling). Return formula, inputs, and result in the response.
5. Verifier (Gemini FAST, plus deterministic checks): for every claim, confirm the cited element supports it (LLM judge on the cited element text/image) and that quoted text actually appears in the element when it is text. Unsupported claims are retried once with a targeted re-retrieval, then dropped. Page numbers must be verified against real element metadata (never trust model-invented pages).
6. Abstain with "not found in the provided documents" when retrieval scores/verification fail thresholds. Return a calibrated confidence (combine retrieval score, verifier result, OCR confidence).

## 7.3 API
POST /ingest (upload PDF), GET /documents, POST /ask {question, doc_ids?} -> structured response, GET /page/{doc_id}/{page} (page image), GET /element/{element_id}, GET /health. Pydantic schemas for all.

## 7.4 Frontend
Left: chat. Right: PDF/page viewer (react-pdf or page images) that jumps to the cited page and draws highlight rectangles from bbox when a citation is clicked. Evidence panel: claims with citations, confidence badge, math formulas + inputs, chart-extracted data table, which modality each evidence came from. Upload box for new PDFs. Clean, simple, polished UI.

# 8. TEST PACK + EVAL (BUILD THIS FIRST, before the pipeline)
scripts/make_test_pack.py generates deterministic synthetic documents into data/sample_docs and data/degraded:
 a) quarterly_report_2025.pdf: narrative text, a Q1-Q4 production table (units, efficiency %, downtime hrs, defect rate), a bar chart and a line chart (efficiency trend), a paragraph explaining three causes of the Q2-to-Q4 change. Include at least one value present ONLY in a chart (not in text/table) to force visual analysis.
 b) research_paper_two_column.pdf: two-column layout, figure with caption, results table, equations-as-text.
 c) annual_summary_2025.pdf: a second related report for cross-document questions (e.g., compare plant A vs plant B, totals across both).
 d) scanned_quarterly_report.pdf: rasterized, rotated slightly, blurred, noisy, JPEG-compressed copy of (a).
 e) lowquality_photo_page.pdf: a heavily degraded single page.
 f) damaged.pdf: truncated/corrupted bytes of a valid PDF.
data/gold_questions.json: 50 questions minimum, each {id, question, type: text|table|chart|image|math|cross_doc|scanned|unanswerable, expected_answer, expected_numeric (if any), expected_docs, expected_pages, notes}. Generate the PDFs and the gold answers from the SAME source data in the script so ground truth is guaranteed correct. Include unanswerable questions where the correct behavior is abstaining.
eval/run_eval.py: runs all questions through the pipeline; reports (a) answer accuracy (numeric tolerance for numbers, LLM-judge or normalized match for text), (b) citation accuracy (cited doc+page matches expected), (c) abstention correctness, (d) breakdown by type and by clean-vs-degraded docs, (e) latency and Gemini call count. Writes eval/results.md and prints a table. Add a --fast mode (subset) to conserve free quota.

# 9. PHASES AND GATES (do in order; commit after each; do not skip gates)
P0 Scaffold repo, config, .env.example, .gitignore, Makefile, CLAUDE.md, gemini_client with fallback/backoff + caching + unit tests with mocked API.
P1 Test pack + gold set + eval runner skeleton. GATE: PDFs open correctly, gold answers verified against source data by a test.
P2 Ingestion (text, tables, OCR, repair). GATE: ingestion report shows all docs processed, damaged.pdf handled without crash; tests pass.
P3 Figure/chart VLM extraction + indexing + hybrid retrieval + rerank. GATE: retrieval recall@8 on gold expected pages measured and printed.
P4 Planner, answerer, math tool, verifier, abstention; /ask endpoint. GATE: run eval; fix failures; iterate on parsing/chunking/prompts until improvements plateau. Report real numbers.
P5 Frontend with citation highlighting and evidence panel. GATE: manual walkthrough of the example Q2-vs-Q4 question works end to end.
P6 README, docs/architecture.md (mermaid pipeline diagram), docs/sample_run.md (real captured output), Scope Note (MVP vs stretch), run_demo.py, final secret scan, final eval results committed.
Stretch only after P6 if time: ColPali/ColQwen page retrieval, confidence calibration plots, multilingual docs.

# 10. WORKING RULES
- Write tests as you go; run them. Never claim something works without running it.
- When a library fails to install or run, pick the fallback, log the decision in docs/architecture.md, and continue.
- Keep code typed, modular, and commented where non-obvious. No dead code.
- After each phase, print a short status: what was done, test/eval results, what's next.
- If you hit a blocker that needs the user (e.g., missing GEMINI_API_KEY), stop and ask once, clearly.

BEGIN with P0 now.
