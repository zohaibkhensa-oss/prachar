# PRACHAR Frontend V2 — Feature Audit & Build Plan

## V1 Feature Inventory (must all exist in V2)

### Public Routes (5)
- [ ] `/` — Landing page (hero, features, pricing, dashboard preview)
- [ ] `/audit` — Free visibility audit (URL → crawl → score → findings, SSE)
- [ ] `/login` — Email/password login
- [ ] `/register` — Name/email/password registration
- [ ] `/onboarding` — Conversational AI onboarding (13 phases)

### Auth Routes (3)
- [ ] `/auth/forgot-password`
- [ ] `/auth/reset-password`
- [ ] `/auth/resend-verification`

### App Routes — Core (8)
- [ ] `/app` — Dashboard (AI-first home with orb, greeting, KPIs, activity feed)
- [ ] `/app/campaigns` — Campaign list (status filtering)
- [ ] `/app/creative-studio` — 10 creative formats generation
- [ ] `/app/review` — Review queue
- [ ] `/app/review/[id]` — Campaign review detail (inline edit, AI suggestions, comments, versions)
- [ ] `/app/performance` — Performance stories list
- [ ] `/app/performance/[id]` — Narrative performance story
- [ ] `/app/settings` — 6-tab settings

### App Routes — Brand (5)
- [ ] `/app/brands` — Brand list
- [ ] `/app/brands/[id]` — Brand workspace
- [ ] `/app/brands/[id]/campaigns` — Campaign list with pause/resume/budget
- [ ] `/app/brands/[id]/campaigns/new` — 1-step campaign creation
- [ ] `/app/brands/[id]/channels` — Brand channel connections

### App Routes — Creative AI (5)
- [ ] `/app/creative` — Creative AI (ad variants, CTR predictions)
- [ ] `/app/design` — Design studio (templates, AI generator, brand kit)
- [ ] `/app/images` — AI image studio
- [ ] `/app/video` — Video studio
- [ ] `/app/repurpose` — Content repurposing (1 video → 11 assets)

### App Routes — Creator (2)
- [ ] `/app/youtube-plan` — YouTube video planning
- [ ] `/app/brands/[id]/content` — Content assets with diff view

### App Routes — Analytics & Reports (3)
- [ ] `/app/analytics` — Results metrics
- [ ] `/app/reports` — Cross-brand reports
- [ ] `/app/brands/[id]/report` — Brand weekly PDF reports

### App Routes — Channels & Connections (2)
- [ ] `/app/channels` — 16+ platform connections
- [ ] `/app/connections` — Regional channel connections

### App Routes — Marketing Tools (8)
- [ ] `/app/calendar` — Content calendar (month/week view)
- [ ] `/app/reviews` — Customer reviews management
- [ ] `/app/audience` — Audience builder
- [ ] `/app/advocacy` — Employee advocacy
- [ ] `/app/influencers` — Influencer marketing
- [ ] `/app/listening` — Social listening
- [ ] `/app/bio` — Link-in-bio builder
- [ ] `/app/shop` — E-commerce integration

### App Routes — Misc (3)
- [ ] `/app/marketplace` — Integration marketplace
- [ ] `/app/knowledge` — Knowledge base
- [ ] `/app/pricing` — Pricing & checkout

### Global Components (4)
- [ ] Sidebar navigation (collapsible, domain-based)
- [ ] Top bar (search ⌘K, notifications, avatar)
- [ ] VoiceAssistant (floating orb, wake word, Web Speech API, 30+ KB)
- [ ] ProactiveNotifications (PRACHAR AI messages, launch recommendations)
- [ ] CommandPalette (⌘K)

### Lib Files (16) — all must be ported
- [ ] `api.ts` — API client (apiGet, apiPost, apiPostStream)
- [ ] `auth.ts` — Token management, refresh, route protection
- [ ] `hooks.ts` — useBrands, useActiveBrand, useCampaignPlans
- [ ] `consult.ts` — Business onboarding types
- [ ] `creator.ts` — Creator intelligence types
- [ ] `creator-types.ts` — Creator/business presets
- [ ] `industries.ts` — 9 industry presets
- [ ] `review.ts` — Review workflow API client
- [ ] `performance.ts` — Performance intelligence API client
- [ ] `creative-studio.ts` — Creative Studio API client
- [ ] `proactive.ts` — Proactive notifications API client
- [ ] `unified-consult.ts` — Unified consult API client
- [ ] `schemas.ts` — Zod validation schemas
- [ ] `utils.ts` — cn() class merger
- [ ] `query.tsx` — React Query provider
- [ ] (new) `voice.ts` — Voice/orb state management

