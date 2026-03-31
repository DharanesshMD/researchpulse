"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Rss,
  MessageSquare,
  FileText,
  Bell,
  Settings,
  Zap,
} from "lucide-react";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/feed", label: "Feed", icon: Rss },
  { href: "/ask", label: "Ask", icon: MessageSquare },
  { href: "/digest", label: "Digest", icon: FileText },
  { href: "/alerts", label: "Alerts", icon: Bell },
  { href: "/settings", label: "Settings", icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-60 flex-col border-r border-border bg-card">
      {/* Logo */}
      <div className="flex items-center gap-2 px-5 py-5 border-b border-border">
        <Zap className="h-6 w-6 text-accent" />
        <span className="text-lg font-bold text-text-primary">
          ResearchPulse
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href !== "/" && pathname.startsWith(item.href));
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-accent/10 text-accent"
                  : "text-text-secondary hover:bg-card-hover hover:text-text-primary"
              }`}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-border px-5 py-4">
        <p className="text-xs text-text-muted">ResearchPulse v0.1.0</p>
        <p className="text-xs text-text-muted">Open Source AI Research</p>
      </div>
    </aside>
  );
}
