"use client";

import { FileText, GitFork, Newspaper, MessageCircle, Database } from "lucide-react";
import type { StatsResponse } from "@/lib/types";

interface StatsCardsProps {
  stats?: StatsResponse;
  isLoading?: boolean;
}

const cards = [
  {
    key: "papers" as const,
    label: "Papers",
    icon: FileText,
    color: "text-source-arxiv",
    bgColor: "bg-source-arxiv/10",
  },
  {
    key: "repositories" as const,
    label: "Repositories",
    icon: GitFork,
    color: "text-source-github",
    bgColor: "bg-source-github/10",
  },
  {
    key: "news_articles" as const,
    label: "News Articles",
    icon: Newspaper,
    color: "text-source-news",
    bgColor: "bg-source-news/10",
  },
  {
    key: "reddit_posts" as const,
    label: "Reddit Posts",
    icon: MessageCircle,
    color: "text-source-reddit",
    bgColor: "bg-source-reddit/10",
  },
  {
    key: "total" as const,
    label: "Total Items",
    icon: Database,
    color: "text-accent",
    bgColor: "bg-accent/10",
  },
];

export default function StatsCards({ stats, isLoading }: StatsCardsProps) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
      {cards.map((card) => {
        const Icon = card.icon;
        const value = stats?.[card.key] ?? 0;

        return (
          <div
            key={card.key}
            className="rounded-xl border border-border bg-card p-4 transition-colors hover:bg-card-hover"
          >
            <div className="flex items-center justify-between">
              <p className="text-sm text-text-secondary">{card.label}</p>
              <div className={`rounded-lg p-2 ${card.bgColor}`}>
                <Icon className={`h-4 w-4 ${card.color}`} />
              </div>
            </div>
            <div className="mt-2">
              {isLoading ? (
                <div className="skeleton h-8 w-20" />
              ) : (
                <p className="text-2xl font-bold text-text-primary">
                  {value.toLocaleString()}
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
