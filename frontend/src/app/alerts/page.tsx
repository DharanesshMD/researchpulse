"use client";

import { useAlerts } from "@/lib/hooks";
import AlertList from "@/components/alert-list";
import { Bell } from "lucide-react";

export default function AlertsPage() {
  const { data, isLoading } = useAlerts();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Bell className="h-6 w-6 text-accent" />
          <div>
            <h1 className="text-2xl font-bold text-text-primary">Alerts</h1>
            <p className="text-sm text-text-secondary">
              Items matching your alert keywords and relevance thresholds
            </p>
          </div>
        </div>

        {data && (
          <span className="rounded-full bg-accent/10 px-3 py-1 text-sm text-accent">
            {data.matches} match{data.matches !== 1 ? "es" : ""}
          </span>
        )}
      </div>

      {/* Alert Matches */}
      <AlertList alerts={data?.items ?? []} isLoading={isLoading} />
    </div>
  );
}
