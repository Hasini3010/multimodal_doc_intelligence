"use client";

import type { AskResponse, Citation } from "@/lib/api";

type Props = {
  response: AskResponse | null;
  onCitationClick: (c: Citation) => void;
};

export function EvidencePanel({ response, onCitationClick }: Props) {
  if (!response) {
    return (
      <div className="rounded-lg border border-surface-border bg-surface-card p-4 text-sm text-slate-400">
        Ask a question to see claims, citations, and math steps here.
      </div>
    );
  }

  const confPct = Math.round(response.confidence * 100);

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-surface-border bg-surface-card p-4">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-300">Evidence</h2>
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
            response.abstained ? "bg-amber-900/50 text-amber-200" : "bg-emerald-900/50 text-emerald-200"
          }`}
        >
          {response.abstained ? "Abstained" : `${confPct}% confidence`}
        </span>
      </div>

      {response.reasoning_summary && (
        <p className="text-sm text-slate-400">{response.reasoning_summary}</p>
      )}

      {response.calculations.length > 0 && (
        <div>
          <h3 className="mb-2 text-xs font-semibold text-slate-500">Calculations</h3>
          <ul className="space-y-2 text-sm">
            {response.calculations.map((c) => (
              <li key={c.name} className="rounded bg-surface/80 p-2 font-mono text-xs">
                <div className="text-slate-300">{c.name}</div>
                <div className="text-slate-500">{c.formula}</div>
                <div className="text-accent">{String(c.result)}</div>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <h3 className="mb-2 text-xs font-semibold text-slate-500">Claims</h3>
        {response.claims.length === 0 ? (
          <p className="text-sm text-slate-500">No verified claims with citations.</p>
        ) : (
          <ul className="space-y-3">
            {response.claims.map((claim, i) => (
              <li key={i} className="rounded border border-surface-border p-2 text-sm">
                <p className="text-slate-200">{claim.text}</p>
                <ul className="mt-2 space-y-1">
                  {claim.citations.map((cit, j) => (
                    <li key={j}>
                      <button
                        type="button"
                        onClick={() => onCitationClick(cit)}
                        className="text-left text-xs text-accent hover:underline"
                      >
                        {cit.doc_name ?? cit.doc_id} · p.{cit.page}
                        {cit.section ? ` · ${cit.section}` : ""}
                        {cit.quote ? ` — “${cit.quote.slice(0, 80)}…”` : ""}
                      </button>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
