"use client";

import { Users } from "lucide-react";
import { LabsBanner } from "@/components/LabsBanner";
import { ComingSoon } from "@/components/ui/coming-soon";

export default function InfluencersPage() {
  return (
    <div className="space-y-6">
      <LabsBanner
        title="Influencer Marketing"
        description="Discover, match, and manage influencer collaborations."
        features={["AI matching", "Campaign pipeline", "Reach analytics"]}
      />
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">Influencer Marketing</h1>
          <p className="text-sm text-text-secondary mt-1">Discover, manage, and measure creator campaigns</p>
        </div>
      </div>

      <ComingSoon
        icon={<Users className="w-9 h-9" />}
        title="Influencer Marketing is on the way"
        description="Discover creators in your niche with AI-powered matching, manage campaign pipelines from outreach to publishing, and track reach and ROI — all in one place."
        features={[
          "AI Creator Matching",
          "Campaign Pipeline",
          "Reach & ROI Analytics",
          "Outreach Templates",
          "Contract Management",
        ]}
      />
    </div>
  );
}
