"use client";

import type { AskResponse, Citation } from "@/lib/api";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faShieldHalved,
  faCircleCheck,
  faTriangleExclamation,
  faCircleInfo,
  faCalculator,
  faQuoteLeft,
  faLocationDot,
  faFileLines,
  faClipboardList,
  faArrowRight,
} from "@fortawesome/free-solid-svg-icons";

type Props = {
  response: AskResponse | null;
  onCitationClick: (c: Citation) => void;
};

export function EvidencePanel({ response, onCitationClick }: Props) {
  if (!response) {
    return (
      <div className="flex h-full flex-col rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-2.5 border-b border-slate-200 pb-3.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-slate-600">
            <FontAwesomeIcon icon={faShieldHalved} className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-slate-900 leading-tight">Evidence & Audit</h2>
            <p className="text-xs text-slate-500 leading-tight">Grounded verification log</p>
          </div>
        </div>

        <div className="flex flex-1 flex-col items-center justify-center px-4 text-center py-12">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-slate-50 text-slate-400 border border-slate-200">
            <FontAwesomeIcon icon={faClipboardList} className="h-5 w-5" />
          </div>
          <h3 className="text-xs font-semibold text-slate-700">No active audit data</h3>
          <p className="mt-1 text-xs text-slate-500 max-w-[240px] leading-relaxed">
            Submit a query to inspect cited page sources, extracted quotes, and mathematical formulas.
          </p>
        </div>
      </div>
    );
  }

  const confPct = Math.round(response.confidence * 100);

  return (
    <div className="flex h-full flex-col gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 pb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-blue-50 text-blue-600 border border-blue-100">
            <FontAwesomeIcon icon={faShieldHalved} className="h-3.5 w-3.5" />
          </div>
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-700">
              Evidence & Audit
            </h2>
            <span className="text-[11px] text-slate-400">Verifiable grounding data</span>
          </div>
        </div>

        <span
          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium border ${
            response.abstained
              ? "bg-amber-50 text-amber-800 border-amber-200"
              : "bg-emerald-50 text-emerald-800 border-emerald-200"
          }`}
        >
          <FontAwesomeIcon
            icon={response.abstained ? faTriangleExclamation : faCircleCheck}
            className={`h-3 w-3 ${response.abstained ? "text-amber-600" : "text-emerald-600"}`}
          />
          {response.abstained ? "Abstained" : `${confPct}% Confidence`}
        </span>
      </div>

      {/* Analytical Reasoning Summary */}
      {response.reasoning_summary && (
        <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-3">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-700 mb-1.5">
            <FontAwesomeIcon icon={faCircleInfo} className="h-3.5 w-3.5 text-blue-600" />
            <span>Analytical Reasoning</span>
          </div>
          <p className="text-xs text-slate-600 leading-relaxed">{response.reasoning_summary}</p>
        </div>
      )}

      {/* Calculations */}
      {response.calculations.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
            <FontAwesomeIcon icon={faCalculator} className="h-3 w-3 text-slate-500" />
            <span>Formula Derivations ({response.calculations.length})</span>
          </div>
          <ul className="space-y-2">
            {response.calculations.map((c, idx) => (
              <li
                key={idx}
                className="rounded-lg border border-slate-200 bg-white p-2.5 shadow-subtle text-xs"
              >
                <div className="font-semibold text-slate-800 text-xs flex items-center justify-between">
                  <span>{c.name}</span>
                  <span className="rounded bg-blue-50 px-2 py-0.5 font-mono text-[11px] font-semibold text-blue-700 border border-blue-100">
                    = {String(c.result)}
                  </span>
                </div>
                <div className="mt-1 font-mono text-[11px] text-slate-500 bg-slate-50 p-1.5 rounded border border-slate-100">
                  {c.formula}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Grounded Claims & Citations */}
      <div>
        <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
          <FontAwesomeIcon icon={faQuoteLeft} className="h-3 w-3 text-slate-500" />
          <span>Claims & Sources ({response.claims.length})</span>
        </div>

        {response.claims.length === 0 ? (
          <p className="rounded-lg border border-dashed border-slate-200 p-3 text-center text-xs text-slate-400">
            No specific claims extracted for this response.
          </p>
        ) : (
          <div className="space-y-3">
            {response.claims.map((claim, i) => (
              <div
                key={i}
                className="rounded-lg border border-slate-200 bg-white p-3 shadow-subtle"
              >
                <div className="flex items-start gap-2">
                  <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-slate-100 text-[10px] font-semibold text-slate-600 mt-0.5">
                    {i + 1}
                  </span>
                  <p className="text-xs font-medium text-slate-800 leading-relaxed">{claim.text}</p>
                </div>

                {claim.citations.length > 0 && (
                  <div className="mt-2.5 pl-6 space-y-1.5">
                    {claim.citations.map((cit, j) => (
                      <button
                        key={j}
                        type="button"
                        onClick={() => onCitationClick(cit)}
                        className="group flex w-full flex-col rounded-md border border-slate-200 bg-slate-50/70 p-2 text-left transition-all hover:border-blue-400 hover:bg-blue-50/40"
                      >
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="font-semibold text-blue-700 flex items-center gap-1">
                            <FontAwesomeIcon icon={faLocationDot} className="h-2.5 w-2.5" />
                            {cit.doc_name ?? cit.doc_id} · Page {cit.page}
                          </span>
                          <span className="text-[10px] text-slate-400 group-hover:text-blue-600 flex items-center gap-0.5">
                            Inspect
                            <FontAwesomeIcon icon={faArrowRight} className="h-2 w-2" />
                          </span>
                        </div>

                        {cit.section && (
                          <span className="mt-0.5 text-[10px] text-slate-500 font-medium">
                            Section: {cit.section}
                          </span>
                        )}

                        {cit.quote && (
                          <div className="mt-1 text-[11px] italic text-slate-600 border-l-2 border-blue-300 pl-2 line-clamp-2">
                            “{cit.quote}”
                          </div>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
