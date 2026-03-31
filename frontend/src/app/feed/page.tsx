"use client";

import { useState } from "react";
import { useItems } from "@/lib/hooks";
import ItemFeed from "@/components/item-feed";
import SearchBar from "@/components/search-bar";
import { Rss } from "lucide-react";
import type { Source } from "@/lib/types";

const sourceTabs: { value: string; label: string }[] = [
  { value: "all", label: "All" },
  { value: "arxiv", label: "ArXiv" },
  { value: "github", label: "GitHub" },
  { value: "news", label: "News" },
  { value: "reddit", label: "Reddit" },
];

export default function FeedPage() {
  const [source, setSource] = useState("all");
  const [offset, setOffset] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const limit = 20;

  const { data, isLoading } = useItems(
    source === "all" ? undefined : source,
    offset,
    limit,
  );

  const handleSourceChange = (newSource: string) => {
    setSource(newSource);
    setOffset(0);
  };

  const handleSearch = (query: string) => {
    setSearchQuery(query);
    setOffset(0);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Rss className="h-6 w-6 text-accent" />
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Feed</h1>
          <p className="text-sm text-text-secondary">
            Browse all scraped research items
          </p>
        </div>
      </div>

      {/* Source Tabs */}
      <div className="flex gap-1 rounded-lg border border-border bg-card p-1">
        {sourceTabs.map((tab) => (
          <button
            key={tab.value}
            onClick={() => handleSourceChange(tab.value)}
            className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              source === tab.value
                ? "bg-accent text-white"
                : "text-text-secondary hover:text-text-primary hover:bg-card-hover"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Search */}
      <SearchBar
        onSearch={handleSearch}
        onSourceChange={handleSourceChange}
        currentSource={source}
        placeholder="Search research items..."
      />

      {/* Feed */}
      <ItemFeed
        items={data?.items ?? []}
        total={data?.total ?? 0}
        offset={offset}
        limit={limit}
        onPageChange={setOffset}
        isLoading={isLoading}
      />
    </div>
  );
}
