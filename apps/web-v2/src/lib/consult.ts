/** Types for the conversational onboarding (/consult) API. */

export interface BusinessExtraction {
  business_name: string;
  industry: string;
  location: string;
  products: string[];
  services: string[];
  audience: string;
  goals: string[];
  website: string;
  social_handles: string[];
  additional_context: string;
}

export interface BusinessUnderstanding {
  summary: string;
  strengths: string[];
  weaknesses: string[];
  likely_customers: string[];
  likely_competitors: string[];
  marketing_opportunities: string[];
  seasonal_opportunities: string[];
  marketing_maturity: string;
  potential_risks: string[];
}

export interface GrowthOpportunity {
  title: string;
  description: string;
  business_impact: "High" | "Medium" | "Low" | string;
  difficulty: "Easy" | "Medium" | "Hard" | string;
  timeframe: string;
}

export interface WeekPlan {
  week: number;
  theme: string;
  objectives: string[];
  content: string[];
  offers: string[];
  channels: string[];
  kpis: string[];
}

export interface ConsultResponse {
  reply: string;
  business: BusinessUnderstanding;
  growth_opportunities: GrowthOpportunity[];
  plan: WeekPlan[];
  extracted: BusinessExtraction;
  brand_id: string;
  brand_name: string;
  confidence: number;
  tokens_used: number;
  model: string;
}

export interface CampaignPreview {
  title: string;
  hero_image_concept: string;
  video_concept: string;
  post_ideas: string[];
  estimated_reach: string;
  expected_enquiries: string;
  budget_estimate: string;
  why_this_campaign: string;
  confidence: number;
  expected_benefit: string;
  risks: string[];
  alternative: string;
}

export interface CampaignPreviewResponse {
  reply: string;
  preview: CampaignPreview;
  campaign_plan_id: string;
  tokens_used: number;
  model: string;
}
