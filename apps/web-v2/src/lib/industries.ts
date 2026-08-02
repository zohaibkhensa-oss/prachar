/**
 * Industry presets for onboarding and campaign inference.
 *
 * When a user picks an industry, we infer:
 * - Sensible default channels (organic + paid)
 * - Sensible default budget range
 * - Business-language goal suggestions
 * - Tone of voice
 *
 * The user never has to configure these manually.
 */

export interface IndustryPreset {
  id: string;
  label: string;          // "Restaurant" — user-facing
  emoji: string;          // visual cue
  category: string;       // maps to Brand.category in the API
  defaultChannels: string[];
  defaultBudget: number;  // monthly INR
  budgetRange: [number, number];
  goals: string[];        // business-language goals
  tone: string;           // one-line tone description
  blurb: string;          // "We'll get you more customers walking through your door"
}

export const INDUSTRIES: IndustryPreset[] = [
  {
    id: "restaurant",
    label: "Restaurant",
    emoji: "🍽️",
    category: "restaurant",
    defaultChannels: ["google", "instagram", "facebook"],
    defaultBudget: 15000,
    budgetRange: [5000, 50000],
    goals: [
      "Get more customers walking in",
      "Promote my menu & specials",
      "Build a loyal customer base",
      "Get more table reservations",
    ],
    tone: "Warm, welcoming, food-loving",
    blurb: "We'll get more hungry customers walking through your door.",
  },
  {
    id: "clinic",
    label: "Clinic",
    emoji: "🏥",
    category: "healthcare",
    defaultChannels: ["google", "instagram"],
    defaultBudget: 20000,
    budgetRange: [8000, 80000],
    goals: [
      "Get more patient appointments",
      "Build trust in my community",
      "Promote my services",
      "Get more walk-ins",
    ],
    tone: "Caring, professional, trustworthy",
    blurb: "We'll help more patients find and trust your clinic.",
  },
  {
    id: "retail",
    label: "Retail Shop",
    emoji: "🛍️",
    category: "retail",
    defaultChannels: ["google", "instagram", "facebook"],
    defaultBudget: 12000,
    budgetRange: [4000, 40000],
    goals: [
      "Get more foot traffic",
      "Promote my products",
      "Clear out old stock",
      "Build a loyal customer base",
    ],
    tone: "Friendly, helpful, value-driven",
    blurb: "We'll get more shoppers walking into your store.",
  },
  {
    id: "realestate",
    label: "Real Estate",
    emoji: "🏠",
    category: "realestate",
    defaultChannels: ["google", "instagram", "facebook"],
    defaultBudget: 25000,
    budgetRange: [10000, 100000],
    goals: [
      "Get more property enquiries",
      "Showcase my listings",
      "Build my brand as an agent",
      "Get more site visits",
    ],
    tone: "Professional, aspirational, trustworthy",
    blurb: "We'll get more qualified buyers and sellers contacting you.",
  },
  {
    id: "education",
    label: "Education",
    emoji: "🎓",
    category: "education",
    defaultChannels: ["google", "instagram", "youtube"],
    defaultBudget: 18000,
    budgetRange: [6000, 60000],
    goals: [
      "Get more student enrolments",
      "Promote my courses",
      "Build my institute's reputation",
      "Get more demo class signups",
    ],
    tone: "Inspiring, knowledgeable, encouraging",
    blurb: "We'll get more students enrolling in your courses.",
  },
  {
    id: "gym",
    label: "Gym",
    emoji: "💪",
    category: "fitness",
    defaultChannels: ["instagram", "google", "facebook"],
    defaultBudget: 15000,
    budgetRange: [5000, 50000],
    goals: [
      "Get more memberships",
      "Promote my classes",
      "Build a fitness community",
      "Get more trial sessions",
    ],
    tone: "Energetic, motivating, community-focused",
    blurb: "We'll get more members signing up at your gym.",
  },
  {
    id: "salon",
    label: "Salon",
    emoji: "💇",
    category: "salon",
    defaultChannels: ["instagram", "google", "facebook"],
    defaultBudget: 10000,
    budgetRange: [4000, 30000],
    goals: [
      "Get more appointments",
      "Showcase my work",
      "Promote my services",
      "Build a loyal client base",
    ],
    tone: "Stylish, friendly, confidence-boosting",
    blurb: "We'll get more clients booking appointments at your salon.",
  },
  {
    id: "hotel",
    label: "Hotel",
    emoji: "🏨",
    category: "hospitality",
    defaultChannels: ["google", "instagram", "youtube"],
    defaultBudget: 30000,
    budgetRange: [10000, 100000],
    goals: [
      "Get more bookings",
      "Showcase my property",
      "Build my hotel's reputation",
      "Get more direct reservations",
    ],
    tone: "Luxurious, welcoming, hospitable",
    blurb: "We'll get more guests booking direct stays at your hotel.",
  },
  {
    id: "professional",
    label: "Professional Services",
    emoji: "💼",
    category: "professional",
    defaultChannels: ["google", "linkedin"],
    defaultBudget: 20000,
    budgetRange: [8000, 80000],
    goals: [
      "Get more client enquiries",
      "Build my professional brand",
      "Get more leads",
      "Establish thought leadership",
    ],
    tone: "Professional, authoritative, clear",
    blurb: "We'll get more clients finding and contacting you.",
  },
];

export const INDUSTRY_BY_ID: Record<string, IndustryPreset> = Object.fromEntries(
  INDUSTRIES.map((i) => [i.id, i]),
);

/**
 * Friendly channel names — never expose internal channel IDs to users.
 */
export const CHANNEL_LABELS: Record<string, string> = {
  google: "Google",
  instagram: "Instagram",
  facebook: "Facebook",
  youtube: "YouTube",
  tiktok: "TikTok",
  linkedin: "LinkedIn",
  x: "X (Twitter)",
  pinterest: "Pinterest",
  whatsapp: "WhatsApp",
  telegram: "Telegram",
};

/**
 * Map an industry preset to a BrandIn payload for the API.
 */
export function industryToBrand(
  preset: IndustryPreset,
  businessName: string,
  website?: string,
): {
  name: string;
  website?: string;
  category: string;
  locales: string[];
  tone: { voice: string; description: string };
} {
  return {
    name: businessName,
    website: website || undefined,
    category: preset.category,
    locales: ["en-IN"],
    tone: {
      voice: preset.tone,
      description: `${preset.tone} — appropriate for ${preset.label.toLowerCase()}.`,
    },
  };
}
