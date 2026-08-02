# CREATOR PRODUCT REVIEW

> **Decision gate:** If this document is weak, stop. Do not code.

## 1. Why Creators Need a Different Experience

A business owner and a YouTube creator are not the same person, and they are not trying to do the same thing. Confusing them would be the most expensive product mistake PRACHAR could make.

### The fundamental difference

A **business** sells a product or service. Content is *marketing* — a means to acquire customers. A biryani restaurant posts on Instagram to get people to walk in and eat.

A **creator** sells *content itself*. The content is the product. A YouTube creator's videos are what they sell — to audiences (for watch time) and to advertisers (for sponsorships). When a creator posts on Instagram, they're not marketing a separate product. They *are* the product.

This single difference cascades into everything:

- **Goals**: Business wants customers. Creator wants audience growth and monetisation.
- **Metrics**: Business tracks conversions and CPA. Creator tracks subscribers, watch time, retention, CTR.
- **Content cadence**: Business posts when promoting. Creator posts on a schedule their audience expects.
- **Platform strategy**: Business wants to be everywhere. Creator is native to 1-2 platforms and expands strategically.
- **Competitors**: Business competes with other businesses. Creator competes with other creators for the same audience's attention.
- **Monetisation**: Business sells products. Creator earns through ad revenue, sponsorships, merchandise, memberships, courses.
- **The "wow" moment**: For a business, it's "this AI gave me a marketing plan." For a creator, it's "this AI gave me a week of content I can actually post, plus repurposed my video into 10 other formats."

### What happens if we don't differentiate

If we serve creators with the business experience, here's what they'd see:
- "What business do you run?" → A creator doesn't run a business. They'd feel miscategorised.
- "Get more customers" → A creator doesn't have customers in the traditional sense. They have viewers.
- "Conversions, CPA, ROAS" → Meaningless to a creator. They care about watch time and CTR.
- "Promote your products" → A creator's product is their content. This framing doesn't work.
- "Budget slider" → Creators don't think in ad budgets. They think in content output.

The creator would leave within 30 seconds. They'd feel that PRACHAR doesn't understand them. That's the opposite of our mission.

---

## 2. How Creators Differ from Businesses

| Dimension | Business | Creator |
|-----------|----------|---------|
| **Primary goal** | Get more customers | Grow audience & monetise |
| **Content role** | Marketing for products | The product itself |
| **Platform strategy** | Be everywhere | Native to 1-2 platforms |
| **Key metrics** | Conversions, CPA, ROAS, revenue | Subscribers, views, watch time, retention, CTR, RPM |
| **Monetisation** | Sell products/services | Ad revenue, sponsorships, merch, memberships, courses |
| **Competitors** | Other businesses in same industry | Other creators in same niche |
| **Content cadence** | When promoting | Regular schedule (daily/weekly) audience expects |
| **Brand** | The business entity | The person (personal brand) |
| **Budget thinking** | "How much to spend on ads?" | "How much content to produce?" |
| **"Wow" moment** | "This AI understands my business" | "This AI understands my channel and gave me content I can post" |
| **What they want from PRACHAR** | Marketing campaigns | Content plans + repurposing + growth strategy |
| **Approval flow** | Approve ads before they go live | Approve content before it gets published |

---

## 3. Which Components Can Be Shared

| Component | Shared? | How |
|-----------|---------|-----|
| Authentication | ✅ Shared | Same login/register, same JWT, same tenant model |
| Conversation interface | ✅ Shared | Same chat UI, same BRO personality, same animated indicators |
| Conversation memory | ✅ Shared | Same `brand_graph` JSONB storage, same context persistence |
| Dashboard layout | ✅ Shared | Same sidebar, same top bar, same responsive structure |
| AIGateway | ✅ Shared | Same LLM orchestration, same tiering, same caching |
| Brand model | ✅ Shared (extended) | Add `customer_type` field (business/creator) |
| Campaign plan storage | ✅ Shared | Same `CampaignPlanRecord` table |
| Approval flow | ✅ Shared | Same Approve/Regenerate/Back pattern |
| Card/timeline UI components | ✅ Shared | Same visual components (cards, timelines, badges), different content |
| Onboarding conversation flow | ✅ Shared | Same "type → analyse → cards → plan → preview → approve" flow |
| Audit logging | ✅ Shared | Same `AuditEvent` system |

