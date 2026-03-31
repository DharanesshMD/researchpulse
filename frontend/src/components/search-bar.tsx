"use client";

import { useState } from "react";
import { Search, Filter } from "lucide-react";
import type { Source } from "@/lib/types";
import { sourceLabel } from "@/lib/utils";

interface SearchBarProps {
  onSearch: (query: string) => void;
  onSourceChange: (source: string) => void;
  currentSource: string;
  placeholder?: string;
}

const sources: { value: string; label: string }[] = [
  { value: "all", label: "All Sources" },
  { value: "arxiv", label: "ArXiv" },
  { value: "github", label: "GitHub" },
  { value: "news", label: "News" },
  { value: "reddit", label: "Reddit" },
];

export default function SearchBar({
  onSearch,
  onSourceChange,
  currentSource,
  placeholder = "Search items...",
}: SearchBarProps) {
  const [query, setQuery] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSearch(query);
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-3">
      <div className="relative flex-1">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder}
          className="w-full rounded-lg border border-border bg-card py-2.5 pl-10 pr-4 text-sm text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
        />
      </div>

      <div className="relative">
        <Filter className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
        <select
          value={currentSource}
          onChange={(e) => onSourceChange(e.target.value)}
          className="appearance-none rounded-lg border border-border bg-card py-2.5 pl-10 pr-8 text-sm text-text-primary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
        >
          {sources.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </div>
    </form>
  );
}
