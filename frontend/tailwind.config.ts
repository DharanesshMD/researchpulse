import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        background: "#0a0a0f",
        card: "#12121a",
        "card-hover": "#1a1a28",
        border: "#1e1e2e",
        accent: "#6366f1",
        "accent-hover": "#818cf8",
        "text-primary": "#e2e8f0",
        "text-secondary": "#94a3b8",
        "text-muted": "#64748b",
        "source-arxiv": "#3b82f6",
        "source-github": "#a855f7",
        "source-news": "#f59e0b",
        "source-reddit": "#f97316",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
