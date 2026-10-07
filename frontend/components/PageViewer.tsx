"use client";

import type { BBox } from "@/lib/api";
import { pageImageUrl } from "@/lib/api";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faBullseye, faFileArrowUp } from "@fortawesome/free-solid-svg-icons";

type Props = {
  docId: string;
  page: number;
  highlight?: BBox | null;
};

export function PageViewer({ docId, page, highlight }: Props) {
  const src = pageImageUrl(docId, page);

  if (!docId) {
    return (
      <div className="flex min-h-[480px] w-full flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center shadow-sm">
        <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-slate-50 text-slate-400 border border-slate-200">
          <FontAwesomeIcon icon={faFileArrowUp} className="h-5 w-5" />
        </div>
        <p className="text-xs font-semibold text-slate-700">No Document Selected</p>
        <p className="mt-1 text-xs text-slate-500 max-w-[260px]">
          Upload or select a PDF document from the toolbar to inspect pages and citations.
        </p>
      </div>
    );
  }

  return (
    <div className="relative flex min-h-[520px] w-full items-center justify-center overflow-auto rounded-xl border border-slate-200 bg-slate-100/80 p-4 shadow-inner">
      <div className="relative inline-block overflow-hidden rounded-md bg-white shadow-sheet border border-slate-200">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt={`Page ${page} of document ${docId}`}
          className="mx-auto max-h-[75vh] w-auto object-contain block select-none"
        />

        {highlight && (
          <div
            className="pointer-events-none absolute border-2 border-amber-500 bg-amber-400/25 transition-all duration-300 shadow-sm"
            style={{
              left: `${Math.max(0, highlight.x0 * 100)}%`,
              top: `${Math.max(0, highlight.y0 * 100)}%`,
              width: `${Math.min(100, (highlight.x1 - highlight.x0) * 100)}%`,
              height: `${Math.min(100, (highlight.y1 - highlight.y0) * 100)}%`,
            }}
          >
            <div className="absolute -top-6 left-0 flex items-center gap-1 rounded bg-amber-600 px-1.5 py-0.5 text-[10px] font-semibold text-white shadow-sm whitespace-nowrap">
              <FontAwesomeIcon icon={faBullseye} className="h-2.5 w-2.5" />
              <span>Cited Ground Truth</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
