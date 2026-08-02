"use client";

import { CalendarDays } from "lucide-react";
import { ComingSoon } from "@/components/ui/coming-soon";

export default function CalendarPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">Content Calendar</h1>
          <p className="text-sm text-text-secondary mt-1">Schedule and visualise your content across all platforms</p>
        </div>
      </div>

      <ComingSoon
        icon={<CalendarDays className="w-9 h-9" />}
        title="Content Calendar is on the way"
        description="A visual calendar to schedule, draft, and publish content across all your connected platforms. Drag-and-drop scheduling, best-time-to-post heatmaps, multi-platform previews, and AI-suggested content plans — all in one beautiful view."
        features={[
          "Drag & Drop Scheduling",
          "Multi-Platform Publishing",
          "Best-Time Heatmaps",
          "Content Drafts & Approval",
          "Weekly AI Content Plans",
        ]}
      />
    </div>
  );
}
