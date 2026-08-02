"use client";

import { apiGet, apiPost } from "@/lib/api";

// ─── Types ────────────────────────────────────────────────────────────────

export interface ProactiveAnomaly {
  brand_id: string;
  campaign_id: string;
  metric: string;
  magnitude: number;
  timeframe: string;
  severity: "high" | "medium" | "low";
  direction: "drop" | "spike" | "plateau";
}

export interface ProactiveRecommendation {
  what_to_do: string;
  why: string;
  creative_directions: string[];
  expected_impact: string;
}

export interface ProactiveNotification {
  anomaly: ProactiveAnomaly;
  recommendation: ProactiveRecommendation;
}

export interface ProactiveNotificationsResponse {
  notifications: ProactiveNotification[];
  count: number;
}

export interface PracharMessage {
  id: string;
  prachar_message: string;
  anomaly: ProactiveAnomaly;
  recommendation: ProactiveRecommendation;
  severity: "high" | "medium" | "low";
}

export interface PracharMessagesResponse {
  messages: PracharMessage[];
  count: number;
}

export interface LaunchResponse {
  recommendation_id: string;
  brand_id: string;
  campaign_name: string;
  goal: string;
  budget: string;
  creative_directions: string[];
  what_to_do: string;
  why: string;
  expected_impact: string;
  prachar_message: string;
  prefill: {
    brand_id: string;
    goal: string;
    budget: string;
    creative_directions: string[];
    what_to_do: string;
    why: string;
    expected_impact: string;
    source_anomaly: ProactiveAnomaly;
  };
}

// ─── API client ────────────────────────────────────────────────────────────

/** Fetch pending proactive notifications (anomalies + recommendations). */
export function getProactiveNotifications(): Promise<ProactiveNotificationsResponse> {
  return apiGet<ProactiveNotificationsResponse>("/proactive/notifications");
}

/** Fetch pending proactive messages from PRACHAR AI. */
export function getPracharMessages(): Promise<PracharMessagesResponse> {
  return apiGet<PracharMessagesResponse>("/chat/proactive");
}

/** Launch a proactive recommendation — returns pre-filled campaign data. */
export function launchRecommendation(notificationId: string): Promise<LaunchResponse> {
  return apiPost<LaunchResponse>(`/proactive/${encodeURIComponent(notificationId)}/launch`);
}
