/**
 * Orb State Machine — 13 frozen states from Architecture Freeze v2.0.
 *
 * Every runtime event carries an orb_state. The frontend simply sets
 * the orb to whatever state an event carries. State transitions are
 * enforced by the Runtime, not the frontend.
 */

export type OrbState =
  | "idle"
  | "wake"
  | "listening"
  | "transcribing"
  | "understanding"
  | "planning"
  | "reasoning"
  | "executing"
  | "generating"
  | "waiting_approval"
  | "speaking"
  | "completed"
  | "cancelled"
  | "error";

export const ORB_STATES: OrbState[] = [
  "idle",
  "wake",
  "listening",
  "transcribing",
  "understanding",
  "planning",
  "reasoning",
  "executing",
  "generating",
  "waiting_approval",
  "speaking",
  "completed",
  "cancelled",
  "error",
];

export const ORB_STATE_LABELS: Record<OrbState, string> = {
  idle: "PRACHAR AI",
  wake: "Waking up...",
  listening: "Listening...",
  transcribing: "Transcribing...",
  understanding: "Understanding...",
  planning: "Planning...",
  reasoning: "Reasoning...",
  executing: "Executing...",
  generating: "Generating...",
  waiting_approval: "Waiting for approval",
  speaking: "Speaking...",
  completed: "Done",
  cancelled: "Cancelled",
  error: "Something went wrong",
};

export const ORB_STATE_DESCRIPTIONS: Record<OrbState, string> = {
  idle: "Ready to help",
  wake: "I heard you",
  listening: "I'm listening",
  transcribing: "Converting your voice to text",
  understanding: "Understanding what you need",
  planning: "Planning the best approach",
  reasoning: "Thinking through this",
  executing: "Working on it",
  generating: "Creating your content",
  waiting_approval: "I need your approval",
  speaking: "Here's what I found",
  completed: "All done!",
  cancelled: "Okay, cancelled",
  error: "Let me try again",
};

/**
 * Map an event type to an orb state.
 * This is the bridge between runtime events and the orb.
 */
export function orbStateFromEvent(eventType: string): OrbState {
  // runtime.*
  if (eventType === "runtime.session.started") return "understanding";
  if (eventType === "runtime.session.completed") return "completed";
  if (eventType === "runtime.session.cancelled") return "cancelled";
  if (eventType === "runtime.session.error") return "error";
  if (eventType === "runtime.session.timeout") return "error";

  // planner.*
  if (eventType === "planner.intent.classifying" || eventType === "planner.intent.classified")
    return "understanding";
  if (eventType === "planner.plan.creating" || eventType === "planner.plan.created")
    return "planning";
  if (eventType === "planner.decision.created") return "planning";
  if (eventType === "planner.decision.approved") return "executing";
  if (eventType === "planner.decision.rejected") return "completed";

  // tool.*
  if (eventType === "tool.started") return "executing";
  if (eventType === "tool.progress") return "reasoning";
  if (eventType === "tool.completed") return "generating";
  if (eventType === "tool.error") return "reasoning";
  if (eventType === "tool.cancelled") return "cancelled";

  // campaign.*
  if (eventType.startsWith("campaign.") && eventType.endsWith(".started")) return "reasoning";
  if (eventType.startsWith("campaign.") && eventType.endsWith(".completed")) return "reasoning";

  // creative.*
  if (eventType.startsWith("creative.") && eventType.endsWith(".started")) return "generating";
  if (eventType.startsWith("creative.") && eventType.endsWith(".completed")) return "generating";

  // review.* / agency.*
  if (eventType.startsWith("review.") || eventType.startsWith("agency."))
    return "reasoning";

  // approval.*
  if (eventType === "approval.requested") return "waiting_approval";
  if (eventType === "approval.granted") return "executing";
  if (eventType === "approval.denied") return "completed";

  // voice.*
  if (eventType === "voice.started") return "listening";
  if (eventType === "voice.transcribing") return "transcribing";
  if (eventType === "voice.completed") return "understanding";
  if (eventType === "voice.speaking.started") return "speaking";
  if (eventType === "voice.speaking.finished") return "idle";
  if (eventType === "voice.interrupted") return "listening";

  // memory.*
  if (eventType.startsWith("memory.")) return "idle";

  // notification.*
  if (eventType.startsWith("notification.")) return "idle";

  // analytics.*
  if (eventType.startsWith("analytics.")) return "reasoning";

  // workspace.*
  if (eventType.startsWith("workspace.")) return "idle";

  // Default
  return "idle";
}

/**
 * Check if an orb state is "active" (orb is doing something).
 */
export function isOrbActive(state: OrbState): boolean {
  return !["idle", "completed", "cancelled", "error"].includes(state);
}

/**
 * Check if an orb state should show ripple waves.
 */
export function shouldShowWaves(state: OrbState): boolean {
  return ["listening", "speaking", "executing", "generating"].includes(state);
}

/**
 * Get the animation duration for the orb based on state.
 */
export function getOrbAnimationDuration(state: OrbState): number {
  switch (state) {
    case "idle": return 5;
    case "listening": return 1.8;
    case "speaking": return 1.2;
    case "executing": return 2;
    case "generating": return 1.5;
    case "planning": return 3;
    case "reasoning": return 2.5;
    case "understanding": return 3;
    case "waiting_approval": return 2;
    default: return 4;
  }
}
