import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/sidebar";
import QueryProvider from "@/providers/query-provider";

export const metadata: Metadata = {
  title: "ResearchPulse Dashboard",
  description: "Open Source AI Research Intelligence Platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-background text-text-primary antialiased">
        <QueryProvider>
          <div className="flex min-h-screen">
            <Sidebar />
            <main className="ml-60 flex-1 p-6">{children}</main>
          </div>
        </QueryProvider>
      </body>
    </html>
  );
}
