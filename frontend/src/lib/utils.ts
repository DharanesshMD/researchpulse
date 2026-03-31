import type { Source } from "./types";

export function formatDate(dateStr?: string): string {
  if (!dateStr) return "N/A";
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return "N/A";
  }
}

export function formatRelativeTime(dateStr?: string): string {
  if (!dateStr) return "";
  try {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return "just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 30) return `${diffDays}d ago`;
    return formatDate(dateStr);
  } catch {
    return "";
  }
}

export function truncate(text: string, maxLength: number = 200): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength - 3).trimEnd() + "...";
}

export function parseTags(tagsStr?: string): string[] {
  if (!tagsStr) return [];
  return tagsStr
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
}

export function sourceLabel(source: Source): string {
  const labels: Record<Source, string> = {
    arxiv: "ArXiv",
    github: "GitHub",
    news: "News",
    reddit: "Reddit",
  };
  return labels[source] || source;
}

export function sourceColor(source: Source): string {
  const colors: Record<Source, string> = {
    arxiv: "bg-source-arxiv",
    github: "bg-source-github",
    news: "bg-source-news",
    reddit: "bg-source-reddit",
  };
  return colors[source] || "bg-gray-500";
}