---

## 4. Which Components Must Diverge

| Component | Diverges? | Why |
|-----------|-----------|-----|
| Onboarding question | ✅ Diverges | "Tell me who you are" → Business Growth vs Creator Growth paths |
| Category options | ✅ Diverges | Business: Restaurant, Clinic, Retail... Creator: YouTube Creator, Instagram Creator, Podcaster... |
| Intelligence layer | ✅ Diverges | Creator Intelligence = new orchestration with creator-specific prompts. NOT a copy of Marketing Intelligence. Uses same AIGateway. |
| Analysis output | ✅ Diverges | Creator Profile (niche, platforms, upload frequency, content pillars, monetisation, growth stage) vs Business Profile (industry, products, services, audience) |
| Growth opportunities | ✅ Diverges | Creator: content gaps, collaboration opportunities, monetisation. Business: customer acquisition, channel expansion. |
| 30-day plan | ✅ Diverges | Creator: videos, shorts, reels, community posts, collaborations, SEO, newsletter, live sessions. Business: objectives, content, offers, channels. |
| Dashboard KPIs | ✅ Diverges | Creator: subscribers, views, watch time, retention, CTR, uploads, revenue, brand deals. Business: customers, revenue, CPA, ROAS. |
| Content repurposing | ✅ Creator-only | YouTube video → 11 asset types. Not applicable to businesses. |
| YouTube planning | ✅ Creator-only | Titles, thumbnails, hooks, retention, SEO, tags, chapters. Not applicable to businesses. |
| Campaign preview | ✅ Diverges | Creator: content plan + repurposing preview. Business: ads + posts + budget preview. |
| Sidebar labels | ✅ Diverges | Creator: "My Channel", "Content", "Audience". Business: "My Brand", "Campaigns", "Results". |

---

## 5. Expected UX Changes

### Onboarding (first screen)
- **Before**: "What business do you run?" → industry grid
- **After**: "Tell me who you are." → Two paths: **Business Growth** / **Creator Growth**
  - Business path: Restaurant, Clinic, Retail, Hotel, Real Estate, Education, Professional Services, Manufacturing, Startup, Agency
  - Creator path: YouTube Creator, Instagram Creator, Podcaster, Influencer, Gaming Creator, Educator, Media Company, Production Studio, Musician, Personal Brand
- After selection, both paths enter the same conversation flow (different prompts)

### Conversation
- **Business**: "Tell me about your business." → Business Intelligence → Marketing plan
- **Creator**: "Tell me about your channel." → Creator Intelligence → Content plan
- Same BRO personality, same chat UI, same card-based insights

### Dashboard
- **Business dashboard**: Unchanged (per instructions: "Do NOT change. Only improve where shared.")
- **Creator dashboard**: New KPIs (subscribers, views, watch time, retention, CTR, uploads, revenue, brand deals, trending opportunities, content pipeline)
- **Common dashboard elements**: Today's recommended action, upcoming tasks, drafts, approvals, performance summary

### Content Repurposing (creator-only)
- New page: paste a YouTube URL → get 11 repurposed assets (Shorts, Reels, LinkedIn post, X thread, blog, newsletter, email, community post, podcast summary, sponsor pitch)
- Each asset is editable

### YouTube Planning (creator-only)
- For each planned video: title options, thumbnail concepts, opening hook, retention improvements, description, SEO keywords, tags, chapters, pinned comment, community post, end screen suggestions

---

## 6. Risks

### Risk 1: Scope creep
**What**: Content repurposing (11 asset types) and YouTube planning (10 elements per video) are substantial features.
**Mitigation**: Build them as single LLM calls with well-structured prompts. No per-asset infrastructure. Each asset is a text field in the response.

