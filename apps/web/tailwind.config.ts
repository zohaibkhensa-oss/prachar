import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/app/**/*.{ts,tsx}",
    "./src/components/**/*.{ts,tsx}",
    "./src/lib/**/*.{ts,tsx}",
  ],
  theme: {
    container: {
      center: true,
      padding: "1.5rem",
      screens: { "2xl": "96rem" },
    },
    extend: {
      colors: {
        // ─── Dark-first palette ───
        bg: {
          DEFAULT: "#0B0F14",
          surface: "#111827",
          card: "#161B22",
          elevated: "#1C2333",
          hover: "#1F2937",
        },
        text: {
          DEFAULT: "#F9FAFB",
          secondary: "#94A3B8",
          tertiary: "#64748B",
          muted: "#475569",
        },
        accent: {
          DEFAULT: "#8B5CF6",
          dark: "#7C3AED",
          glow: "rgba(139,92,246,0.15)",
        },
        success: "#22C55E",
        danger: "#EF4444",
        info: "#3B82F6",
        warning: "#F59E0B",
        // Legacy aliases for backward compat
        ink: { DEFAULT: "#0B0F14" },
        paper: { DEFAULT: "#0B0F14" },
        yellow: { DEFAULT: "#8B5CF6", dark: "#7C3AED" },
        blue: "#3B82F6",
      },
      fontFamily: {
        display: ["var(--font-display)", "sans-serif"],
        body: ["var(--font-body)", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
        sans: ["var(--font-body)", "sans-serif"],
      },
      borderRadius: {
        none: "0",
        DEFAULT: "8px",
        sm: "6px",
        md: "8px",
        lg: "12px",
        xl: "16px",
        "2xl": "20px",
        "3xl": "24px",
        full: "9999px",
      },
      spacing: {
        18: "4.5rem",
        22: "5.5rem",
        30: "7.5rem",
        38: "9.5rem",
      },
      borderWidth: {
        DEFAULT: "1px",
        0: "0",
        2: "2px",
        3: "3px",
      },
      boxShadow: {
        // 3D depth shadows
        "3d-sm": "0 2px 8px rgba(0,0,0,0.3), 0 1px 2px rgba(0,0,0,0.2)",
        "3d": "0 8px 24px rgba(0,0,0,0.4), 0 2px 8px rgba(0,0,0,0.2)",
        "3d-lg": "0 16px 48px rgba(0,0,0,0.5), 0 4px 16px rgba(0,0,0,0.3)",
        "3d-xl": "0 32px 64px rgba(0,0,0,0.6), 0 8px 32px rgba(0,0,0,0.4)",
        glow: "0 0 24px rgba(139,92,246,0.2)",
        "glow-blue": "0 0 24px rgba(59,130,246,0.2)",
        "glow-green": "0 0 24px rgba(34,197,94,0.2)",
        "glow-red": "0 0 24px rgba(239,68,68,0.2)",
        "inner-glow": "inset 0 1px 0 rgba(255,255,255,0.05)",
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "gradient-conic": "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
        "gradient-mesh": "radial-gradient(at 0% 0%, rgba(59,130,246,0.08) 0%, transparent 50%), radial-gradient(at 100% 0%, rgba(139,92,246,0.06) 0%, transparent 50%), radial-gradient(at 50% 100%, rgba(34,197,94,0.05) 0%, transparent 50%)",
        "gradient-surface": "linear-gradient(145deg, #161B22 0%, #111827 100%)",
        "gradient-card": "linear-gradient(145deg, rgba(28,35,51,0.6) 0%, rgba(17,24,39,0.6) 100%)",
        "gradient-accent": "linear-gradient(135deg, #8B5CF6 0%, #7C3AED 100%)",
        "gradient-dark": "linear-gradient(180deg, #0B0F14 0%, #111827 100%)",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in-scale": {
          "0%": { opacity: "0", transform: "scale(0.95)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        "slide-in-right": {
          "0%": { opacity: "0", transform: "translateX(20px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        "shimmer": {
          "0%": { backgroundPosition: "-1000px 0" },
          "100%": { backgroundPosition: "1000px 0" },
        },
        "glow-pulse": {
          "0%, 100%": { boxShadow: "0 0 20px rgba(139,92,246,0.1)" },
          "50%": { boxShadow: "0 0 40px rgba(139,92,246,0.25)" },
        },
        "ai-thinking": {
          "0%, 100%": { opacity: "0.3" },
          "50%": { opacity: "1" },
        },
        "float": {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-6px)" },
        },
        "rotate-3d": {
          "0%": { transform: "perspective(1000px) rotateY(0deg)" },
          "100%": { transform: "perspective(1000px) rotateY(360deg)" },
        },
        "marquee": {
          "0%": { transform: "translateX(0)" },
          "100%": { transform: "translateX(-50%)" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.4s ease-out",
        "fade-in-scale": "fade-in-scale 0.3s ease-out",
        "slide-in-right": "slide-in-right 0.3s ease-out",
        shimmer: "shimmer 2s linear infinite",
        "glow-pulse": "glow-pulse 2s ease-in-out infinite",
        "ai-thinking": "ai-thinking 1.5s ease-in-out infinite",
        float: "float 3s ease-in-out infinite",
        "rotate-3d": "rotate-3d 8s linear infinite",
        marquee: "marquee 30s linear infinite",
      },
      transitionTimingFunction: {
        "out-expo": "cubic-bezier(0.16, 1, 0.3, 1)",
        "out-quart": "cubic-bezier(0.25, 1, 0.5, 1)",
        spring: "cubic-bezier(0.34, 1.56, 0.64, 1)",
      },
    },
  },
  plugins: [],
};

export default config;
