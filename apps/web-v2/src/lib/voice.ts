/**
 * Voice state management for the AI orb.
 * Tracks the current orb state and provides helpers.
 */

export type OrbState = "idle" | "listening" | "thinking" | "speaking";

export const ORB_STATE_LABELS: Record<OrbState, string> = {
  idle: "PRACHAR AI",
  listening: "Listening...",
  thinking: "Thinking...",
  speaking: "Speaking...",
};

/**
 * Check if the Web Speech API is available.
 */
export function isSpeechRecognitionAvailable(): boolean {
  if (typeof window === "undefined") return false;
  return "SpeechRecognition" in window || "webkitSpeechRecognition" in window;
}

/**
 * Check if speech synthesis is available.
 */
export function isSpeechSynthesisAvailable(): boolean {
  if (typeof window === "undefined") return false;
  return "speechSynthesis" in window;
}

/**
 * Wake words for PRACHAR AI.
 */
export const WAKE_WORDS = [
  "hey prachar",
  "hey prachar ai",
  "hay prachar",
  "a prachar",
  "hey prachar a i",
  "hey pracher",
  "hey prasher",
];

/**
 * Check if a transcript contains a wake word.
 */
export function containsWakeWord(transcript: string): boolean {
  const lower = transcript.toLowerCase().trim();
  return WAKE_WORDS.some((word) => lower.includes(word));
}

/**
 * Speak text using Web Speech Synthesis.
 */
export function speak(text: string, onEnd?: () => void): void {
  if (!isSpeechSynthesisAvailable()) {
    onEnd?.();
    return;
  }
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1.05;
  utterance.pitch = 1.0;
  utterance.volume = 0.85;

  // Prefer a natural-sounding voice
  const voices = window.speechSynthesis.getVoices();
  const preferred = voices.find((v) => ["Samantha", "Google US English", "Daniel"].includes(v.name));
  if (preferred) utterance.voice = preferred;

  utterance.onend = () => onEnd?.();
  window.speechSynthesis.speak(utterance);
}

/**
 * Stop any ongoing speech.
 */
export function stopSpeaking(): void {
  if (isSpeechSynthesisAvailable()) {
    window.speechSynthesis.cancel();
  }
}
