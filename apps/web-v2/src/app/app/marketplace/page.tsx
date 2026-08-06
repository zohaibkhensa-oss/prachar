"use client";

import { Store } from "lucide-react";
import { LabsBanner } from "@/components/LabsBanner";
import { ComingSoon } from "@/components/ui/coming-soon";

export default function MarketplacePage() {
  return (
    <div className="p-4 lg:p-8 max-w-[1600px] mx-auto animate-fade-in space-y-6">
      <LabsBanner
        title="Marketplace"
        description="Extend PRACHAR AI with integrations and add-ons."
        features={["Integrations", "Templates", "Plugins"]}
      />
      {/* Header */}
      <div className="flex flex-col gap-4 mb-2 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="font-display uppercase text-2xl sm:text-3xl lg:text-4xl tracking-wide text-text mb-1">
            Marketplace
          </h1>
          <p className="text-sm text-text-secondary">
            Extend PRACHAR with channels, AI models, and creative tools.
          </p>
        </div>
      </div>

      <ComingSoon
        icon={<Store className="w-9 h-9" />}
        title="The Marketplace is being curated"
        description="A curated marketplace of integrations, templates, plugins, and AI models to extend PRACHAR's capabilities. Connect new channels, install creative tools, and supercharge your workflow — all in one place."
        features={[
          "Channel Integrations",
          "Design Templates",
          "AI Model Add-ons",
          "Workflow Plugins",
          "Community Extensions",
        ]}
      />
    </div>
  );
}
