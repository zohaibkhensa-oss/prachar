# UNIFIED INTELLIGENCE SPRINT — Migration Guide & Founder Demo

## Migration Guide

### For backend developers

#### Adding a new domain (e.g. Law Firm, Hotel, Education)

**Before this sprint:** You would create a new router file (`routers/lawfirm.py`), copy-paste the orchestration from `consult.py`, write new prompts, register the router in `main.py`, and add new frontend pages. ~500 lines of duplicated code per domain.

**After this sprint:** You create ONE folder + ONE file + ONE registration line.

1. **Create the pack folder:**
   ```
   packages/shared/prachar_shared/domain_packs/lawfirm/
       __init__.py
       pack.py
   ```

2. **Implement the pack** (`pack.py`):
   ```python
   from ..base import BaseDomainPack, SubtypePreset, KpiCardSpec, ...

   class LawFirmPack(BaseDomainPack):
       id = "lawfirm"
       label = "Law Firm Growth"
       customer_type = "business"
       emoji = "⚖️"
       subtypes = [SubtypePreset("general", "General Practice", "⚖️", "Get more clients.", "lawfirm")]
       extraction_schema = {...}
       extraction_prompt = 'Extract info from: "{message}"'
       kpi_cards = [KpiCardSpec("clients", "Clients", "Users", "")]
       opportunity_prompt = "List 5 growth opportunities."
       week_schema = {...}
       week_prompt = "Create a 4-week plan."
       campaign_template = "Client Acquisition Campaign"
       campaign_prompt = "Create a campaign for {business_name}."
       recommendations_prompt = "Be specific."
       dashboard_widgets = [WidgetSpec("kpi_grid", "Your firm")]
       quick_actions = []
       brand_graph_schema = {...}
       memory_namespace = "business.lawfirm"
       conversation_role = "marketing strategist"
       forbidden_jargon = ["ROAS", "CPA"]
       greeting_template = "Tell me about your firm."
       nav_sections = [NavSectionSpec("Main", [NavItemSpec("Home", "/app")])]
       tools = []
   ```

3. **Register it** in `packages/shared/prachar_shared/domain_packs/base.py`:
   ```python
   def register_all() -> None:
       from .business.pack import BusinessPack
       from .creator.pack import CreatorPack
       from .restaurant.pack import RestaurantPack
       from .clinic.pack import ClinicPack
       from .lawfirm.pack import LawFirmPack  # ← ONE line

       reg = get_registry()
       reg.clear()
       reg.register(BusinessPack())
       reg.register(CreatorPack())
       reg.register(RestaurantPack())
       reg.register(ClinicPack())
       reg.register(LawFirmPack())  # ← ONE line
   ```

4. **Done.** Zero router changes. Zero dashboard changes. Zero pipeline changes.

The new domain automatically:
- Appears in `GET /consult/domains` (onboarding UI)
- Has its config available at `GET /consult/nav/lawfirm` (sidebar, KPIs, widgets)
- Works with `POST /consult` (universal consult)
- Works with `POST /consult/campaign` (universal campaign generation)
- Works with `POST /consult/tool/{tool_id}` (if it has tools)
- Uses `CampaignBrain.analyse()` and `CampaignBrain.generate_campaign()` (always)
- Persists to `CampaignPlanRecord` (shared)
- Writes audit logs (shared)
- Stores memory in `brand_graph` (shared, domain-tagged)

**Time to add a new domain: under one day.** The LawFirmPack test in `test_architecture.py` proves this — a new pack is created inline and registered in 3 lines.

#### Migrating from the legacy routers

The legacy `/consult` (business) and `/creator/*` (creator) routers are **still registered** for backward compatibility. They have NOT been removed. Existing API consumers continue to work.

**To migrate to the unified router:**

| Old endpoint | New endpoint |
|--------------|--------------|
| `POST /consult` (business) | `POST /consult` with `domain="business"` |
| `POST /consult/campaign` (business) | `POST /consult/campaign` with `domain="business"` |
| `POST /creator/consult` | `POST /consult` with `domain="creator"` |
| `POST /creator/campaign` | `POST /consult/campaign` with `domain="creator"` |
| `POST /creator/repurpose` | `POST /consult/tool/repurpose` with `domain="creator"` |
| `POST /creator/youtube-plan` | `POST /consult/tool/youtube_plan` with `domain="creator"` |

