"use client";

import type { ResearchItem } from "@/lib/types";
import ItemCard from "./item-card";
import { ChevronLeft, ChevronRight } from "lucide-react";

interface ItemFeedProps {
  items: ResearchItem[];
  total: number;
  offset: number;
  limit: number;
  onPageChange: (newOffset: number) => void;
  isLoading?: boolean;
}

export default function ItemFeed({
  items,
  total,
  offset,
  limit,
  onPageChange,
  isLoading,
}: ItemFeedProps) {
  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.ceil(total / limit);

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="skeleton h-32 rounded-xl" />
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-border bg-card py-16">
        <p className="text-text-secondary">No items found</p>
        <p className="mt-1 text-sm text-text-muted">
          Try adjusting your filters or run a scrape first
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {items.map((item) => (
        <ItemCard key={`${item.source}-${item.id}`} item={item} />
      ))}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-border pt-4">
          <p className="text-sm text-text-muted">
            Showing {offset + 1}–{Math.min(offset + limit, total)} of {total}
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onPageChange(Math.max(0, offset - limit))}
              disabled={offset === 0}
              className="flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-card-hover disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </button>
            <span className="text-sm text-text-muted">
              {currentPage} / {totalPages}
            </span>
            <button
              onClick={() => onPageChange(offset + limit)}
              disabled={offset + limit >= total}
              className="flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-card-hover disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
