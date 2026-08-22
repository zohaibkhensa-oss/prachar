/**
 * Friendly tool name mapping — translates internal tool names
 * to user-facing labels for progress indicators.
 */

export interface ToolLabel {
  label: string;
  verb: string;
  icon: "image" | "video" | "campaign" | "review" | "publish" | "memory" | "chat" | "analytics" | "generic";
}

export const TOOL_LABELS: Record<string, ToolLabel> = {
  "creative_studio.generate_image": {
    label: "Generating image…",
    verb: "Generating image",
    icon: "image",
  },
  "video_gen.generate": {
    label: "Creating video…",
    verb: "Creating video",
    icon: "video",
  },
  "campaign_brain.analyse": {
    label: "Analysing your business…",
    verb: "Analysing business",
    icon: "campaign",
  },
  "campaign_brain.strategy": {
    label: "Developing strategy…",
    verb: "Developing strategy",
    icon: "campaign",
  },
  "campaign_brain.creative": {
    label: "Creating creative direction…",
    verb: "Creating creative direction",
    icon: "campaign",
  },
  "campaign_brain.media": {
    label: "Planning media…",
    verb: "Planning media",
    icon: "campaign",
  },
  "campaign_brain.full_campaign": {
    label: "Building your campaign…",
    verb: "Building campaign",
    icon: "campaign",
  },
  "council.review": {
    label: "My team is reviewing…",
    verb: "Reviewing with team",
    icon: "review",
  },
  "channel.publish": {
    label: "Publishing…",
    verb: "Publishing",
    icon: "publish",
  },
  "channel.list": {
    label: "Checking your channels…",
    verb: "Checking channels",
    icon: "publish",
  },
  "channel.connect": {
    label: "Connecting channel…",
    verb: "Connecting channel",
    icon: "publish",
  },
  "channel.metrics": {
    label: "Pulling metrics…",
    verb: "Pulling metrics",
    icon: "analytics",
  },
  "performance.story": {
    label: "Analysing performance…",
    verb: "Analysing performance",
    icon: "analytics",
  },
  "performance.summary": {
    label: "Summarising results…",
    verb: "Summarising results",
    icon: "analytics",
  },
  "memory.update": {
    label: "Saving learnings…",
    verb: "Saving learnings",
    icon: "memory",
  },
  "memory.retrieve": {
    label: "Recalling…",
    verb: "Recalling",
    icon: "memory",
  },
  "chat.respond": {
    label: "Thinking…",
    verb: "Thinking",
    icon: "chat",
  },
  "creator.youtube_plan": {
    label: "Planning YouTube content…",
    verb: "Planning YouTube",
    icon: "video",
  },
  "creator.repurpose": {
    label: "Repurposing content…",
    verb: "Repurposing content",
    icon: "generic",
  },
  "review.publish": {
    label: "Publishing review…",
    verb: "Publishing review",
    icon: "review",
  },
  "audit.run": {
    label: "Running brand audit…",
    verb: "Running audit",
    icon: "analytics",
  },
};

export function getToolLabel(toolName: string): ToolLabel {
  // Try exact match first
  if (TOOL_LABELS[toolName]) return TOOL_LABELS[toolName];

  // Try prefix match (e.g. "campaign_brain." matches any campaign_brain.* tool)
  for (const [key, label] of Object.entries(TOOL_LABELS)) {
    if (key.endsWith(".") && toolName.startsWith(key)) return label;
  }

  // Fallback: prettify the tool name
  const parts = toolName.split(".");
  const last = parts[parts.length - 1] || toolName;
  const pretty = last
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
  return {
    label: `${pretty}…`,
    verb: pretty,
    icon: "generic",
  };
}

/**
 * Contextual follow-up suggestions based on the last artefact or tool used.
 */
export function getContextualSuggestions(
  lastTool?: string,
  artefactKinds?: string[],
): string[] {
  // After image generation
  if (lastTool === "creative_studio.generate_image" || artefactKinds?.includes("image")) {
    return [
      "Make a video version of this",
      "Create a campaign with this image",
      "Publish this to Instagram",
      "Generate another variation",
    ];
  }

  // After video generation
  if (lastTool === "video_gen.generate" || artefactKinds?.includes("video_preview")) {
    return [
      "Publish this to YouTube",
      "Create an Instagram reel version",
      "Generate a thumbnail image",
      "Create a campaign around this video",
    ];
  }

  // After channel publish
  if (lastTool === "channel.publish") {
    return [
      "Check performance",
      "Create another post",
      "Generate a report",
    ];
  }

  // After campaign creation
  if (lastTool?.startsWith("campaign_brain.")) {
    return [
      "Review with your team",
      "Generate creatives",
      "Plan the media budget",
      "Publish to channels",
    ];
  }

  // After council review
  if (lastTool === "council.review") {
    return [
      "Apply the feedback",
      "Publish the campaign",
      "Generate improvements",
    ];
  }

  // Default suggestions
  return [
    "Create a campaign",
    "Generate an image",
    "Make a video",
    "Check performance",
  ];
}
