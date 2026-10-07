"use client";

import { useState } from "react";

type Message = { role: "user" | "assistant"; text: string };

type Props = {
  onAsk: (question: string) => Promise<void>;
  loading: boolean;
  messages: Message[];
};

const SUGGESTIONS = [
  "Compare production efficiency between Q2 and Q4, identify the three biggest reasons for the change, and show me the proof",
  "What peak efficiency percentage appears on the line chart for Q3?",
  "Which plant has higher average efficiency, Plant A or Plant B?",
];

export function ChatPanel({ onAsk, loading, messages }: Props) {
  const [input, setInput] = useState("");

  const submit = async (q: string) => {
    const text = q.trim();
    if (!text || loading) return;
    setInput("");
    await onAsk(text);
  };

  return (
    <div className="flex h-full flex-col rounded-lg border border-surface-border bg-surface-card">
      <div className="border-b border-surface-border px-4 py-3">
        <h1 className="text-lg font-semibold text-white">Document Q&A</h1>
        <p className="text-xs text-slate-500">Answers include citations you can click to highlight sources.</p>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="space-y-2">
            <p className="text-sm text-slate-500">Try a demo question:</p>
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => submit(s)}
                className="block w-full rounded-lg border border-surface-border bg-surface/60 p-2 text-left text-xs text-slate-300 hover:border-accent"
              >
                {s}
              </button>
            ))}
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`max-w-[95%] rounded-lg px-3 py-2 text-sm ${
              m.role === "user" ? "ml-auto bg-accent/20 text-slate-100" : "bg-surface/80 text-slate-200"
            }`}
          >
            {m.text}
          </div>
        ))}
        {loading && <p className="text-xs text-slate-500">Thinking…</p>}
      </div>

      <form
        className="flex gap-2 border-t border-surface-border p-3"
        onSubmit={(e) => {
          e.preventDefault();
          submit(input);
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about your documents…"
          className="flex-1 rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm text-white outline-none focus:border-accent"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  );
}
