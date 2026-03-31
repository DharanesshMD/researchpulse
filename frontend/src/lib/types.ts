// TypeScript interfaces mirroring FastAPI response models

export type Source = "arxiv" | "github" | "news" | "reddit";

export interface ResearchItem {
  id: number;
  title: string;
  url: string;
  source: Source;
  content: string;
  summary?: string;
  tags?: string;
  relevance_score?: number;
  published_at?: string;
  scraped_at?: string;
  // ArXiv-specific
  arxiv_id?: string;
  authors?: string;
  categories?: string;
  pdf_url?: string;
  // GitHub-specific
  full_name?: string;
  description?: string;
  language?: string;
  stars?: number;
  forks?: number;
  topics?: string;
  // Reddit-specific
  reddit_id?: string;
  subreddit?: string;
  score?: number;
  num_comments?: number;
  selftext?: string;
  post_type?: string;
  // News-specific
  feed_name?: string;
  author?: string;
}

export interface PaginatedResponse {
  items: ResearchItem[];
  total: number;
  offset: number;
  limit: number;
}

export interface StatsResponse {
  papers: number;
  repositories: number;
  news_articles: number;
  reddit_posts: number;
  total: number;
}

export interface AskRequest {
  question: string;
  source_filter?: string;
  top_k?: number;
}

export interface SourceReference {
  title: string;
  url: string;
  source: string;
  score?: number;
  summary?: string;
  content_preview?: string;
}

export interface AskResponse {
  answer: string;
  sources: SourceReference[];
  question: string;
}

export interface DigestResponse {
  content: string;
  format: string;
  frequency: string;
}

export interface AlertMatch {
  title: string;
  url: string;
  source: string;
  content?: string;
  alert_reasons: string[];
  relevance_score?: number;
}

export interface AlertsCheckResponse {
  matches: number;
  items: AlertMatch[];
}

export interface ConfigResponse {
  scraping: {
    schedule: string;
    max_items_per_source: number;
    sources: Record<string, { enabled: boolean }>;
  };
  interests: {
    topics: string[];
    relevance_threshold: number;
  };
  llm: {
    provider: string;
  };
  alerts: {
    enabled: boolean;
    keywords: string[];
    notify_via: string;
    min_relevance: number;
  };
  outputs: {
    digest: {
      enabled: boolean;
      frequency: string;
      format: string;
    };
  };
}
