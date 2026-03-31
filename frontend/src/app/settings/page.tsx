"use client";

import { useConfig } from "@/lib/hooks";
import {
  Settings as SettingsIcon,
  Globe,
  Brain,
  Bell,
  FileText,
  Database,
} from "lucide-react";

function ConfigSection({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center gap-2 mb-4">
        <Icon className="h-4 w-4 text-accent" />
        <h2 className="text-sm font-semibold text-text-primary">{title}</h2>
      </div>
      {children}
    </div>
  );
}

function ConfigRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-sm text-text-secondary">{label}</span>
      <span className="text-sm text-text-primary font-mono">{value}</span>
    </div>
  );
}

export default function SettingsPage() {
  const { data: config, isLoading } = useConfig();

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <SettingsIcon className="h-6 w-6 text-accent" />
          <h1 className="text-2xl font-bold text-text-primary">Settings</h1>
        </div>
        <div className="space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="skeleton h-40 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <SettingsIcon className="h-6 w-6 text-accent" />
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Settings</h1>
          <p className="text-sm text-text-secondary">
            Read-only view of your current configuration
          </p>
        </div>
      </div>

      {config ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {/* Scraping */}
          <ConfigSection title="Scraping" icon={Globe}>
            <ConfigRow label="Schedule" value={config.scraping.schedule} />
            <ConfigRow
              label="Max items/source"
              value={String(config.scraping.max_items_per_source)}
            />
            <div className="mt-3">
              <span className="text-xs text-text-muted">Sources</span>
              <div className="mt-1 space-y-1">
                {Object.entries(config.scraping.sources).map(
                  ([name, source]) => (
                    <div
                      key={name}
                      className="flex items-center justify-between"
                    >
                      <span className="text-sm text-text-secondary capitalize">
                        {name}
                      </span>
                      <span
                        className={`text-xs ${source.enabled ? "text-green-400" : "text-red-400"}`}
                      >
                        {source.enabled ? "Enabled" : "Disabled"}
                      </span>
                    </div>
                  ),
                )}
              </div>
            </div>
          </ConfigSection>

          {/* LLM */}
          <ConfigSection title="LLM Provider" icon={Brain}>
            <ConfigRow label="Provider" value={config.llm.provider} />
          </ConfigSection>

          {/* Interests */}
          <ConfigSection title="Interests" icon={Database}>
            <ConfigRow
              label="Relevance threshold"
              value={String(config.interests.relevance_threshold)}
            />
            <div className="mt-3">
              <span className="text-xs text-text-muted">Topics</span>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {config.interests.topics.map((topic) => (
                  <span
                    key={topic}
                    className="rounded-md bg-accent/10 px-2 py-0.5 text-xs text-accent"
                  >
                    {topic}
                  </span>
                ))}
              </div>
            </div>
          </ConfigSection>

          {/* Alerts */}
          <ConfigSection title="Alerts" icon={Bell}>
            <ConfigRow
              label="Enabled"
              value={config.alerts.enabled ? "Yes" : "No"}
            />
            <ConfigRow label="Notify via" value={config.alerts.notify_via} />
            <ConfigRow
              label="Min relevance"
              value={String(config.alerts.min_relevance)}
            />
            <div className="mt-3">
              <span className="text-xs text-text-muted">Keywords</span>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {config.alerts.keywords.map((kw) => (
                  <span
                    key={kw}
                    className="rounded-md bg-amber-500/10 px-2 py-0.5 text-xs text-amber-400"
                  >
                    {kw}
                  </span>
                ))}
              </div>
            </div>
          </ConfigSection>

          {/* Digest */}
          <ConfigSection title="Digest Output" icon={FileText}>
            <ConfigRow
              label="Enabled"
              value={config.outputs.digest.enabled ? "Yes" : "No"}
            />
            <ConfigRow
              label="Frequency"
              value={config.outputs.digest.frequency}
            />
            <ConfigRow label="Format" value={config.outputs.digest.format} />
          </ConfigSection>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center rounded-xl border border-border bg-card py-16">
          <SettingsIcon className="h-10 w-10 text-text-muted mb-3" />
          <p className="text-text-secondary">
            Could not load configuration
          </p>
          <p className="mt-1 text-sm text-text-muted">
            Make sure the backend API is running
          </p>
        </div>
      )}
    </div>
  );
}