The response shapes are unified but backward-compatible:
- `business` field → `understanding` field (contains the same data)
- `growth_opportunities` field → `opportunities` field
- `plan` field → `plan` field (same)
- `extracted` field → `extracted` field (same)
- `profile` + `position` (creator) → `understanding` field (contains both)

**Migration timeline:**
1. **Now:** Both old and new endpoints work. Frontend can migrate at its own pace.
2. **Next sprint:** Frontend migrates to the unified endpoints.
3. **Future:** Legacy routers are removed once all consumers have migrated.

### For frontend developers

#### Using the unified API client

```typescript
import { unifiedConsultApi } from "@/lib/unified-consult";

// List all domains (for onboarding type-selection screen)
const domains = await unifiedConsultApi.domains();

// Get domain config (nav, KPIs, widgets, tools) for sidebar + dashboard
const config = await unifiedConsultApi.config("creator");

// Universal consult (any domain)
const result = await unifiedConsultApi.consult({
  message: "I run a biryani restaurant in Hyderabad.",
  domain: "business",
  subtype_id: "restaurant",
});

// Universal campaign generation (any domain)
const campaign = await unifiedConsultApi.campaign({
  brand_id: brand.id,
  goal: "get more customers",
  budget: "₹15,000",
  domain: "business",
});

// Domain-specific tool (e.g. creator's repurpose)
const repurposed = await unifiedConsultApi.tool("repurpose", {
  domain: "creator",
  inputs: { video_title: "...", video_description: "...", niche: "tech" },
});
```

#### Using the shared presentation components

```typescript
import {
  UnderstandingCards,
  OpportunityCards,
  PlanTimeline,
  CampaignDeck,
  getPresentationConfig,
} from "@/components/consult/SharedPresentation";

const config = getPresentationConfig("creator");

<UnderstandingCards understanding={result.understanding} config={config} onContinue={...} />
<OpportunityCards opportunities={result.opportunities} onContinue={...} />
<PlanTimeline weeks={result.plan} config={config} onContinue={...} />
<CampaignDeck preview={campaign.preview} domain="creator" onApprove={...} onRegenerate={...} />
```

#### Using the unified dashboard shell

```typescript
import { DashboardShell } from "@/components/consult/DashboardShell";
import { useQuery } from "@tanstack/react-query";
import { unifiedConsultApi } from "@/lib/unified-consult";

const { data: config } = useQuery({
  queryKey: ["domain-config", domain],
  queryFn: () => unifiedConsultApi.config(domain),
});

<DashboardShell brand={brand} plans={plans} config={config} />
```

The shell renders greeting, today's action, and domain-supplied widgets. Adding a new domain = supplying a new `DomainConfig` from the backend. No shell changes.

#### Using the domain-driven sidebar

The sidebar (`apps/web/src/app/app/layout.tsx`) now fetches nav from `GET /consult/nav/{domain}`. Adding a new domain automatically makes its nav available — no frontend hard-coding.

Fallback nav arrays (`BUSINESS_NAV_FALLBACK`, `CREATOR_NAV_FALLBACK`) are kept for resilience if the backend is unavailable.

### For existing brands (database migration)

**No migration required.** All existing brands have `customer_type='business'` (the default from migration `0004_customer_type`). They map to the BusinessPack automatically.

The `brand_graph` JSONB field is backward-compatible:
- Existing business brands have `{location, products, services, audience, goals, ...}`
- New consults add `{domain: "business", memory_namespace: "business"}` to the graph
- No data is lost or transformed

---

## Founder Demo

### The architectural guarantee

> To add a new domain, the developer only implements a Domain Pack. No changes are required in Campaign Brain, Dashboard, Conversation, Memory, Core AI, Authentication, or Infrastructure.

### Demo 1: Register a Restaurant

