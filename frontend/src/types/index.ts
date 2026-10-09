export type ApiResponse<T> = {
  code: string;
  message: string;
  data: T;
};

export type PaginatedResponse<T> = ApiResponse<T[]> & {
  total: number;
  page: number;
  page_size: number;
};

export type User = {
  id: string;
  username: string;
  email: string;
  avatar?: string | null;
  settings: Record<string, unknown>;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
};

export type KnowledgeBase = {
  id: string;
  user_id: string;
  name: string;
  description?: string | null;
  category?: string | null;
  tags: string[];
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type KnowledgeBaseInput = {
  name: string;
  description?: string;
  category?: string;
  tags?: string[];
};

export type KnowledgeBaseStats = {
  kb_id: string;
  content_count: number;
  knowledge_point_count: number;
  last_updated?: string | null;
};

export type ContentItem = {
  id: string;
  kb_id: string;
  source_type: "text" | "url" | "image" | string;
  source_url?: string | null;
  title: string;
  original_text: string;
  distilled_text?: string | null;
  summary?: string | null;
  status: "pending" | "finalizing" | "processed" | "failed" | "cancelled" | string;
  extracted_knowledge?: Record<string, unknown> | null;
  metadata: Record<string, unknown>;
  merge_status: "active" | "merged" | "archived" | string;
  merged_into_id?: string | null;
  created_at: string;
  updated_at: string;
};

export type SearchMode = "hybrid" | "vector" | "keyword";

export type SearchResult = {
  point_id: string;
  title: string;
  content: string;
  score: number;
  content_id?: string | null;
  kb_id?: string | null;
};

export type ProviderInfo = {
  provider: string;
  display_name: string;
  available: boolean;
  models: Record<string, string>;
};

export type LLMConfig = {
  default_provider: string;
  current_provider: string;
  available_providers: ProviderInfo[];
  model_fast: string;
  model_balanced: string;
  model_quality: string;
  embedding_model: string;
};

export type KnowledgePoint = {
  id: string;
  content_id: string;
  kb_id: string;
  title: string;
  content: string;
  importance: number;
  category?: string | null;
  related_points: string[];
  created_at: string;
  updated_at: string;
};

export type TemplateField = {
  name: string;
  label: string;
  required: boolean;
  max_length?: number | null;
};

export type SummaryTemplate = {
  id: string;
  user_id: string;
  name: string;
  description?: string | null;
  fields: TemplateField[];
  default_style: "brief" | "medium" | "detailed";
  is_default: boolean;
  created_at: string;
  updated_at: string;
};

export type SimilarContent = {
  id: string;
  title: string;
  summary?: string | null;
  source_type: string;
  similarity: number;
  created_at: string;
};

export type MergePreview = {
  target_id: string;
  source_ids: string[];
  merged_title: string;
  merged_summary: string;
  merged_text: string;
  conflicts: Array<Record<string, unknown>>;
};

export type MergeHistory = {
  id: string;
  user_id: string;
  kb_id: string;
  target_id: string;
  source_ids: string[];
  source_titles: string[];
  merged_result_id: string;
  strategy: string;
  summary?: string | null;
  conflicts: Array<Record<string, unknown>>;
  created_at: string;
  updated_at: string;
};

export type KnowledgeTree = {
  nodes: Array<{
    id: string;
    label: string;
    category?: string | null;
    importance: number;
    content_id?: string | null;
  }>;
  edges: Array<{
    source: string;
    target: string;
    relation: string;
  }>;
};

export type AskResponse = {
  answer: string;
  sources: SearchResult[];
  answer_source: "rag" | "wiki";
  wiki_hit: boolean;
  ask_count: number;
  wiki_entry_id?: string | null;
  wiki_created: boolean;
};
