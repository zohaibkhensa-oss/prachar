"use client";

import { Radar } from "lucide-react";
import { LabsBanner } from "@/components/LabsBanner";
import { ComingSoon } from "@/components/ui/coming-soon";

export default function ListeningPage() {
  return (
    <div className="space-y-6">
      <LabsBanner
        title="Social Listening"
        description="Monitor mentions, sentiment, and trends across platforms."
        features={["Mention tracking", "Sentiment analysis", "Competitor monitoring"]}
      />
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">Social Listening</h1>
          <p className="text-sm text-text-secondary mt-1">Real-time brand intelligence across the web</p>
        </div>
      </div>

      <ComingSoon
        icon={<Radar className="w-9 h-9" />}
        title="Social Listening is on the way"
        description="Monitor brand mentions, sentiment, and emerging trends across every major platform in real time. Track competitors, catch crises early, and discover opportunities — all powered by AI that surfaces what matters most."
        features={[
          "Real-time Mention Tracking",
          "AI Sentiment Analysis",
          "Competitor Monitoring",
          "Trend Detection",
          "Alert & Notification System",
        ]}
      />
    </div>
  );
}