1. User lands on `/onboarding`
2. Sees "Tell me who you are" → picks "Business Growth"
3. Sees business subtypes → picks "Restaurant" 🍽️
4. Types: *"I run a biryani restaurant in Hyderabad. We do catering too. Want more weekday customers."*
5. `POST /consult` with `{domain: "business", subtype_id: "restaurant", message: "..."}`
6. The ConsultEngine:
   - Loads BusinessPack from registry
   - Extracts: `{business_name: "", industry: "restaurant", location: "Hyderabad", products: ["biryani"], services: ["catering"], ...}`
   - Creates Brand with `customer_type="business"`, `category="restaurant"`
   - Runs `CampaignBrain.analyse()` (business + audience + competitor engines)
   - Generates understanding (strengths, weaknesses, customers, competitors)
   - Generates 5 growth opportunities (e.g. "Launch weekday lunch thali")
   - Generates 30-day plan (4 weeks: content, offers, channels, KPIs)
   - Returns unified `ConsultResponse`
7. User sees understanding cards, opportunity cards, plan timeline
8. User clicks "Build my campaign"
9. `POST /consult/campaign` with `{domain: "business", brand_id: ..., goal: "get more customers", budget: "₹15,000"}`
10. The ConsultEngine:
    - Runs `CampaignBrain.generate_campaign()` (all 9 engines)
    - Generates campaign preview using BusinessPack campaign_prompt
    - Persists to `CampaignPlanRecord` with `campaign.template = "Promotion Campaign"`
11. User sees campaign deck (title, hero image, video concept, post ideas, reach, enquiries, budget, why, confidence, risks, alternative)
12. User clicks "Approve & start"
13. Lands on dashboard → sees restaurant KPIs (covers, AOV, repeats, reviews), today's action, quick actions

**Pipeline used:** Universal Consult Engine + BusinessPack. Same as today.

### Demo 2: Register a Creator

1. User lands on `/onboarding`
2. Sees "Tell me who you are" → picks "Creator Growth" 🎨
3. Sees creator subtypes → picks "YouTube Creator" 📹
4. Types: *"I make tech review videos on YouTube, 8K subscribers, post 1 video/week, want to grow to 50K."*
5. `POST /consult` with `{domain: "creator", subtype_id: "youtube_creator", message: "..."}`
6. The ConsultEngine:
   - Loads CreatorPack from registry
   - Extracts: `{niche: "tech reviews", platforms: ["YouTube"], upload_frequency: "1 video/week", ...}`
   - Creates Brand with `customer_type="creator"`, `category="youtube"`
   - Runs `CampaignBrain.analyse()` (NOW creators benefit from the Marketing Intelligence Engine — this was the bug fix)
   - Generates creator profile (niche, platforms, growth stage, monetisation)
   - Generates position (strengths, weaknesses, growth opportunities, content gaps)
   - Generates 30-day content plan (4 weeks: videos, shorts, community posts, collaborations, SEO, newsletter, live sessions, KPIs)
   - Returns unified `ConsultResponse`
7. User sees creator understanding cards, opportunity cards, content plan timeline
8. User clicks "Build my campaign"
9. `POST /consult/campaign` with `{domain: "creator", brand_id: ..., goal: "grow the channel", budget: "₹5,000"}`
10. The ConsultEngine:
    - Runs `CampaignBrain.generate_campaign()` (all 9 engines — creators now get the full brain)
    - Generates content campaign preview using CreatorPack campaign_prompt
    - Persists to `CampaignPlanRecord` with `campaign.template = "Content Campaign"`
11. User sees campaign deck (title, publishing schedule, expected growth, confidence)
12. User clicks "Approve & start"
13. Lands on dashboard → sees creator KPIs (subscribers, views, watch time, retention, CTR, uploads, revenue, brand deals), today's action, quick actions (Repurpose video, Plan YouTube video, Build content campaign)

**Pipeline used:** Universal Consult Engine + CreatorPack. **Same pipeline as Demo 1.** Only the Domain Pack changed.

### Demo 3: Register a Clinic

