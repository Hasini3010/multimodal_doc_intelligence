"use client";

import type { BBox } from "@/lib/api";
import { pageImageUrl } from "@/lib/api";

type Props = {
  docId: string;
  page: number;
  highlight?: BBox | null;
};

export function PageViewer({ docId, page, highlight }: Props) {
  const src = pageImageUrl(docId, page);

  return (
    <div className="relative w-full overflow-auto rounded-lg border border-surface-border bg-black/40">
      <div className="relative inline-block min-w-full">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={src} alt={`Page ${page}`} className="mx-auto max-h-[70vh] w-auto" />
        {highlight && (
          <div
            className="pointer-events-none absolute border-2 border-yellow-400 bg-yellow-400/20"
            style={{
              left: `${highlight.x0 * 100}%`,
              top: `${highlight.y0 * 100}%`,
              width: `${(highlight.x1 - highlight.x0) * 100}%`,
              height: `${(highlight.y1 - highlight.y0) * 100}%`,
            }}
          />
        )}
      </div>
    </div>
  );
}
