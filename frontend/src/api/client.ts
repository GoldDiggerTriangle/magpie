export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, data: unknown) {
    super(formatApiErrorMessage(status, data));
    this.status = status;
    this.data = data;
  }
}

export function formatApiErrorMessage(status: number, data: unknown): string {
  if (typeof data === "string") {
    const trimmed = data.trim();
    if (trimmed.startsWith("<!DOCTYPE") || trimmed.startsWith("<html")) {
      return `API request failed with status ${status}. The server returned an HTML error page.`;
    }
    if (trimmed) {
      return trimmed.length > 300 ? `${trimmed.slice(0, 300)}...` : trimmed;
    }
  }

  if (data && typeof data === "object") {
    const detail = (data as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail.trim();
    }
    const fieldError = firstFieldError(data as Record<string, unknown>);
    if (fieldError) {
      return fieldError;
    }
  }

  return `API request failed with status ${status}`;
}

function firstFieldError(data: Record<string, unknown>): string {
  for (const value of Object.values(data)) {
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
    if (Array.isArray(value)) {
      const first = value.find((entry) => typeof entry === "string" && entry.trim());
      if (typeof first === "string") {
        return first.trim();
      }
    }
  }
  return "";
}

export function getCookie(name: string): string | null {
  const match = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.split("=").slice(1).join("=")) : null;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  multipart?: FormData;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: HeadersInit = {};
  let body: BodyInit | undefined;

  if (options.multipart) {
    body = options.multipart;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  if (!["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase())) {
    const csrf = getCookie("csrftoken");
    if (csrf) {
      headers["X-CSRFToken"] = csrf;
    }
  }

  const response = await fetch(path, {
    method,
    headers,
    body,
    credentials: "include"
  });

  const contentType = response.headers.get("content-type") ?? "";
  const data = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    throw new ApiError(response.status, data);
  }

  return data as T;
}
