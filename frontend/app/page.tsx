"use client";

import { ChatPanel } from "@/components/ChatPanel";
import { EvidencePanel } from "@/components/EvidencePanel";
import { PageViewer } from "@/components/PageViewer";
import {
  askQuestion,
  listDocuments,
  uploadPdf,
  type AskResponse,
  type Citation,
  type DocumentSummary,
} from "@/lib/api";
import { useCallback, useEffect, useState } from "react";

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

  const refreshDocs = useCallback(async () => {
    try {
      const list = await listDocuments();
      setDocs(list);
      if (list.length && !selectedDocId) setSelectedDocId(list[0].doc_id);
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
      setMessages((m) => [...m, { role: "assistant", text: `Error: ${msg}` }]);
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
    setUploading(true);
    try {
      await uploadPdf(file);
      await refreshDocs();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const selected = docs.find((d) => d.doc_id === selectedDocId);

  return (
    <main className="flex min-h-screen flex-col">
      <header className="flex items-center justify-between border-b border-surface-border px-4 py-3">
        <span className="font-semibold text-white">HNX26PSI01 · Multimodal Doc AI</span>
        <div className="flex items-center gap-3 text-xs text-slate-500">
          {!apiOk && <span className="text-amber-400">API offline — start backend on :8000</span>}
          <label className="cursor-pointer rounded border border-surface-border px-2 py-1 hover:border-accent">
            {uploading ? "Uploading…" : "Upload PDF"}
            <input
              type="file"
              accept="application/pdf"
              className="hidden"
              disabled={uploading}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onUpload(f);
              }}
            />
          </label>
        </div>
      </header>

      <div className="grid flex-1 grid-cols-1 gap-3 p-3 lg:grid-cols-12 lg:gap-4 lg:p-4">
        <section className="lg:col-span-4 lg:min-h-[calc(100vh-4rem)]">
          <ChatPanel onAsk={onAsk} loading={loading} messages={messages} />
        </section>

        <section className="flex flex-col gap-3 lg:col-span-5">
          <div className="flex flex-wrap items-center gap-2">
            <label className="text-xs text-slate-500">Document</label>
            <select
              value={selectedDocId ?? ""}
              onChange={(e) => {
                setSelectedDocId(e.target.value);
                setPage(1);
                setHighlight(null);
              }}
              className="rounded border border-surface-border bg-surface-card px-2 py-1 text-sm"
            >
              {docs.map((d) => (
                <option key={d.doc_id} value={d.doc_id}>
                  {d.doc_name}
                </option>
              ))}
            </select>
            <label className="text-xs text-slate-500">Page</label>
            <input
              type="number"
              min={1}
              max={selected?.page_count ?? 1}
              value={page}
              onChange={(e) => setPage(Number(e.target.value) || 1)}
              className="w-16 rounded border border-surface-border bg-surface-card px-2 py-1 text-sm"
            />
          </div>
          {selectedDocId ? (
            <PageViewer docId={selectedDocId} page={page} highlight={highlight} />
          ) : (
            <p className="text-sm text-slate-500">Ingest documents to preview pages.</p>
          )}
        </section>

        <section className="lg:col-span-3">
          <EvidencePanel response={response} onCitationClick={onCitationClick} />
        </section>
      </div>
    </main>
  );
}
