"use client";

import { useState } from "react";
import { useDigest } from "@/lib/hooks";
import DigestViewer from "@/components/digest-viewer";
import { FileText, Loader2 } from "lucide-react";

export default function DigestPage() {
  const [frequency, setFrequency] = useState("daily");
  const [format, setFormat] = useState("markdown");

  const { data, isLoading, isFetching, refetch } = useDigest(frequency, format);

  const handleGenerate = () => {
    refetch();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <FileText className="h-6 w-6 text-accent" />
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Digest</h1>
          <p className="text-sm text-text-secondary">
            Generate research digests from your collected items
          </p>
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-end gap-4 rounded-xl border border-border bg-card p-5">
        <div>
          <label className="block text-xs text-text-muted mb-1.5">
            Frequency
          </label>
          <select
            value={frequency}
            onChange={(e) => setFrequency(e.target.value)}
            className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
          >
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
          </select>
        </div>

        <div>
          <label className="block text-xs text-text-muted mb-1.5">
            Format
          </label>
          <select
            value={format}
            onChange={(e) => setFormat(e.target.value)}
            className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
          >
            <option value="markdown">Markdown</option>
            <option value="html">HTML</option>
          </select>
        </div>

        <button
          onClick={handleGenerate}
          disabled={isFetching}
          className="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
        >
          {isFetching ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Generating...
            </>
          ) : (
            "Generate Digest"
          )}
        </button>
      </div>

      {/* Digest Content */}
      {data ? (
        <DigestViewer
          content={data.content}
          format={data.format}
          frequency={data.frequency}
        />
      ) : (
        <div className="flex flex-col items-center justify-center rounded-xl border border-border bg-card py-16">
          <FileText className="h-10 w-10 text-text-muted mb-3" />
          <p className="text-text-secondary">No digest generated yet</p>
          <p className="mt-1 text-sm text-text-muted">
            Click &quot;Generate Digest&quot; to create a research summary
          </p>
        </div>
      )}
    </div>
  );
}