1. User lands on `/onboarding`
2. Sees "Tell me who you are" → picks "Business Growth"
3. Sees business subtypes → picks "Clinic" 🏥
4. Types: *"I run a dental clinic in Mumbai. We do checkups, root canals, teeth whitening. Want more patient appointments."*
5. `POST /consult` with `{domain: "business", subtype_id: "clinic", message: "..."}`
6. The ConsultEngine:
   - Loads BusinessPack from registry (clinic is a business subtype)
   - Extracts: `{business_name: "", industry: "clinic", location: "Mumbai", services: ["dental checkups", "root canal", "teeth whitening"], ...}`
   - Creates Brand with `customer_type="business"`, `category="clinic"`
   - Runs `CampaignBrain.analyse()`
   - Generates understanding (strengths, weaknesses, patients, competitors)
   - Generates 5 growth opportunities (e.g. "Launch free first consultation")
   - Generates 30-day plan (4 weeks: content, offers, channels, KPIs)
   - Returns unified `ConsultResponse`

**Alternatively**, if the clinic wants healthcare-specific KPIs (appointments, new patients, no-shows) and a "Patient Acquisition Campaign" template, they can use the dedicated ClinicPack:
5'. `POST /consult` with `{domain: "clinic", subtype_id: "dental", message: "..."}`
6'. The ConsultEngine loads ClinicPack → healthcare-specific KPIs, "Patient Acquisition Campaign" template, compliance-aware prompts (no medical claims).

**Pipeline used:** Universal Consult Engine + BusinessPack (or ClinicPack). **Same pipeline as Demos 1 and 2.** Only the Domain Pack changed.

### The point

All three demos follow the **SAME pipeline**:
```
POST /consult → ConsultEngine.consult(pack_id, message, ...)
    → extract → create brand → CampaignBrain.analyse() → generate understanding → update memory
POST /consult/campaign → ConsultEngine.campaign(pack_id, brand_id, goal, budget)
    → CampaignBrain.generate_campaign() → generate preview → persist
```

Only the Domain Pack changes. Everything else (router, engine, persistence, audit, memory, auth, dashboard shell, presentation components) is identical.

---

## Quality gates (per the review)

| Question | Answer |
|----------|--------|
| What duplication was removed? | `_extract_json` (2 copies → shared), brand creation (2 copies → shared), campaign persistence (2 copies → shared), prompt templates (moved to packs), dashboard components (4 pairs → shared), sidebar nav (2 hard-coded arrays → pack-driven) |
| How many files became shared? | 8 new shared files (base.py, 4 packs, consult_engine.py, SharedPresentation.tsx, DashboardShell.tsx) replace ~12 duplicated files/sections |
| Can a new domain be added in under one day? | **Yes.** The LawFirmPack test creates a new pack in 3 lines. The RestaurantPack and ClinicPack were each implemented in one file. |
| Can it be demonstrated in under 60 seconds? | **Yes.** The founder demo runs through the same `/consult` endpoint for all three domains. |

---

## Test results

- **Architecture tests:** 41 pass ✅ (no duplication, no circular deps, plugin isolation)
- **Unified consult router tests:** 20 pass ✅ (domains, nav, auth, validation, founder demo)
- **Existing API tests:** 48 pass ✅ (no regressions)
- **Frontend typecheck:** 0 errors ✅
- **Frontend build:** 33 pages compile ✅

**Total: 109 backend tests pass. 0 regressions.**

---

## What's next (future sprints)

1. **Migrate frontend onboarding to unified endpoints** — replace `consultApi` and `creatorApi` calls with `unifiedConsultApi`
2. **Remove legacy routers** — once all consumers have migrated, remove `routers/consult.py` and `routers/creator.py`
3. **Add more domain packs** — Hotel, Education, Real Estate, Retail, Agency, Fitness, Manufacturing, Law Firm, Architecture Firm, Travel Agency, Fitness Coach
4. **Domain-specific tools** — restaurants could get a "Menu Engineer" tool, clinics a "Patient Education Content" tool, etc. All via `ToolSpec` in the pack.
5. **Platform API integration per domain** — YouTube/Instagram for creators, Google Business Profile for restaurants, Practo for clinics. Each pack can declare which platform connections it needs.
6. **Domain-specific Agency Council directors** — the Compliance director could have healthcare-specific rules for clinics, food safety rules for restaurants.
