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

// ─── iOS Safari speech synthesis fixes ───────────────────────────────────────
// 1. Voices load asynchronously — cache them when the voiceschanged event fires
// 2. iOS requires a "warm-up" utterance triggered by a user gesture to unlock
//    speech synthesis. Subsequent calls from non-gesture contexts then work.
// 3. iOS Safari has a bug where speechSynthesis.speak() silently fails if
//    called without a prior user interaction.

let _cachedVoices: SpeechSynthesisVoice[] = [];
let _iOSUnlocked = false;

function refreshVoices() {
  if (!isSpeechSynthesisAvailable()) return;
  _cachedVoices = window.speechSynthesis.getVoices();
}

// Load voices immediately and on voiceschanged event
if (typeof window !== "undefined" && "speechSynthesis" in window) {
  refreshVoices();
  window.speechSynthesis.addEventListener("voiceschanged", refreshVoices);
  // Some browsers fire voiceschanged late — poll a few times
  setTimeout(refreshVoices, 500);
  setTimeout(refreshVoices, 2000);
}

/**
 * Unlock speech synthesis on iOS Safari.
 * Call this from a user gesture (tap/click) to enable TTS for subsequent
 * non-gesture calls (e.g., from SSE callbacks).
 */
export function unlockSpeechSynthesis(): void {
  if (!isSpeechSynthesisAvailable()) return;
  if (_iOSUnlocked) return;

  // iOS Safari workaround: speak a near-silent utterance to unlock the API
  const u = new SpeechSynthesisUtterance("");
  u.volume = 0;
  u.rate = 1;
  window.speechSynthesis.speak(u);
  _iOSUnlocked = true;
}

/**
 * Speak text using Web Speech Synthesis.
 * Handles iOS Safari quirks (async voice loading, autoplay restrictions).
 */
export function speak(text: string, onEnd?: () => void): void {
  if (!isSpeechSynthesisAvailable()) {
    onEnd?.();
    return;
  }

  // Cancel any pending speech
  window.speechSynthesis.cancel();

  // Small delay after cancel — iOS Safari needs this
  setTimeout(() => {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.05;
    utterance.pitch = 1.0;
    utterance.volume = 0.85;

    // Use cached voices (getVoices() can return [] on iOS before voiceschanged)
    const voices = _cachedVoices.length > 0 ? _cachedVoices : window.speechSynthesis.getVoices();
    const preferred = voices.find((v) =>
      ["Samantha", "Google US English", "Daniel", "Karen", "Moira", "Tessa"].includes(v.name)
    );
    if (preferred) utterance.voice = preferred;

    // iOS Safari sometimes doesn't fire onend — add a fallback timeout
    let ended = false;
    const safeEnd = () => {
      if (ended) return;
      ended = true;
      onEnd?.();
    };
    utterance.onend = safeEnd;
    utterance.onerror = safeEnd;

    // Fallback: if onend doesn't fire within 30s, call it anyway
    const fallbackTimer = setTimeout(safeEnd, 30000);

    try {
      window.speechSynthesis.speak(utterance);
    } catch {
      clearTimeout(fallbackTimer);
      safeEnd();
    }

    // Clear fallback timer when utterance ends
    const origOnEnd = utterance.onend;
    utterance.onend = (e) => {
      clearTimeout(fallbackTimer);
      if (origOnEnd) origOnEnd.call(utterance, e);
    };
    utterance.onerror = (e) => {
      clearTimeout(fallbackTimer);
      safeEnd();
    };
  }, 50);
}

/**
 * Stop any ongoing speech.
 */
export function stopSpeaking(): void {
  if (isSpeechSynthesisAvailable()) {
    window.speechSynthesis.cancel();
  }
}
