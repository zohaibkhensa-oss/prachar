"use client";

import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";

export interface Brand {
  id: string;
  name: string;
  website: string | null;
  category: string | null;
  customer_type: string; // "business" | "creator"
  locales: string[] | null;
  tone: { voice?: string; description?: string } | null;
  visibility_score: number | null;
  created_at: string;
}

export interface CampaignPlan {
  id: string;
  brand_id: string;
  name: string;
  goal: string;
  status: string;
  overall_confidence: number;
  campaign: Record<string, unknown>;
  created_at: string;
}

/**
 * Fetch the user's brands. Most users have exactly one brand.
 */
export function useBrands() {
  return useQuery<Brand[]>({
    queryKey: ["brands"],
    queryFn: () => apiGet<Brand[]>("/brands"),
    retry: 1,
  });
}

/**
 * Fetch the active brand — either from localStorage or the first brand.
 */
export function useActiveBrand() {
  const { data: brands, isLoading, error } = useBrands();
  const activeId = typeof window !== "undefined"
    ? window.localStorage.getItem("prachar_active_brand")
    : null;
  const active = brands?.find((b) => b.id === activeId) ?? brands?.[0] ?? null;
  return { brand: active, brands, isLoading, error };
}

/**
 * Fetch saved campaign plans for a brand.
 * Passes `brand_id` so only the active brand's plans are returned.
 */
export function useCampaignPlans(brandId: string | null) {
  return useQuery<CampaignPlan[]>({
    queryKey: ["campaign-plans", brandId],
    queryFn: () =>
      apiGet<CampaignPlan[]>(
        brandId ? `/campaign-brain/plans?brand_id=${encodeURIComponent(brandId)}` : "/campaign-brain/plans",
      ),
    enabled: !!brandId,
    retry: 1,
  });
}
