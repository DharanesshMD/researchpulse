import type { AskResponse } from "@/lib/types";
import { ExternalLink } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface AnswerCardProps {
  response: AskResponse;
}

export default function AnswerCard({ response }: AnswerCardProps) {
  return (
    <div className="space-y-4">
      {/* Answer */}
      <div className="rounded-xl border border-border bg-card p-5">
        <h3 className="mb-3 text-sm font-medium text-text-muted">Answer</h3>
        <div className="markdown-content prose-sm">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {response.answer}
          </ReactMarkdown>
        </div>
      </div>

      {/* Cited Sources */}
      {response.sources && response.sources.length > 0 && (
        <div className="rounded-xl border border-border bg-card p-5">
          <h3 className="mb-3 text-sm font-medium text-text-muted">
            Sources ({response.sources.length})
          </h3>
          <div className="space-y-2">
            {response.sources.map((src, idx) => (
              <div
                key={idx}
                className="flex items-start gap-3 rounded-lg bg-background p-3"
              >
                <span className="flex-shrink-0 rounded-full bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent">
                  {idx + 1}
                </span>
                <div className="flex-1 min-w-0">
                  <a
                    href={src.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-sm text-text-primary hover:text-accent transition-colors"
                  >
                    <span className="line-clamp-1">{src.title}</span>
                    <ExternalLink className="h-3 w-3 flex-shrink-0" />
                  </a>
                  {src.source && (
                    <span className="ml-2 text-xs text-text-muted">
                      {src.source}
                    </span>
                  )}
                  {src.score !== undefined && (
                    <span className="ml-2 text-xs text-accent">
                      {(src.score * 100).toFixed(0)}% match
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
