"use client";

import { useAsk } from "@/lib/hooks";
import AskForm from "@/components/ask-form";
import AnswerCard from "@/components/answer-card";
import { MessageSquare } from "lucide-react";

export default function AskPage() {
  const { mutate, data, isPending, error, reset } = useAsk();

  const handleSubmit = (
    question: string,
    sourceFilter?: string,
    topK?: number,
  ) => {
    mutate({ question, source_filter: sourceFilter, top_k: topK });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <MessageSquare className="h-6 w-6 text-accent" />
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Ask</h1>
          <p className="text-sm text-text-secondary">
            Query your research knowledge base with RAG
          </p>
        </div>
      </div>

      {/* Ask Form */}
      <AskForm onSubmit={handleSubmit} isLoading={isPending} />

      {/* Error */}
      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4">
          <p className="text-sm text-red-400">
            {error.message || "Query failed. Please try again."}
          </p>
        </div>
      )}

      {/* Response */}
      {data && <AnswerCard response={data} />}

      {/* Placeholder */}
      {!data && !isPending && !error && (
        <div className="flex flex-col items-center justify-center rounded-xl border border-border bg-card py-16">
          <MessageSquare className="h-10 w-10 text-text-muted mb-3" />
          <p className="text-text-secondary">Ask a question to get started</p>
          <p className="mt-1 text-sm text-text-muted">
            Uses RAG to search your indexed research and generate an answer
          </p>
        </div>
      )}
    </div>
  );
}
