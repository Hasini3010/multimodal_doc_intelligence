"use client";

import { ChatPanel } from "@/components/ChatPanel";
import { EvidencePanel } from "@/components/EvidencePanel";
import { PageViewer } from "@/components/PageViewer";
import {
  askQuestion,
  documentPdfUrl,
  getHealth,
  listDocuments,
  uploadPdf,
  type AskResponse,
  type Citation,
  type DocumentSummary,
} from "@/lib/api";
import { useCallback, useEffect, useRef, useState } from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faFileLines,
  faCircleDot,
  faLayerGroup,
  faCloudArrowUp,
  faRotateRight,
  faFilePdf,
  faChevronLeft,
  faChevronRight,
  faXmark,
  faArrowUpRightFromSquare,
  faSpinner,
} from "@fortawesome/free-solid-svg-icons";

type Message = { role: "user" | "assistant"; text: string };

export default function HomePage() {
  const [docs, setDocs] = useState<DocumentSummary[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [highlight, setHighlight] = useState<Citation["bbox"] | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [response, setResponse] = useState<AskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [apiOk, setApiOk] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadNotice, setUploadNotice] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const refreshDocs = useCallback(async () => {
    try {
      const [list] = await Promise.all([listDocuments(), getHealth().catch(() => null)]);
      setDocs(list);
      if (list.length && (!selectedDocId || !list.some((d) => d.doc_id === selectedDocId))) {
        setSelectedDocId(list[0].doc_id);
        setPage(1);
      }
      setApiOk(true);
    } catch {
      setApiOk(false);
    }
  }, [selectedDocId]);

  useEffect(() => {
    refreshDocs();
  }, [refreshDocs]);

  const onAsk = async (question: string) => {
    setMessages((m) => [...m, { role: "user", text: question }]);
    setLoading(true);
    try {
      const res = await askQuestion(question);
      setResponse(res);
      setMessages((m) => [...m, { role: "assistant", text: res.answer }]);
      const first = res.claims[0]?.citations[0];
      if (first?.doc_id) {
        setSelectedDocId(first.doc_id);
        setPage(first.page);
        setHighlight(first.bbox ?? null);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Request failed";
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: `Inquiry failed: ${msg}. Make sure the backend server is running on http://localhost:8000.`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const onCitationClick = (c: Citation) => {
    setSelectedDocId(c.doc_id);
    setPage(c.page);
    setHighlight(c.bbox ?? null);
  };

  const onUpload = async (file: File) => {
    if (!apiOk) {
      alert(
        "Backend API is offline. Start the server on port 8000 (see docs/how-to-run.md), then click Refresh."
      );
      return;
    }
    if (file.type && file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      alert("Please choose a PDF file.");
      return;
    }
    setUploadNotice(null);
    setUploading(true);
    try {
      const report = await uploadPdf(file);
      await refreshDocs();
      setSelectedDocId(report.doc_id);
      setPage(1);
      setHighlight(null);
      setUploadNotice(
        `Uploaded “${report.doc_name}” (${report.pages_total} page${report.pages_total === 1 ? "" : "s"}). You can ask questions about it now.`
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Document upload failed";
      alert(msg);
      setUploadNotice(null);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const clearMessages = () => {
    setMessages([]);
    setResponse(null);
    setHighlight(null);
  };

  const selected = docs.find((d) => d.doc_id === selectedDocId);
  const totalPages = selected?.page_count ?? 1;

  return (
    <main className="flex min-h-screen flex-col bg-slate-50 text-slate-800">
      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200 bg-white/95 px-5 py-3 shadow-subtle backdrop-blur">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600 text-white shadow-sm">
            <FontAwesomeIcon icon={faFileLines} className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold tracking-tight text-slate-900">
                Document Intelligence
              </span>
              <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-600 border border-slate-200">
                Audit Edition
              </span>
            </div>
            <p className="text-[11px] text-slate-500">
              Grounded multimodal QA with verifiable citations
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* API Health indicator */}
          <div
            className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium border ${
              apiOk
                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                : "bg-amber-50 text-amber-700 border-amber-200"
            }`}
            title={apiOk ? "Backend API is online and healthy" : "Backend API is unreachable on :8000"}
          >
            <FontAwesomeIcon
              icon={faCircleDot}
              className={`h-2.5 w-2.5 ${apiOk ? "text-emerald-500" : "text-amber-500"}`}
            />
            <span>{apiOk ? "API Online" : "API Offline"}</span>
          </div>

          {/* Document Count Badge */}
          <div className="hidden sm:flex items-center gap-1.5 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600">
            <FontAwesomeIcon icon={faLayerGroup} className="h-3 w-3 text-slate-400" />
            <span>
              {docs.length} {docs.length === 1 ? "Document" : "Documents"}
            </span>
          </div>

          {/* Refresh Docs Button */}
          <button
            type="button"
            onClick={refreshDocs}
            title="Refresh documents list"
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-colors"
          >
            <FontAwesomeIcon icon={faRotateRight} className="h-3 w-3" />
          </button>

          {/* Upload Button */}
          <label
            className={`flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm transition-colors ${
              uploading || !apiOk
                ? "cursor-not-allowed bg-blue-400"
                : "cursor-pointer bg-blue-600 hover:bg-blue-700"
            }`}
            title={
              !apiOk
                ? "Start the backend API before uploading"
                : "Upload a PDF — it will be ingested and indexed for Q&A"
            }
          >
            {uploading ? (
              <FontAwesomeIcon icon={faSpinner} className="h-3 w-3 animate-spin" />
            ) : (
              <FontAwesomeIcon icon={faCloudArrowUp} className="h-3 w-3" />
            )}
            <span>{uploading ? "Ingesting & indexing…" : "Upload PDF"}</span>
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf,.pdf"
              className="hidden"
              disabled={uploading || !apiOk}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void onUpload(f);
              }}
            />
          </label>
        </div>
      </header>

      {uploadNotice && (
        <div className="border-b border-emerald-200 bg-emerald-50 px-5 py-2 text-xs text-emerald-800">
          {uploadNotice}
        </div>
      )}

      {/* Main 3-Column Workspace */}
      <div className="grid flex-1 grid-cols-1 gap-4 p-4 lg:grid-cols-12 lg:h-[calc(100vh-4.25rem)]">
        {/* Left: Chat / Inquiry Column */}
        <section className="lg:col-span-4 h-full min-h-[500px]">
          <ChatPanel
            onAsk={onAsk}
            loading={loading}
            messages={messages}
            onClear={clearMessages}
          />
        </section>

        {/* Middle: Document Page Inspector Column */}
        <section className="flex flex-col gap-3 lg:col-span-5 h-full overflow-hidden">
          {/* Document & Page Toolbar */}
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200 bg-white p-2.5 shadow-sm">
            <div className="flex items-center gap-2 flex-1 min-w-[200px]">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-slate-100 text-slate-600">
                <FontAwesomeIcon icon={faFilePdf} className="h-3.5 w-3.5 text-rose-600" />
              </div>
              <select
                value={selectedDocId ?? ""}
                onChange={(e) => {
                  setSelectedDocId(e.target.value);
                  setPage(1);
                  setHighlight(null);
                }}
                className="w-full truncate rounded-md border border-slate-200 bg-slate-50/70 px-2.5 py-1 text-xs font-medium text-slate-800 outline-none focus:border-blue-500 focus:bg-white"
              >
                {docs.length === 0 ? (
                  <option value="">No documents loaded</option>
                ) : (
                  docs.map((d) => (
                    <option key={d.doc_id} value={d.doc_id}>
                      {d.doc_name} ({d.page_count} {d.page_count === 1 ? "page" : "pages"})
                    </option>
                  ))
                )}
              </select>
            </div>

            {/* Pagination Controls */}
            <div className="flex items-center gap-1.5 shrink-0">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                title="Previous page"
                className="flex h-7 w-7 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <FontAwesomeIcon icon={faChevronLeft} className="h-2.5 w-2.5" />
              </button>

              <div className="flex items-center gap-1 text-xs text-slate-600">
                <span className="text-[11px] text-slate-400">Page</span>
                <input
                  type="number"
                  min={1}
                  max={totalPages}
                  value={page}
                  onChange={(e) => {
                    const val = Number(e.target.value);
                    if (val >= 1 && val <= totalPages) setPage(val);
                  }}
                  className="w-11 rounded-md border border-slate-200 bg-slate-50/80 px-1.5 py-0.5 text-center text-xs font-semibold text-slate-800 outline-none focus:border-blue-500 focus:bg-white"
                />
                <span className="text-[11px] text-slate-400">of {totalPages}</span>
              </div>

              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                title="Next page"
                className="flex h-7 w-7 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <FontAwesomeIcon icon={faChevronRight} className="h-2.5 w-2.5" />
              </button>

              {/* External PDF view button */}
              {selectedDocId && (
                <a
                  href={documentPdfUrl(selectedDocId)}
                  target="_blank"
                  rel="noopener noreferrer"
                  title="Open source PDF in new browser tab"
                  className="flex h-7 w-7 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-500 hover:bg-slate-50 hover:text-blue-600"
                >
                  <FontAwesomeIcon icon={faArrowUpRightFromSquare} className="h-2.5 w-2.5" />
                </a>
              )}
            </div>
          </div>

          {/* Active Highlight Banner if active */}
          {highlight && (
            <div className="flex items-center justify-between rounded-lg border border-amber-200 bg-amber-50/80 px-3 py-1.5 text-xs text-amber-800 shadow-subtle">
              <span className="font-medium">
                Bounding box highlight active for cited claim
              </span>
              <button
                type="button"
                onClick={() => setHighlight(null)}
                className="flex items-center gap-1 rounded px-1.5 py-0.5 font-semibold text-amber-900 hover:bg-amber-100 transition-colors"
                title="Dismiss highlight overlay"
              >
                <FontAwesomeIcon icon={faXmark} className="h-3 w-3" />
                <span>Clear</span>
              </button>
            </div>
          )}

          {/* Page Image Viewer Canvas */}
          <div className="flex-1 overflow-hidden">
            {selectedDocId ? (
              <PageViewer docId={selectedDocId} page={page} highlight={highlight} />
            ) : (
              <div className="flex h-full flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center">
                <p className="text-xs font-semibold text-slate-600">No Document Selected</p>
                <p className="mt-1 text-xs text-slate-400">
                  Upload a PDF document to preview its pages and inspect citations.
                </p>
              </div>
            )}
          </div>
        </section>

        {/* Right: Evidence & Audit Column */}
        <section className="lg:col-span-3 h-full overflow-hidden">
          <EvidencePanel response={response} onCitationClick={onCitationClick} />
        </section>
      </div>
    </main>
  );
}
