"use client";

import { Target } from "lucide-react";
import { LabsBanner } from "@/components/LabsBanner";
import { ComingSoon } from "@/components/ui/coming-soon";

export default function AudiencePage() {
  return (
    <div className="p-4 lg:p-8 max-w-[1600px] mx-auto animate-fade-in space-y-6">
      <LabsBanner
        title="Audience Builder"
        description="Define and refine your target audience with AI assistance."
        features={["Demographics", "Interests", "Reach estimation"]}
      />
      <div className="mb-2">
        <h1 className="font-display uppercase text-2xl sm:text-3xl lg:text-4xl tracking-wide text-text mb-1">
          Audience Builder
        </h1>
        <p className="text-sm text-text-secondary">
          Craft precision audiences with AI-assisted targeting.
        </p>
      </div>

      <ComingSoon
        icon={<Target className="w-9 h-9" />}
        title="Audience Builder is on the way"
        description="Define and refine your target audience with AI assistance. Set demographics, interests, behaviors, and geographic targeting — then get instant reach estimates and AI-suggested refinements to maximize your campaign's precision."
        features={[
          "Demographic Targeting",
          "Interest & Behavior Filters",
          "AI Reach Estimation",
          "Lookalike Audiences",
          "Saved Segments",
        ]}
      />
    </div>
  );
}
