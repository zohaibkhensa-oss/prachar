"use client";

import { Megaphone } from "lucide-react";
import { LabsBanner } from "@/components/LabsBanner";
import { ComingSoon } from "@/components/ui/coming-soon";

export default function AdvocacyPage() {
  return (
    <div className="space-y-6">
      <LabsBanner
        title="Brand Advocacy"
        description="Turn employees and customers into brand advocates."
        features={["Advocate profiles", "Content library", "Campaign tracking"]}
      />
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">Employee Advocacy</h1>
          <p className="text-sm text-text-secondary mt-1">Turn your team into brand ambassadors</p>
        </div>
      </div>

      <ComingSoon
        icon={<Megaphone className="w-9 h-9" />}
        title="Brand Advocacy is on the way"
        description="Empower your employees and customers to become authentic brand advocates. Share pre-approved content, track engagement, and measure the amplification of your message through the people who know your brand best."
        features={[
          "Advocate Profiles",
          "Pre-approved Content Library",
          "Campaign Tracking",
          "Engagement Leaderboards",
          "Amplification Analytics",
        ]}
      />
    </div>
  );
}
