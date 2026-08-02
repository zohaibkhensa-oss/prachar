"use client";

import { ShoppingBag } from "lucide-react";
import { LabsBanner } from "@/components/LabsBanner";
import { ComingSoon } from "@/components/ui/coming-soon";

export default function ShopPage() {
  return (
    <div className="space-y-6">
      <LabsBanner
        title="E-Commerce"
        description="Sync products and generate AI content for your online store."
        features={["Product sync", "AI content", "Auto-publishing"]}
      />
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">E-Commerce Integration</h1>
          <p className="text-sm text-text-secondary mt-1">Auto-generate ads from your product catalog</p>
        </div>
      </div>

      <ComingSoon
        icon={<ShoppingBag className="w-9 h-9" />}
        title="E-Commerce Integration is on the way"
        description="Connect your Shopify, WooCommerce, or custom store to automatically sync products, generate AI-powered ad creatives for each item, and publish campaigns — turning your entire catalog into ready-to-run ads."
        features={[
          "Shopify & WooCommerce Sync",
          "AI Product Ad Generation",
          "Catalog Auto-Publishing",
          "Dynamic Product Ads",
          "Inventory-Aware Campaigns",
        ]}
      />
    </div>
  );
}