### Risk 2: Code duplication
**What**: Risk of duplicating the Marketing Intelligence Engine for creators.
**Mitigation**: Creator Intelligence is NOT a new engine. It's a new orchestration layer (`/creator` router) that uses the AIGateway directly with creator-specific prompts. The Marketing Intelligence Engine remains unchanged. This is the same pattern as `/consult` — an orchestration layer, not an engine.

### Risk 3: Shallow creator analysis
**What**: Creator-specific prompts might produce generic analysis ("post more videos, engage with your audience").
**Mitigation**: Prompts are structured to extract specific, actionable insights: niche, platforms, upload frequency, content pillars, competitors, monetisation stage, growth stage. The output is specific to the creator's description.

### Risk 4: UI confusion
**What**: Two different dashboards could confuse users who switch between business and creator modes.
**Mitigation**: The `customer_type` is set at onboarding and stored on the Brand. The dashboard renders based on `customer_type`. Users don't switch — they are one or the other. (A user could have both a business brand and a creator brand, but each brand has its own type.)

### Risk 5: No platform API integration
**What**: We can't pull real YouTube/Instagram analytics without OAuth integration.
**Mitigation**: This sprint relies on the user's description + LLM analysis (same as the business sprint). Platform API integration is a future sprint. The value is in the content plan and repurposing, not in analytics dashboards.

### Risk 6: Migration of existing users
**What**: Existing brands don't have a `customer_type`.
**Mitigation**: Default `customer_type` to "business" for all existing brands. No migration needed — just a default.

### Risk 7: Content repurposing quality
**What**: Generating 11 asset types from one video description might produce low-quality output.
**Mitigation**: The prompt is structured per asset type with specific requirements (e.g. "Shorts: 30-60 second script with hook in first 3 seconds"). The user can edit each asset. We're not trying to be perfect — we're trying to give the creator a strong starting point.

---

## 7. Architecture Impact

### What changes

1. **Brand model** — Add `customer_type` column (String, default "business"). Values: "business" | "creator". This is a 1-line addition to the model + a migration.

2. **New router: `/creator`** — 4 endpoints:
   - `POST /creator/consult` — Creator Intelligence: free-text → Creator Profile + growth opportunities + 30-day plan
   - `POST /creator/repurpose` — Content repurposing: YouTube video description → 11 asset types
   - `POST /creator/youtube-plan` — YouTube planning: video concept → title options, thumbnail, hook, retention, SEO, tags, chapters, pinned comment, community post, end screen
   - `POST /creator/campaign` — Creator campaign: brand_id → content plan + publishing schedule (reuses CampaignBrain.generate_campaign() with creator-specific goal)

3. **Frontend onboarding** — Add customer type selection before the conversation. The conversation flow is shared, but the prompts and analysis differ based on customer type.

4. **Frontend dashboard** — Render different KPIs based on `customer_type`. The dashboard layout is shared; the content diverges.

5. **Frontend new pages** (creator-only):
   - `/app/repurpose` — Content repurposing tool
   - `/app/youtube-plan` — YouTube video planning tool

### What does NOT change

- Marketing Intelligence Engine — unchanged
- CampaignBrain — reused (creator campaigns use `generate_campaign()` with creator-specific goals)
- AIGateway — unchanged
- Authentication — unchanged
- Conversation memory — reused (same `brand_graph` storage)
- Dashboard framework — reused (same layout, sidebar, top bar)
- Audit logging — unchanged
- Database schema (except 1 new column on Brand)

### Architecture diagram

```
                    Onboarding
                       │
              "Tell me who you are"
                    /     \
           Business       Creator
              │              │
         /consult        /creator/consult
         (existing)      (new orchestration)
              │              │
         CampaignBrain    AIGateway
         .analyse()      (creator prompts)
              │              │
         Business         Creator
         understanding    understanding
              │              │
         /consult/       /creator/
         campaign        campaign
              │              │
         CampaignBrain   CampaignBrain
         .generate_      .generate_
         campaign()      campaign()
              │              │
         Business         Creator
         campaign         campaign
         preview          preview
```

