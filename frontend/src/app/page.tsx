"use client";

import { useState } from "react";
import { useStats, useItems } from "@/lib/hooks";
import StatsCards from "@/components/stats-cards";
import ItemFeed from "@/components/item-feed";
import { Activity } from "lucide-react";

export default function DashboardPage() {
  const [offset, setOffset] = useState(0);
  const limit = 10;

  const { data: stats, isLoading: statsLoading } = useStats();
  const { data: items, isLoading: itemsLoading } = useItems(
    undefined,
    offset,
    limit,
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Activity className="h-6 w-6 text-accent" />
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Dashboard</h1>
          <p className="text-sm text-text-secondary">
            Research intelligence overview
          </p>
        </div>
      </div>

      {/* Stats */}
      <StatsCards stats={stats} isLoading={statsLoading} />

      {/* Recent Feed */}
      <div>
        <h2 className="mb-4 text-lg font-semibold text-text-primary">
          Recent Items
        </h2>
        <ItemFeed
          items={items?.items ?? []}
          total={items?.total ?? 0}
          offset={offset}
          limit={limit}
          onPageChange={setOffset}
          isLoading={itemsLoading}
        />
      </div>
    </div>
  );
}
