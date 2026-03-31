"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface DigestViewerProps {
  content: string;
  format: string;
  frequency: string;
}

export default function DigestViewer({
  content,
  format,
  frequency,
}: DigestViewerProps) {
  const [viewMode, setViewMode] = useState<"rendered" | "raw">(
    format === "html" ? "rendered" : "rendered",
  );

  return (
    <div className="rounded-xl border border-border bg-card">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-5 py-3">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-text-primary">
            {frequency.charAt(0).toUpperCase() + frequency.slice(1)} Digest
          </span>
          <span className="rounded-full bg-accent/10 px-2 py-0.5 text-xs text-accent">
            {format}
          </span>
        </div>
        <div className="flex rounded-lg border border-border">
          <button
            onClick={() => setViewMode("rendered")}
            className={`px-3 py-1 text-xs transition-colors ${
              viewMode === "rendered"
                ? "bg-accent text-white"
                : "text-text-secondary hover:text-text-primary"
            } rounded-l-lg`}
          >
            Rendered
          </button>
          <button
            onClick={() => setViewMode("raw")}
            className={`px-3 py-1 text-xs transition-colors ${
              viewMode === "raw"
                ? "bg-accent text-white"
                : "text-text-secondary hover:text-text-primary"
            } rounded-r-lg`}
          >
            Raw
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="p-5">
        {viewMode === "raw" ? (
          <pre className="whitespace-pre-wrap rounded-lg bg-background p-4 text-sm text-text-secondary overflow-x-auto">
            {content}
          </pre>
        ) : format === "html" ? (
          <div
            className="markdown-content"
            dangerouslySetInnerHTML={{ __html: content }}
          />
        ) : (
          <div className="markdown-content">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
