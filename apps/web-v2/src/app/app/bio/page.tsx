"use client";

import { Link as LinkIcon } from "lucide-react";
import { LabsBanner } from "@/components/LabsBanner";
import { ComingSoon } from "@/components/ui/coming-soon";

export default function BioPage() {
  return (
    <div className="space-y-6">
      <LabsBanner
        title="Link in Bio"
        description="Create a beautiful link-in-bio page with AI suggestions."
        features={["Custom themes", "Drag & drop", "Analytics"]}
      />
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">Link-in-Bio</h1>
          <p className="text-sm text-text-secondary mt-1">Your all-in-one bio link — better than Buffer's Start Page</p>
        </div>
      </div>

      <ComingSoon
        icon={<LinkIcon className="w-9 h-9" />}
        title="Link-in-Bio is on the way"
        description="A beautiful, customizable link-in-bio page with drag-and-drop editing, custom themes, social icons, custom domains, and full analytics — clicks, views, and conversions tracked in real time."
        features={[
          "Custom Themes & Fonts",
          "Drag & Drop Editor",
          "Social Icons",
          "Custom Domain",
          "Click & Conversion Analytics",
          "AI Link Suggestions",
        ]}
      />
    </div>
  );
}
