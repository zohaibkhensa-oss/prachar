/**
 * Creative Studio API client (P2.14).
 *
 * Wraps the three backend endpoints:
 *   POST /creative-studio/generate           — generate all 10 formats
 *   POST /creative-studio/generate/{format_id} — generate one format
 *   GET  /creative-studio/{package_id}        — retrieve a saved package (stub, 404 for now)
 *
 * Uses the shared `api` fetcher from `./api.ts` (auth headers, base URL, error
 * handling). Mirrors the pattern in `./unified-consult.ts`.
 */
import { apiGet, apiPost } from "./api";

// ─── Request / response types ──────────────────────────────────────────────

export interface CreativeStudioGenerateRequest {
  campaign_id: string;
  creative_direction_id: string;
  domain: string;
}

/** Request body for the regenerate-field endpoint. */
export interface RegenerateFieldRequest extends CreativeStudioGenerateRequest {
  format_id: string;
  field_name: string;
  current_content: Record<string, unknown>;
}

/** Response from the regenerate-field endpoint. */
export interface RegenerateFieldResponse {
  field_name: string;
  new_value: string | string[];
}

/** A single creative format's generated content (shape varies per format). */
export type CreativeFormatData = Record<string, unknown>;

/** The package returned by POST /creative-studio/generate. */
export interface CreativePackage {
  id: string;
  campaign_id: string;
  creative_direction_id: string;
  /** Map of format id → generated content dict (or `{ error: string }` on failure). */
  formats: Record<string, CreativeFormatData>;
  generated_at: string;
  total_tokens: number;
}

// ─── Format catalogue (mirrors the backend CreativeFormatRegistry) ──────────

export interface FormatMeta {
  id: string;
  label: string;
  description: string;
}

/** The 10 creative format ids, in canonical order. */
export const CREATIVE_FORMAT_IDS = [
  "poster",
  "video_script",
  "carousel",
  "story",
  "whatsapp",
  "facebook",
  "linkedin",
  "email",
  "landing_page",
  "sms",
] as const;

export type CreativeFormatId = (typeof CREATIVE_FORMAT_IDS)[number];

export const CREATIVE_FORMATS: FormatMeta[] = [
  { id: "poster", label: "Poster", description: "Single-image poster with headline, body, and CTA." },
  { id: "video_script", label: "Video Script", description: "Scene-by-scene short-form video script." },
  { id: "carousel", label: "Carousel", description: "Multi-slide carousel post with a final CTA slide." },
  { id: "story", label: "Story", description: "Interactive story frames with polls and stickers." },
  { id: "whatsapp", label: "WhatsApp", description: "WhatsApp status text and broadcast message." },
  { id: "facebook", label: "Facebook", description: "Facebook post with copy and image brief." },
  { id: "linkedin", label: "LinkedIn", description: "LinkedIn post with hook, body, and hashtags." },
  { id: "email", label: "Email", description: "Email campaign with 3 subject line variants." },
  { id: "landing_page", label: "Landing Page", description: "Landing page with hero, benefits, FAQ, and CTA." },
  { id: "sms", label: "SMS", description: "Two SMS variants with opt-out language." },
];

export function formatLabel(id: string): string {
  return CREATIVE_FORMATS.find((f) => f.id === id)?.label ?? id;
}

// ─── API client ────────────────────────────────────────────────────────────

export const creativeStudioApi = {
  /** Generate all 10 creative formats for a campaign + creative direction. */
  async generateAllFormats(body: CreativeStudioGenerateRequest): Promise<CreativePackage> {
    return apiPost<CreativePackage>("/creative-studio/generate", body);
  },

  /** Generate a single creative format by id. Returns the format content dict. */
  async generateOneFormat(
    formatId: string,
    body: CreativeStudioGenerateRequest,
  ): Promise<CreativeFormatData> {
    return apiPost<CreativeFormatData>(
      `/creative-studio/generate/${formatId}`,
      body,
    );
  },

  /** Regenerate a single field of an already-generated creative format. */
  async regenerateField(body: RegenerateFieldRequest): Promise<RegenerateFieldResponse> {
    return apiPost<RegenerateFieldResponse>("/creative-studio/regenerate-field", body);
  },

  /** Retrieve a saved creative package by id (stub — backend returns 404 for now). */
  async getPackage(packageId: string): Promise<CreativePackage> {
    return apiGet<CreativePackage>(`/creative-studio/${packageId}`);
  },
};
