export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

// Use relative path so requests go through Next.js rewrite proxy (avoids CORS).
// The rewrite in next.config.mjs forwards /api/* to http://localhost:8000/*
const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";

import { authedFetch } from "./auth";

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      body = await res.text();
    }
    throw new ApiError(`API ${res.status}`, res.status, body);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await authedFetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    cache: "no-store" as RequestInit["cache"],
  });
  return handle<T>(res);
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await authedFetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return handle<T>(res);
}

export async function apiUpload<T>(path: string, formData: FormData): Promise<T> {
  const res = await authedFetch(`${BASE}${path}`, {
    method: "POST",
    body: formData,
  });
  return handle<T>(res);
}

export async function apiDelete<T>(path: string): Promise<T> {
  const res = await authedFetch(`${BASE}${path}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
  });
  return handle<T>(res);
}

export async function apiPostStream(path: string, body?: unknown): Promise<Response> {
  const res = await authedFetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let errBody: unknown = null;
    try { errBody = await res.json(); } catch { errBody = await res.text(); }
    throw new ApiError(`API ${res.status}`, res.status, errBody);
  }
  return res;
}
