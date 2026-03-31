import type { ResearchItem } from "@/lib/types";
import SourceBadge from "./source-badge";
import { formatRelativeTime, truncate, parseTags } from "@/lib/utils";
import { ExternalLink, Star, GitFork, ArrowUp, MessageCircle } from "lucide-react";

interface ItemCardProps {
  item: ResearchItem;
}

export default function ItemCard({ item }: ItemCardProps) {
  const tags = parseTags(item.tags);

  return (
    <div className="group rounded-xl border border-border bg-card p-4 transition-colors hover:bg-card-hover">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <SourceBadge source={item.source} />
            <span className="text-xs text-text-muted">
              {formatRelativeTime(item.scraped_at || item.published_at)}
            </span>
          </div>

          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-text-primary hover:text-accent transition-colors"
          >
            <h3 className="font-medium text-sm leading-snug line-clamp-2">
              {item.title}
            </h3>
            <ExternalLink className="h-3 w-3 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
          </a>

          <p className="mt-1.5 text-sm text-text-secondary leading-relaxed line-clamp-2">
            {item.summary || truncate(item.content, 180)}
          </p>

          {/* Source-specific metadata */}
          <div className="mt-2 flex items-center gap-3 text-xs text-text-muted">
            {item.source === "github" && (
              <>
                {item.stars !== undefined && (
                  <span className="flex items-center gap-1">
                    <Star className="h-3 w-3" /> {item.stars}
                  </span>
                )}
                {item.forks !== undefined && (
                  <span className="flex items-center gap-1">
                    <GitFork className="h-3 w-3" /> {item.forks}
                  </span>
                )}
                {item.language && <span>{item.language}</span>}
              </>
            )}
            {item.source === "reddit" && (
              <>
                {item.score !== undefined && (
                  <span className="flex items-center gap-1">
                    <ArrowUp className="h-3 w-3" /> {item.score}
                  </span>
                )}
                {item.num_comments !== undefined && (
                  <span className="flex items-center gap-1">
                    <MessageCircle className="h-3 w-3" /> {item.num_comments}
                  </span>
                )}
                {item.subreddit && <span>r/{item.subreddit}</span>}
              </>
            )}
            {item.source === "arxiv" && item.categories && (
              <span>{item.categories}</span>
            )}
            {item.source === "news" && item.feed_name && (
              <span>{item.feed_name}</span>
            )}
          </div>

          {/* Tags */}
          {tags.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {tags.slice(0, 5).map((tag) => (
                <span
                  key={tag}
                  className="rounded-md bg-card-hover px-1.5 py-0.5 text-xs text-text-muted"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>

        {item.relevance_score !== undefined && item.relevance_score !== null && (
          <div className="flex-shrink-0 rounded-lg bg-accent/10 px-2 py-1">
            <span className="text-xs font-medium text-accent">
              {(item.relevance_score * 100).toFixed(0)}%
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
