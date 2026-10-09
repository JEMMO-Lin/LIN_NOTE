import type {
  ApiResponse,
  ContentItem,
  KnowledgeBase,
  KnowledgeBaseInput,
  KnowledgeBaseStats,
  LLMConfig,
  KnowledgePoint,
  KnowledgeTree,
  AskResponse,
  MergeHistory,
  MergePreview,
  PaginatedResponse,
  SearchMode,
  SearchResult,
  TokenResponse,
  SimilarContent,
  SummaryTemplate,
  TemplateField,
  User,
} from "@/types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

function getToken() {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("knowflow-token");
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  authenticated = true,
): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();

  if (!(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (authenticated && token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers,
      cache: "no-store",
    });
  } catch {
    throw new ApiError("暂时连接不到服务，请确认后端已启动", 0, "NETWORK_ERROR");
  }

  const body = await response.json().catch(() => null);
  if (!response.ok || (body?.code && body.code !== "OK")) {
    if (response.status === 401 && typeof window !== "undefined") {
      window.localStorage.removeItem("knowflow-token");
    }
    throw new ApiError(
      body?.message || body?.detail?.[0]?.msg || "请求没有成功，请稍后重试",
      response.status,
      body?.code,
    );
  }
  return body as T;
}

export const authApi = {
  login: (payload: { email: string; password: string }) =>
    request<ApiResponse<TokenResponse>>(
      "/auth/login",
      { method: "POST", body: JSON.stringify(payload) },
      false,
    ),

  register: (payload: {
    username: string;
    email: string;
    password: string;
  }) =>
    request<ApiResponse<User>>(
      "/auth/register",
      { method: "POST", body: JSON.stringify(payload) },
      false,
    ),

  me: () => request<ApiResponse<User>>("/auth/me"),

  updateMe: (payload: Partial<Pick<User, "username" | "avatar" | "settings">>) =>
    request<ApiResponse<User>>("/auth/me", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
};

export const knowledgeBaseApi = {
  list: () => request<PaginatedResponse<KnowledgeBase>>("/kb"),

  create: (payload: KnowledgeBaseInput) =>
    request<ApiResponse<KnowledgeBase>>("/kb", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  update: (id: string, payload: Partial<KnowledgeBaseInput>) =>
    request<ApiResponse<KnowledgeBase>>(`/kb/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  remove: (id: string) =>
    request<ApiResponse<null>>(`/kb/${id}`, { method: "DELETE" }),

  stats: (id: string) =>
    request<ApiResponse<KnowledgeBaseStats>>(`/kb/${id}/stats`),

  exportUrl: (id: string, format: "markdown" | "json") =>
    `${API_BASE}/kb/${id}/export?format=${format}`,
};

export const contentApi = {
  list: (
    kbId: string,
    page = 1,
    pageSize = 50,
    filters?: {
      status?: string;
      source_type?: string;
      keyword?: string;
      sort_by?: "newest" | "oldest" | "title";
      include_merged?: boolean;
    },
  ) => {
    const params = new URLSearchParams({
      kb_id: kbId,
      page: String(page),
      page_size: String(pageSize),
    });
    Object.entries(filters || {}).forEach(([key, value]) => {
      if (value !== undefined && value !== "") params.set(key, String(value));
    });
    return (
    request<PaginatedResponse<ContentItem>>(
      `/contents?${params.toString()}`,
    )
    );
  },

  detail: (id: string) =>
    request<ApiResponse<ContentItem>>(`/contents/${id}`),

  importText: (payload: {
    kb_id: string;
    title?: string;
    text: string;
    summary_style?: "brief" | "medium" | "detailed";
    template_id?: string;
  }) =>
    request<ApiResponse<ContentItem>>("/contents/text", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  importUrl: (payload: { kb_id: string; url: string }) =>
    request<ApiResponse<ContentItem>>("/contents/url", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  importImage: (kbId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ApiResponse<ContentItem>>(
      `/contents/image?kb_id=${encodeURIComponent(kbId)}`,
      { method: "POST", body: form },
    );
  },

  process: (
    id: string,
    payload: {
      summary_style?: "brief" | "medium" | "detailed";
      template_id?: string;
    } = {},
  ) =>
    request<ApiResponse<ContentItem>>(`/contents/${id}/process`, {
      method: "POST",
      body: JSON.stringify({
        summary_style: payload.summary_style || "medium",
        template_id: payload.template_id,
      }),
    }),

  cancelProcessing: (id: string) =>
    request<ApiResponse<ContentItem>>(`/contents/${id}/process/cancel`, {
      method: "POST",
    }),

  update: (
    id: string,
    payload: Partial<
      Pick<
        ContentItem,
        "title" | "original_text" | "summary" | "extracted_knowledge" | "metadata"
      >
    >,
  ) =>
    request<ApiResponse<ContentItem>>(`/contents/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  remove: (id: string) =>
    request<ApiResponse<null>>(`/contents/${id}`, { method: "DELETE" }),
};

export const searchApi = {
  search: (payload: {
    query: string;
    kb_id?: string;
    mode?: SearchMode;
    top_k?: number;
  }) =>
    request<ApiResponse<SearchResult[]>>("/search", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

export const llmApi = {
  config: () => request<ApiResponse<LLMConfig>>("/llm/config"),
};

export const templateApi = {
  list: () => request<PaginatedResponse<SummaryTemplate>>("/templates"),
  create: (payload: {
    name: string;
    description?: string;
    fields: TemplateField[];
    default_style: "brief" | "medium" | "detailed";
    is_default?: boolean;
  }) =>
    request<ApiResponse<SummaryTemplate>>("/templates", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  update: (id: string, payload: Partial<SummaryTemplate>) =>
    request<ApiResponse<SummaryTemplate>>(`/templates/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  remove: (id: string) =>
    request<ApiResponse<null>>(`/templates/${id}`, { method: "DELETE" }),
};

export const knowledgeApi = {
  points: (kbId: string, contentId?: string) => {
    const params = new URLSearchParams({ kb_id: kbId });
    if (contentId) params.set("content_id", contentId);
    return request<PaginatedResponse<KnowledgePoint>>(
      `/points?${params.toString()}`,
    );
  },
  updatePoint: (id: string, payload: Partial<KnowledgePoint>) =>
    request<ApiResponse<KnowledgePoint>>(`/points/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  removePoint: (id: string) =>
    request<ApiResponse<null>>(`/points/${id}`, { method: "DELETE" }),
  tree: (kbId: string) =>
    request<ApiResponse<KnowledgeTree>>(`/points/tree/${kbId}`),
  ask: (payload: { question: string; kb_id?: string; top_k?: number }) =>
    request<ApiResponse<AskResponse>>("/points/ask", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

export const mergeApi = {
  similar: (contentId: string, threshold = 0.35) =>
    request<ApiResponse<SimilarContent[]>>(
      `/merge/${contentId}/similar?threshold=${threshold}`,
    ),
  preview: (targetId: string, sourceIds: string[]) =>
    request<ApiResponse<MergePreview>>("/merge/preview", {
      method: "POST",
      body: JSON.stringify({ target_id: targetId, source_ids: sourceIds }),
    }),
  merge: (targetId: string, sourceIds: string[]) =>
    request<ApiResponse<ContentItem>>("/merge", {
      method: "POST",
      body: JSON.stringify({ target_id: targetId, source_ids: sourceIds }),
    }),
  history: (kbId?: string) =>
    request<PaginatedResponse<MergeHistory>>(
      `/merge/history/list${kbId ? `?kb_id=${encodeURIComponent(kbId)}` : ""}`,
    ),
};

export async function downloadAuthenticatedFile(
  url: string,
  fallbackName: string,
) {
  const token = getToken();
  const response = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) throw new ApiError("导出失败", response.status);
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = fallbackName;
  anchor.click();
  URL.revokeObjectURL(objectUrl);
}
