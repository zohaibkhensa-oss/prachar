"use client";

import { Palette } from "lucide-react";
import { LabsBanner } from "@/components/LabsBanner";
import { ComingSoon } from "@/components/ui/coming-soon";

export default function DesignPage() {
  return (
    <div className="space-y-6 relative">
      <LabsBanner
        title="Design AI"
        description="Create marketing designs, logos, and brand visuals with AI assistance."
        features={["Template library", "AI generation", "Brand kit"]}
      />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">Design Studio</h1>
          <p className="text-sm text-text-secondary mt-1">AI-powered design — better than Canva</p>
        </div>
        <span className="badge badge-accent">
          <Palette className="w-3 h-3" /> AI Powered
        </span>
      </div>

      <ComingSoon
        icon={<Palette className="w-9 h-9" />}
        title="Design Studio is on the way"
        description="A full AI-powered design studio with templates, brand kits, magic editing tools, and one-click generation of marketing creatives across every platform. Your brand visuals, effortlessly beautiful."
        features={[
          "AI Design Generator",
          "Template Library",
          "Brand Kit & Colors",
          "Magic Tools",
          "One-click Resize",
          "Background Remover",
        ]}
      />
    </div>
  );
}
