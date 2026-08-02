/** Types for the Creator Intelligence (/creator) API. */

export interface CreatorProfile {
  niche: string;
  platforms: string[];
  upload_frequency: string;
  content_pillars: string[];
  audience: string;
  audience_size: string;
  growth_stage: string;
  monetisation: string;
  brand_partnerships: string[];
  competitors: string[];
}

export interface CreatorPosition {
  strengths: string[];
  weaknesses: string[];
  growth_opportunities: string[];
  content_gaps: string[];
  monetisation_opportunities: string[];
}

export interface CreatorWeekPlan {
  week: number;
  theme: string;
  videos: string[];
  shorts: string[];
  community_posts: string[];
  collaborations: string[];
  seo: string[];
  newsletter: string;
  live_sessions: string;
  kpis: string[];
}

export interface CreatorConsultResponse {
  reply: string;
  profile: CreatorProfile;
  position: CreatorPosition;
  plan: CreatorWeekPlan[];
  brand_id: string;
  brand_name: string;
  confidence: number;
  tokens_used: number;
  model: string;
}

export interface RepurposedAsset {
  asset_type: string;
  content: string;
  notes: string;
}

export interface RepurposeResponse {
  reply: string;
  assets: RepurposedAsset[];
  tokens_used: number;
  model: string;
}

export interface YouTubePlan {
  title_options: string[];
  thumbnail_concepts: string[];
  opening_hook: string;
  retention_improvements: string[];
  description: string;
  seo_keywords: string[];
  tags: string[];
  chapters: string[];
  pinned_comment: string;
  community_post: string;
  end_screen_suggestions: string[];
}

export interface YouTubePlanResponse {
  reply: string;
  plan: YouTubePlan;
  tokens_used: number;
  model: string;
}

export interface CreatorCampaignResponse {
  reply: string;
  title: string;
  content_plan: CreatorWeekPlan[];
  publishing_schedule: string;
  expected_growth: string;
  confidence: number;
  campaign_plan_id: string;
  tokens_used: number;
  model: string;
}