The key insight: **Creator Intelligence is an orchestration layer, not a new engine.** It uses the AIGateway directly with creator-specific prompts, just as `/consult` uses the AIGateway with business-specific prompts. The CampaignBrain is reused for campaign generation in both paths.

---

## 8. Quality Gates (per feature)

### Feature: Creator Onboarding
1. **What user problem?** Creators don't identify as businesses. Asking "What business do you run?" alienates them.
2. **Clicks removed?** 0 (it's a new path, not a removal). But it prevents creators from abandoning.
3. **How will the customer notice?** They see "YouTube Creator" as an option and feel recognised.
4. **Demonstrable in 60s?** Yes — pick "YouTube Creator" → describe channel → see creator-specific analysis.
**Verdict: BUILD**

### Feature: Creator Intelligence (analysis)
1. **What user problem?** Creators need to understand their niche, audience, content gaps, monetisation opportunities.
2. **Clicks removed?** Replaces hours of manual niche research with 1 message.
3. **How will the customer notice?** They see "Your content niche: tech reviews for Indian audiences" and feel understood.
4. **Demonstrable in 60s?** Yes — describe channel → see Creator Profile cards.
**Verdict: BUILD**

### Feature: 30-Day Creator Growth Plan
1. **What user problem?** Creators struggle with "what should I post this week?"
2. **Clicks removed?** Replaces hours of content planning with 1 click.
3. **How will the customer notice?** They see "Week 1: Post 2 long-form reviews + 3 shorts" — specific, actionable.
4. **Demonstrable in 60s?** Yes — after analysis, click "See 30-day plan" → see weekly breakdown.
**Verdict: BUILD**

### Feature: Content Repurposing
1. **What user problem?** Creators spend hours repurposing one video into shorts, reels, posts.
2. **Clicks removed?** Replaces ~3 hours of manual repurposing with 1 paste + 1 click.
3. **How will the customer notice?** They paste a video description and get 11 ready-to-edit assets.
4. **Demonstrable in 60s?** Yes — paste URL/description → see 11 assets.
**Verdict: BUILD**

### Feature: YouTube Planning
1. **What user problem?** Creators struggle with titles, thumbnails, SEO for each video.
2. **Clicks removed?** Replaces 30 min of per-video optimisation with 1 click.
3. **How will the customer notice?** They see "Title: 'I tested the ₹500 phone — here's what happened'" with SEO keywords and chapters.
4. **Demonstrable in 60s?** Yes — enter video concept → see full YouTube plan.
**Verdict: BUILD**

### Feature: Creator Dashboard KPIs
1. **What user problem?** Business KPIs (conversions, CPA) are meaningless to creators.
2. **Clicks removed?** 0 — it's a relevance fix, not a click reduction.
3. **How will the customer notice?** They see "Subscribers: 12.4K, Watch time: 840 hrs" instead of "Conversions: 127".
4. **Demonstrable in 60s?** Yes — open dashboard → see creator KPIs.
**Verdict: BUILD**

### Feature: Common Dashboard (Today, Recommended Action, Upcoming Tasks, Drafts, Approvals, Performance)
1. **What user problem?** Both business and creator users need to know "what should I do today?"
2. **Clicks removed?** Replaces navigating to 5 different pages with 1 dashboard view.
3. **How will the customer notice?** They open the dashboard and immediately see today's action.
4. **Demonstrable in 60s?** Yes — open dashboard → see recommended action.
**Verdict: BUILD**

---

## 9. Decision

This document is not weak. The creator segment is fundamentally different from the business segment, the shared components are clearly identified, the divergent components are justified, and every feature passes the quality gates.

**Proceeding with implementation.**

The build order:
1. Backend: Add `customer_type` to Brand + migration
2. Backend: Create `/creator` router (4 endpoints)
3. Frontend: Update onboarding with customer type selection
4. Frontend: Build creator conversation flow (reuses onboarding UI)
5. Frontend: Build creator dashboard with creator KPIs
6. Frontend: Build content repurposing page
7. Frontend: Build YouTube planning page
8. Frontend: Add common dashboard elements (Today, Recommended Action, etc.)
9. Tests + UX report
