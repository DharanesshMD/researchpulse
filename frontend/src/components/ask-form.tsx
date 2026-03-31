"use client";

import { useState } from "react";
import { Send, Loader2 } from "lucide-react";

interface AskFormProps {
  onSubmit: (question: string, sourceFilter?: string, topK?: number) => void;
  isLoading?: boolean;
}

const sources = [
  { value: "", label: "All sources" },
  { value: "arxiv", label: "ArXiv" },
  { value: "github", label: "GitHub" },
  { value: "news", label: "News" },
  { value: "reddit", label: "Reddit" },
];

export default function AskForm({ onSubmit, isLoading }: AskFormProps) {
  const [question, setQuestion] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [topK, setTopK] = useState(10);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;
    onSubmit(question, sourceFilter || undefined, topK);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="relative">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question about your research..."
          rows={3}
          className="w-full rounded-xl border border-border bg-card p-4 pr-12 text-sm text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent resize-none"
        />
        <button
          type="submit"
          disabled={!question.trim() || isLoading}
          className="absolute bottom-3 right-3 rounded-lg bg-accent p-2 text-white transition-colors hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
        </button>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <label className="text-xs text-text-muted">Source:</label>
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="rounded-lg border border-border bg-card px-3 py-1.5 text-xs text-text-primary focus:border-accent focus:outline-none"
          >
            {sources.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs text-text-muted">Sources to retrieve:</label>
          <input
            type="number"
            min={1}
            max={50}
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            className="w-16 rounded-lg border border-border bg-card px-2 py-1.5 text-xs text-text-primary focus:border-accent focus:outline-none"
          />
        </div>
      </div>
    </form>
  );
}
