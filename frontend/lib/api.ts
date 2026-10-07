const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type BBox = { x0: number; y0: number; x1: number; y1: number };

export type Citation = {
  doc_id: string;
  doc_name?: string;
  page: number;
  section?: string;
  element_id?: string;
  bbox?: BBox;
  quote?: string;
};

export type CalculationResult = {
  name: string;
  formula: string;
  inputs: Record<string, unknown>;
  result: number | string;
};

export type Claim = { text: string; citations: Citation[] };

export type AskResponse = {
  answer: string;
  reasoning_summary?: string;
  claims: Claim[];
  calculations: CalculationResult[];
  confidence: number;
  abstained: boolean;
};

export type DocumentSummary = {
  doc_id: string;
  doc_name: string;
  page_count: number;
  sha256?: string;
};

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export function pageImageUrl(docId: string, page: number) {
  return `${API_BASE}/page/${docId}/${page}`;
}

export function documentPdfUrl(docId: string) {
  return `${API_BASE}/documents/${docId}/pdf`;
}

export async function getHealth() {
  return fetchJson<{ status: string; gemini_configured: boolean }>("/health");
}

export async function listDocuments() {
  return fetchJson<DocumentSummary[]>("/documents");
}

export async function askQuestion(question: string, docIds?: string[]) {
  return fetchJson<AskResponse>("/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, doc_ids: docIds ?? null }),
  });
}

export async function uploadPdf(file: File) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/ingest`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
