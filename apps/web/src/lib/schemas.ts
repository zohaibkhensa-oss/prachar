import { z } from "zod";

export const BrandGraphSchema = z.object({
  entities: z.array(z.string()),
  categories: z.array(z.string()),
  usps: z.array(z.string()),
  competitors: z.array(z.string()),
  locales: z.array(z.string()),
  tone: z.string().default(""),
});
export type BrandGraph = z.infer<typeof BrandGraphSchema>;

export const AudienceSpecSchema = z.object({
  geo: z.array(z.string()),
  age: z.tuple([z.number(), z.number()]).default([18, 34]),
  gender: z.enum(["all", "male", "female"]).default("all"),
  interests: z.array(z.string()),
  intents: z.array(z.string()),
  languages: z.array(z.string()),
  lookalike_seed: z.string().default(""),
});
export type AudienceSpec = z.infer<typeof AudienceSpecSchema>;

export const CreativeAssetSchema = z.object({
  id: z.string(),
  type: z.enum(["copy", "image", "video", "thumbnail"]),
  locale: z.string(),
  channel: z.string(),
  variant_group: z.string(),
  policy_status: z.enum(["pending", "approved", "rejected"]).default("pending"),
  copy: z.string().default(""),
  image_url: z.string().default(""),
  ctr: z.number().optional(),
  is_winner: z.boolean().default(false),
});
export type CreativeAsset = z.infer<typeof CreativeAssetSchema>;

export const MetricEventSchema = z.object({
  channel: z.string(),
  entity_type: z.string(),
  entity_id: z.string(),
  metric: z.string(),
  value: z.number(),
  ts: z.string(),
});
export type MetricEvent = z.infer<typeof MetricEventSchema>;

export const VisibilityScoreSchema = z.object({
  brand_id: z.string(),
  overall: z.number(),
  organic_rank_index: z.number(),
  ai_citation_rate: z.number(),
  social_reach_index: z.number(),
  paid_efficiency: z.number(),
  momentum: z.number(),
  week: z.string(),
  breakdown: z
    .record(z.string(), z.number())
    .default({}),
});
export type VisibilityScore = z.infer<typeof VisibilityScoreSchema>;

export const FindingSchema = z.object({
  title: z.string(),
  impact: z.enum(["high", "medium", "low"]).default("medium"),
  effort: z.enum(["high", "medium", "low"]).default("medium"),
  category: z.string(),
  fix_description: z.string(),
  gated: z.boolean().default(false),
});
export type Finding = z.infer<typeof FindingSchema>;

export const AuditFindingsSchema = z.object({
  brand_id: z.string(),
  score: VisibilityScoreSchema,
  findings: z.array(FindingSchema),
});
export type AuditFindings = z.infer<typeof AuditFindingsSchema>;

export const BrandSchema = z.object({
  id: z.string(),
  tenant_id: z.string(),
  name: z.string(),
  handle: z.string().default(""),
  url: z.string().default(""),
  graph: BrandGraphSchema.nullable().default(null),
  created_at: z.string(),
});
export type Brand = z.infer<typeof BrandSchema>;

export const ConnectionSchema = z.object({
  id: z.string(),
  brand_id: z.string(),
  channel: z.string(),
  region: z.string().default(""),
  status: z.enum(["connected", "disconnected", "error"]).default("disconnected"),
  last_publish: z.string().nullable().default(null),
  next_action: z.string().default(""),
});
export type Connection = z.infer<typeof ConnectionSchema>;

export const CampaignSchema = z.object({
  id: z.string(),
  brand_id: z.string(),
  name: z.string(),
  network: z.string(),
  status: z.enum(["active", "paused", "draft"]).default("draft"),
  budget: z.number().default(0),
  spend: z.number().default(0),
  cpa: z.number().default(0),
  roas: z.number().default(0),
  audience: AudienceSpecSchema.nullable().default(null),
  created_at: z.string(),
});
export type Campaign = z.infer<typeof CampaignSchema>;

export const UserSchema = z.object({
  id: z.string(),
  tenant_id: z.string(),
  email: z.string(),
  name: z.string().default(""),
  role: z.string().default("owner"),
});
export type User = z.infer<typeof UserSchema>;

export const TenantSchema = z.object({
  id: z.string(),
  name: z.string(),
  plan: z.enum(["starter", "growth", "agency"]).default("starter"),
  max_cpa: z.number().default(0),
  locales: z.array(z.string()).default([]),
});
export type Tenant = z.infer<typeof TenantSchema>;

export const AuditJobSchema = z.object({
  id: z.string(),
  brand_id: z.string(),
  status: z.enum(["queued", "running", "done", "failed"]).default("queued"),
  stage: z.string().default(""),
  progress: z.number().default(0),
  logs: z.array(z.string()).default([]),
  result: AuditFindingsSchema.nullable().default(null),
  created_at: z.string(),
});
export type AuditJob = z.infer<typeof AuditJobSchema>;
