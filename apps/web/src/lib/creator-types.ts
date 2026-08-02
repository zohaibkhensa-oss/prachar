/** Creator type presets for onboarding. */

export interface CreatorTypePreset {
  id: string;
  label: string;
  emoji: string;
  category: string;       // maps to Brand.category
  platforms: string[];
  blurb: string;
}

export const CREATOR_TYPES: CreatorTypePreset[] = [
  { id: "youtube_creator", label: "YouTube Creator", emoji: "📹", category: "youtube", platforms: ["YouTube"], blurb: "Grow your channel with better titles, thumbnails, and content." },
  { id: "instagram_creator", label: "Instagram Creator", emoji: "📸", category: "instagram", platforms: ["Instagram"], blurb: "Build your Instagram presence with reels, posts, and stories." },
  { id: "podcaster", label: "Podcaster", emoji: "🎙️", category: "podcast", platforms: ["Spotify", "Apple Podcasts"], blurb: "Grow your podcast audience and find sponsors." },
  { id: "influencer", label: "Influencer", emoji: "✨", category: "influencer", platforms: ["Instagram", "TikTok"], blurb: "Grow your following and land brand deals." },
  { id: "gaming_creator", label: "Gaming Creator", emoji: "🎮", category: "gaming", platforms: ["YouTube", "Twitch"], blurb: "Grow your gaming channel and community." },
  { id: "educator", label: "Educator", emoji: "🎓", category: "education", platforms: ["YouTube"], blurb: "Teach your audience and grow your educational channel." },
  { id: "media_company", label: "Media Company", emoji: "📰", category: "media", platforms: ["YouTube", "Instagram"], blurb: "Scale your media brand across platforms." },
  { id: "production_studio", label: "Production Studio", emoji: "🎬", category: "production", platforms: ["YouTube"], blurb: "Produce content that gets noticed." },
  { id: "musician", label: "Musician", emoji: "🎵", category: "music", platforms: ["YouTube", "Spotify"], blurb: "Grow your music career and audience." },
  { id: "personal_brand", label: "Personal Brand", emoji: "🚀", category: "personal", platforms: ["LinkedIn", "YouTube"], blurb: "Build your personal brand and authority." },
];

export const CREATOR_TYPE_BY_ID: Record<string, CreatorTypePreset> = Object.fromEntries(
  CREATOR_TYPES.map((c) => [c.id, c]),
);

/** Business types (shared with existing industries.ts but listed here for the onboarding screen). */
export interface BusinessTypePreset {
  id: string;
  label: string;
  emoji: string;
  blurb: string;
}

export const BUSINESS_TYPES: BusinessTypePreset[] = [
  { id: "restaurant", label: "Restaurant", emoji: "🍽️", blurb: "Get more customers walking in." },
  { id: "clinic", label: "Clinic", emoji: "🏥", blurb: "Get more patient appointments." },
  { id: "retail", label: "Retail", emoji: "🛍️", blurb: "Get more foot traffic and sales." },
  { id: "hotel", label: "Hotel", emoji: "🏨", blurb: "Get more bookings." },
  { id: "realestate", label: "Real Estate", emoji: "🏠", blurb: "Get more property enquiries." },
  { id: "education", label: "Education", emoji: "🎓", blurb: "Get more student enrolments." },
  { id: "professional", label: "Professional Services", emoji: "💼", blurb: "Get more client enquiries." },
  { id: "manufacturing", label: "Manufacturing", emoji: "🏭", blurb: "Reach more B2B buyers." },
  { id: "startup", label: "Startup", emoji: "🚀", blurb: "Launch and grow your startup." },
  { id: "agency", label: "Agency", emoji: "🏢", blurb: "Grow your agency's client base." },
];
