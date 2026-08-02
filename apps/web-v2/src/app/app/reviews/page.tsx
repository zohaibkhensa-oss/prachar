"use client";

import { Star, Sparkles } from "lucide-react";
import { ComingSoon } from "@/components/ui/coming-soon";

export default function ReviewsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">Review Management</h1>
          <p className="text-sm text-text-secondary mt-1">Unified inbox for all your review platforms</p>
        </div>
        <span className="badge badge-accent">
          <Sparkles className="w-3 h-3" /> AI-Powered Responses
        </span>
      </div>

      <ComingSoon
        icon={<Star className="w-9 h-9" />}
        title="Review Management is on the way"
        description="A unified inbox for all your review platforms — Google, Facebook, Yelp, and more. Respond to reviews with AI-crafted replies, track sentiment trends, and turn customer feedback into actionable insights."
        features={[
          "Google & Facebook Reviews",
          "AI-Crafted Responses",
          "Sentiment Trend Tracking",
          "Review Alerts",
          "Response Templates",
        ]}
      />
    </div>
  );
}
