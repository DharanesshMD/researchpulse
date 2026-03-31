import type { AlertMatch } from "@/lib/types";
import { Bell, ExternalLink } from "lucide-react";
import SourceBadge from "./source-badge";
import type { Source } from "@/lib/types";

interface AlertListProps {
  alerts: AlertMatch[];
  isLoading?: boolean;
}

export default function AlertList({ alerts, isLoading }: AlertListProps) {
  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="skeleton h-24 rounded-xl" />
        ))}
      </div>
    );
  }

  if (alerts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-border bg-card py-16">
        <Bell className="h-10 w-10 text-text-muted mb-3" />
        <p className="text-text-secondary">No alert matches</p>
        <p className="mt-1 text-sm text-text-muted">
          Alerts trigger when items match your configured keywords
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {alerts.map((alert, idx) => (
        <div
          key={idx}
          className="rounded-xl border border-border bg-card p-4 transition-colors hover:bg-card-hover"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <SourceBadge source={alert.source as Source} />
              </div>
              <a
                href={alert.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-text-primary hover:text-accent transition-colors"
              >
                <h3 className="font-medium text-sm">{alert.title}</h3>
                <ExternalLink className="h-3 w-3 flex-shrink-0" />
              </a>

              {/* Alert reasons */}
              <div className="mt-2 flex flex-wrap gap-1.5">
                {alert.alert_reasons.map((reason, i) => (
                  <span
                    key={i}
                    className="rounded-md bg-amber-500/10 px-2 py-0.5 text-xs text-amber-400"
                  >
                    {reason}
                  </span>
                ))}
              </div>
            </div>

            {alert.relevance_score !== undefined && (
              <div className="flex-shrink-0 rounded-lg bg-accent/10 px-2 py-1">
                <span className="text-xs font-medium text-accent">
                  {(alert.relevance_score * 100).toFixed(0)}%
                </span>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
