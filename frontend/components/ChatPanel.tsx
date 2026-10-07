"use client";

import { useState } from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faComments,
  faPaperPlane,
  faSpinner,
  faTrashCan,
  faUser,
  faFileLines,
  faCopy,
  faCheck,
  faArrowRight,
  faCircleQuestion,
} from "@fortawesome/free-solid-svg-icons";

type Message = { role: "user" | "assistant"; text: string; id?: string };

type Props = {
  onAsk: (question: string) => Promise<void>;
  loading: boolean;
  messages: Message[];
  onClear?: () => void;
};

const SUGGESTIONS = [
  {
    category: "Cross-Period Analysis",
    prompt:
      "Compare production efficiency between Q2 and Q4, identify the three biggest reasons for the change, and show me the proof",
  },
  {
    category: "Chart Extraction",
    prompt: "What peak efficiency percentage appears on the line chart for Q3?",
  },
  {
    category: "Comparative Audit",
    prompt: "Which plant has higher average efficiency, Plant A or Plant B?",
  },
];

export function ChatPanel({ onAsk, loading, messages, onClear }: Props) {
  const [input, setInput] = useState("");
  const [copiedId, setCopiedId] = useState<number | null>(null);

  const submit = async (q: string) => {
    const text = q.trim();
    if (!text || loading) return;
    setInput("");
    await onAsk(text);
  };

  const handleCopy = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedId(index);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="flex h-full flex-col rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50/75 px-4 py-3.5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50 text-blue-600 border border-blue-100">
            <FontAwesomeIcon icon={faComments} className="h-4 w-4" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-slate-900 leading-tight">Document Inquiry</h1>
            <p className="text-xs text-slate-500 leading-tight">Grounded synthesis with cited proof</p>
          </div>
        </div>

        {messages.length > 0 && onClear && (
          <button
            type="button"
            onClick={onClear}
            title="Clear inquiry history"
            className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-700 transition-colors"
          >
            <FontAwesomeIcon icon={faTrashCan} className="h-3 w-3" />
            <span>Clear</span>
          </button>
        )}
      </div>

      {/* Message Stream */}
      <div className="flex-1 space-y-4 overflow-y-auto p-4 bg-slate-50/30">
        {messages.length === 0 && (
          <div className="space-y-3 py-2">
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-slate-400">
              <FontAwesomeIcon icon={faCircleQuestion} className="h-3.5 w-3.5" />
              <span>Recommended Inquiries</span>
            </div>
            <div className="space-y-2">
              {SUGGESTIONS.map((item, idx) => (
                <button
                  key={idx}
                  type="button"
                  disabled={loading}
                  onClick={() => submit(item.prompt)}
                  className="group flex w-full flex-col items-start rounded-lg border border-slate-200 bg-white p-3 text-left transition-all hover:border-blue-400 hover:shadow-sm"
                >
                  <span className="text-[11px] font-semibold text-blue-600 tracking-wide mb-0.5">
                    {item.category}
                  </span>
                  <div className="flex items-center justify-between w-full">
                    <p className="text-xs text-slate-700 font-medium group-hover:text-slate-900 leading-relaxed">
                      {item.prompt}
                    </p>
                    <FontAwesomeIcon
                      icon={faArrowRight}
                      className="ml-2 h-3 w-3 text-slate-300 transition-transform group-hover:translate-x-0.5 group-hover:text-blue-600 shrink-0"
                    />
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className="flex flex-col gap-1.5">
            {m.role === "user" ? (
              <div className="flex items-start justify-end gap-2.5 pl-8">
                <div className="rounded-2xl rounded-tr-sm bg-blue-600 px-4 py-2.5 text-xs text-white shadow-sm leading-relaxed max-w-[88%]">
                  {m.text}
                </div>
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-200 text-slate-600 text-xs">
                  <FontAwesomeIcon icon={faUser} className="h-3 w-3" />
                </div>
              </div>
            ) : (
              <div className="flex items-start gap-2.5 pr-4">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-100 text-blue-700 text-xs mt-0.5">
                  <FontAwesomeIcon icon={faFileLines} className="h-3.5 w-3.5" />
                </div>
                <div className="flex-1 rounded-xl border border-slate-200 bg-white p-3.5 text-xs text-slate-800 shadow-sm leading-relaxed">
                  <div className="mb-2 flex items-center justify-between border-b border-slate-100 pb-2">
                    <span className="font-semibold text-slate-900 text-xs">Analysis & Answer</span>
                    <button
                      type="button"
                      onClick={() => handleCopy(m.text, i)}
                      className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] text-slate-500 hover:bg-slate-100 hover:text-slate-700 transition-colors"
                      title="Copy response text"
                    >
                      <FontAwesomeIcon
                        icon={copiedId === i ? faCheck : faCopy}
                        className={`h-3 w-3 ${copiedId === i ? "text-emerald-600" : ""}`}
                      />
                      <span>{copiedId === i ? "Copied" : "Copy"}</span>
                    </button>
                  </div>
                  <div className="whitespace-pre-wrap text-slate-700 leading-relaxed font-normal">
                    {m.text}
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-2.5 rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-600 shadow-sm">
            <FontAwesomeIcon icon={faSpinner} className="h-3.5 w-3.5 animate-spin text-blue-600" />
            <span className="font-medium">Synthesizing findings across pages and charts…</span>
          </div>
        )}
      </div>

      {/* Input Form */}
      <form
        className="border-t border-slate-200 bg-white p-3"
        onSubmit={(e) => {
          e.preventDefault();
          submit(input);
        }}
      >
        <div className="flex items-center gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your question about documents and charts…"
            disabled={loading}
            className="flex-1 rounded-lg border border-slate-200 bg-slate-50/50 px-3.5 py-2 text-xs text-slate-900 placeholder:text-slate-400 outline-none transition-all focus:border-blue-500 focus:bg-white focus:ring-2 focus:ring-blue-500/10 disabled:opacity-60"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3.5 py-2 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-blue-700 focus:ring-2 focus:ring-blue-500/20 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {loading ? (
              <FontAwesomeIcon icon={faSpinner} className="h-3 w-3 animate-spin" />
            ) : (
              <FontAwesomeIcon icon={faPaperPlane} className="h-3 w-3" />
            )}
            <span>Send</span>
          </button>
        </div>
      </form>
    </div>
  );
}