### API Endpoints (50+) — all must work
See full list in audit. Key groups:
- Auth: /auth/login, /auth/register, /auth/refresh, /auth/forgot-password, /auth/reset-password, /auth/resend-verification, /auth/verify-email
- Brands: /brands, /brands/{id}, /brands/{id}/campaigns, /brands/{id}/content, /brands/{id}/reports, /brands/audit
- Campaigns: /campaigns/{id}/pause, /campaigns/{id}/resume, /campaigns/{id}/budget, /campaign-brain/plans, /campaign-brain/full-campaign
- Consult: /consult, /consult/campaign, /consult/domains, /consult/nav/{domain}, /consult/tool/{toolId}
- Creator: /creator/consult, /creator/campaign, /creator/repurpose, /creator/youtube-plan
- Creative Studio: /creative-studio/generate, /creative-studio/generate/{formatId}, /creative-studio/regenerate-field, /creative-studio/{packageId}
- Review: /review/queue, /review/{id}/* (request-changes, approve, publish, suggestions, field, comments, versions)
- Performance: /performance/{campaignId}/* (summary, why, next, story)
- Proactive: /proactive/notifications, /chat/proactive, /proactive/{id}/launch
- Chat: /chat
- Billing: /billing/plans, /billing/checkout
- Connections: /connections, /connections/{channel}/oauth
- AI Gen: /api/video/generate, /api/video/generate-image
- Audits: /audits/{id}, /audits/{id}/events (SSE)

### Styling (must match v1)
- Dark-first palette: bg (#0B0F14), surface (#111827), card (#161B22), elevated (#1C2333)
- Accent: #FFD400 (yellow), #F97316 (orange)
- Fonts: Space Grotesk (display), Inter (body), IBM Plex Mono (mono)
- Glass effects: .glass, .glass-strong
- 3D cards: .card-3d
- Custom shadows: 3d-sm, 3d, 3d-lg, 3d-xl, glow variants
- Animations: fade-in, shimmer, glow-pulse, ai-thinking, float, rotate-3d, marquee

### Environment Variables
- `NEXT_PUBLIC_API_BASE` (default: http://localhost:8000)

---

## V2 Architecture (AI-First)

### Key Differences from V1
1. **AI orb is persistent** — floating, always visible, 4 states (idle/listening/thinking/speaking)
2. **Bottom dock** — Home, Campaigns, AI (center), Analytics, Profile
3. **Sidebar is collapsible** — collapsed by default (60px icons), expandable
4. **Dashboard is conversational** — AI greeting, overnight summary, action buttons
5. **Chat is not ChatGPT-style** — live components, streaming, generated checklists
6. **Multimodal input** — voice + text + images + video + documents
7. **Autonomous marketing** — overnight actions, one-click approval

### V2 File Structure
```
apps/web-v2/
  src/
    app/
      layout.tsx              # Root (QueryProvider, fonts, dark mode)
      page.tsx                # Landing
      globals.css             # Same theme as v1
      login/page.tsx
      register/page.tsx
      audit/page.tsx
      onboarding/page.tsx     # Redesigned with orb
      auth/
        forgot-password/page.tsx
        reset-password/page.tsx
        resend-verification/page.tsx
      app/
        layout.tsx            # Sidebar + dock + orb + topbar
        page.tsx              # AI-first dashboard
        campaigns/page.tsx
        creative-studio/page.tsx
        review/page.tsx
        review/[id]/page.tsx
        performance/page.tsx
        performance/[id]/page.tsx
        brands/page.tsx
        brands/[id]/page.tsx
        brands/[id]/campaigns/page.tsx
        brands/[id]/campaigns/new/page.tsx
        brands/[id]/channels/page.tsx
        brands/[id]/content/page.tsx
        brands/[id]/report/page.tsx
        channels/page.tsx
        connections/page.tsx
        calendar/page.tsx
        reviews/page.tsx
        settings/page.tsx
        analytics/page.tsx
        creative/page.tsx
        design/page.tsx
        images/page.tsx
        video/page.tsx
        repurpose/page.tsx
        youtube-plan/page.tsx
        reports/page.tsx
        audience/page.tsx
        advocacy/page.tsx
        influencers/page.tsx
        listening/page.tsx
        bio/page.tsx
        shop/page.tsx
        marketplace/page.tsx
        knowledge/page.tsx
        pricing/page.tsx
    components/
      AIOrb.tsx               # NEW — the floating orb (4 states)
      AIDock.tsx              # NEW — bottom dock with AI center
      Sidebar.tsx             # Collapsible sidebar
      TopBar.tsx              # Search, notifications, avatar
      VoiceAssistant.tsx      # Redesigned with orb
      ProactiveNotifications.tsx
      CommandPalette.tsx
      Logo.tsx
      ui/                     # Same UI components as v1
    lib/
      api.ts                  # Same as v1
      auth.ts                 # Same as v1
      hooks.ts                # Same as v1
      consult.ts              # Same as v1
      creator.ts              # Same as v1
      creator-types.ts        # Same as v1
      industries.ts           # Same as v1
      review.ts               # Same as v1
      performance.ts          # Same as v1
      creative-studio.ts      # Same as v1
      proactive.ts            # Same as v1
      unified-consult.ts      # Same as v1
      schemas.ts              # Same as v1
      utils.ts                # Same as v1
      query.tsx               # Same as v1
      voice.ts                # NEW — orb state management
  tailwind.config.ts          # Same as v1
  next.config.mjs             # Port 3001
  tsconfig.json               # Same as v1
  package.json                # Same deps as v1
```

### Build Phases
1. **Scaffold** — Next.js 15, Tailwind, deps, port 3001
2. **Foundation** — lib/ files (copy from v1), globals.css, layout, auth
3. **AI Shell** — AIOrb, AIDock, Sidebar, TopBar, VoiceAssistant
4. **Public routes** — Landing, login, register, audit, onboarding (with orb)
5. **Core app** — Dashboard (AI-first), campaigns, creative-studio, review, performance
6. **Brand routes** — Brands, brand detail, campaigns, channels, content, reports
7. **Creative AI** — Creative, design, images, video, repurpose, youtube-plan
8. **Marketing tools** — Calendar, reviews, audience, advocacy, influencers, listening, bio, shop
9. **Misc** — Settings, analytics, reports, channels, connections, marketplace, knowledge, pricing
10. **Audit** — Side-by-side comparison with v1, fix any missing features
