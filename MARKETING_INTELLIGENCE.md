# CURV AI — Marketing Intelligence Engine

**The brain of PRACHAR. Thinks before it creates.**

This module transforms PRACHAR from an AI content generation platform into an
AI Communications Company. Every campaign begins with strategy — never with
creative assets. The engine reasons like a senior advertising agency
(McKinsey + WPP + OpenAI + Apple).

---

## The Non-Negotiable Rule

BRO never starts with:
- Generate Image
- Generate Video
- Generate Caption

BRO always starts with:
1. Understand Business
2. Understand Goal
3. Understand Audience
4. Understand Competitors
5. Understand Budget
6. Understand Brand

Then formulate a communication strategy. **Only then** generate assets.

---

## Architecture

```
BRO (chat)
  ↓
CampaignBrain (orchestrator)
  ↓
┌─────────────────────────────────────────────────────────┐
│  1. Business Intelligence Engine                        │
│  2. Audience Intelligence Engine                         │
│  3. Competitor Intelligence Engine                       │
│  4. Marketing Objective Engine                           │
│  5. Campaign Strategy Engine                             │
│  6. Creative Direction Engine                            │
│  7. Media Planning Engine                                │
│  8. Budget Intelligence Engine                           │
│  9. Execution Planner                                    │
│  10. Learning Engine                                     │
└─────────────────────────────────────────────────────────┘
  ↓
Creative Orchestrator → AI Workers → Publishing → Analytics
  ↓
Continuous Learning (updates Business Memory)
```

---

## Module Location

```
packages/shared/prachar_shared/marketing_intelligence/
├── __init__.py          # Public API exports
├── base.py              # IntelligenceEngine base class, EngineOutput, Recommendation
├── business_engine.py   # Business Intelligence Engine
├── audience_engine.py   # Audience Intelligence Engine
├── competitor_engine.py # Competitor Intelligence Engine
├── objective_engine.py  # Marketing Objective Engine
├── strategy_engine.py   # Campaign Strategy Engine
├── creative_engine.py   # Creative Direction Engine
├── media_engine.py      # Media Planning Engine
├── budget_engine.py     # Budget Intelligence Engine
├── execution_engine.py  # Execution Planner
├── learning_engine.py   # Learning Engine
├── memory.py            # Business Memory store
└── brain.py             # CampaignBrain orchestrator + FullCampaign
```

---

## The 10 Engines

### 1. Business Intelligence Engine
Understands the business: industry, business model, products, services, USP,
pricing, customer type, business maturity, market position, seasonality,
SWOT, regulatory considerations.

**Output:** `BusinessProfile` (18 fields)

### 2. Audience Intelligence Engine
Defines primary and secondary audiences: demographics, psychographics,
buying intent, pain points, language, platforms, content preferences,
buying journey mapping.

**Output:** `AudienceProfile` (10 fields)

### 3. Competitor Intelligence Engine
Analyzes top competitors: market messaging, creative positioning, offer
strategy, pricing, communication style, market gaps, SWOT comparison,
positioning map.

**Output:** `CompetitorProfile` (6 fields)

### 4. Marketing Objective Engine
Converts user requests into measurable objectives: increase leads, increase
sales, launch product, increase footfall, build awareness, customer
retention, recruitment, investor outreach. Each objective has SMART KPIs.

**Output:** `MarketingObjective` (7 fields)

### 5. Campaign Strategy Engine
Creates complete campaign strategy: core message, communication theme,
emotional angle, marketing funnel, customer journey, content pillars,
media mix, publishing frequency, campaign duration, budget allocation,
success metrics.

**Output:** `CampaignStrategy` (12 fields)

### 6. Creative Direction Engine
**The "think before create" gate.** Before any image/video is generated,
determines: visual style, mood, colour palette (with hex codes),
typography, photography style, motion style, brand consistency rules,
creative references, do/don't lists, image/video prompt templates.

**Output:** `CreativeDirection` (12 fields)

### 7. Media Planning Engine
Determines optimal media mix across Instagram, Facebook, LinkedIn, Google,
YouTube, WhatsApp, Outdoor, Print, TV, Radio, Cinema, Email, SMS — based
on audience, budget, goal, and industry.

**Output:** `MediaPlan` (5 fields)

### 8. Budget Intelligence Engine
Estimates: creative cost, AI cost, advertising cost, agency cost, total
cost, ROI projection, CAC estimate, expected reach/engagement/conversion,
break-even analysis.

**Output:** `BudgetEstimate` (12 fields)

### 9. Execution Planner
Breaks campaign into executable tasks: strategy → creative → images →
videos → copy → landing page → approval → publishing → monitoring →
optimization. Includes timeline, dependencies, approval checklist,
AI asset requirements, risk mitigation.

**Output:** `ExecutionPlan` (7 fields)

### 10. Learning Engine
After campaign completion: collects CTR, reach, impressions, comments,
shares, conversions, cost, ROI. Generates learning report. Updates
Business Memory. Future campaigns improve automatically.

**Output:** `LearningReport` (10 fields)

---

## Business Memory

Every workspace stores accumulated knowledge that persists across campaigns:

- Brand identity: industry, voice, tone, fonts, logo, colours
- Campaign history: successful and failed campaigns
- Preferences: preferred platforms, budget preference, language preference
- Seasonal events
- **Best practices** (from Learning Engine — capped at 50)
- Audience insights (capped at 30)
- Creative insights (capped at 30)
- Channel insights (capped at 20)
- Metadata: last campaign, total campaigns, average ROI

The Learning Engine updates this memory after every campaign. Future
campaigns read this memory as context, creating a continuous learning loop.

**Storage:** `business_memories` table (JSONB column, one row per brand)

---

## Campaign Brain (Orchestrator)

The `CampaignBrain` class is the single entry point for full campaign
generation. It chains all 9 engines in dependency order:

```
1. Business Intelligence (no deps)
2. Audience Intelligence (needs business)
3. Competitor Intelligence (needs business)
4. Marketing Objective (needs business + audience)
5. Campaign Strategy (needs business + audience + competitor + objective)
6. Creative Direction (needs strategy + audience)
7. Media Plan (needs strategy + audience + objective)
8. Budget Intelligence (needs strategy + media plan)
9. Execution Plan (needs strategy + creative + media + budget)
```

After all 9 engines run, the brain generates:
- **Executive Summary** — concise overview of the entire campaign
- **Risk Assessment** — aggregated risks from all engine recommendations
- **Overall Confidence** — average of all engine confidences
- **Total Cost/Latency/Tokens** — aggregated metadata

**Output:** `FullCampaign` (all 9 analyses + metadata + executive summary)

---

## BRO Integration

BRO (the chat assistant) never directly answers marketing questions.
When a user asks a strategic question (detected via keyword matching)
AND provides a `brand_id`, BRO:

1. Consults the Campaign Brain (runs business + audience + objective + strategy)
2. Gets structured strategy back
3. Converts the structured strategy into conversational language via LLM
4. Returns the conversational response with `campaign_brain_used: true`

This ensures every strategic answer is grounded in actual analysis, not
hallucinated. The `campaign_brain_used` field lets the frontend indicate
when BRO consulted the brain.

---

## REST API

All endpoints require JWT auth. All are tenant-scoped (RLS).

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/campaign-brain/analyse` | Business + audience + competitor analysis |
| POST | `/campaign-brain/strategy` | Marketing objective + campaign strategy |
| POST | `/campaign-brain/creative-direction` | Creative direction |
| POST | `/campaign-brain/media-plan` | Media plan |
| POST | `/campaign-brain/execution-plan` | Execution plan |
| POST | `/campaign-brain/full-campaign` | Complete campaign (all 9 engines) |
| GET | `/campaign-brain/plans` | List saved campaign plans |
| GET | `/campaign-brain/plans/{id}` | Get a saved campaign plan |
| POST | `/campaign-brain/{id}/learn` | Generate learning report from performance |

### Full Campaign Request

```json
{
  "brand_id": "uuid",
  "goal": "increase sales by 30%",
  "budget": "₹5,00,000",
  "locale": "en-IN",
  "name": "Q3 Growth Campaign",
  "save": true
}
```

### Full Campaign Response

Returns all 9 analyses + executive summary + risk assessment + metadata.
If `save=true`, also returns `campaign_plan_id` for future reference.

---

## Database Schema

10 new tables (migration `0002_marketing_intelligence`):

| Table | Purpose |
|-------|---------|
| `business_memories` | Persistent business memory (JSONB) |
| `business_profiles` | Business analysis results |
| `audience_profiles` | Audience analysis results |
| `competitor_profiles` | Competitor analysis results |
| `marketing_strategies` | Objective + strategy (combined) |
| `creative_directions` | Creative direction results |
| `media_plans` | Media plan results |
| `campaign_plans` | Master record — full campaign JSONB + links |
| `execution_plans` | Execution plan results |
| `learning_reports` | Post-campaign learning reports |

All tables are tenant-scoped with RLS. All link to `brands` via foreign key.
The `campaign_plans` table is the master record — it stores the full campaign
as JSONB and links to individual analysis records.

---

## AI Quality

Every engine output includes:

| Field | Description |
|-------|-------------|
| `confidence` | 0.0-1.0 — how certain the AI is |
| `reasoning` | Why the AI made these choices |
| `recommendations` | List of `Recommendation` objects |
| `model` | Which AI model was used |
| `provider` | Which provider (groq/anthropic/openai/stub) |
| `tokens_used` | Token count |
| `cost_usd` | Estimated cost |
| `latency_ms` | Response time |
| `cached` | Whether result came from cache |
| `prompt_version` | Versioned prompt identifier |
| `request_id` | Unique request ID for debugging |

Every `Recommendation` includes:

| Field | Description |
|-------|-------------|
| `title` | Short title |
| `description` | Detailed description |
| `confidence` | 0.0-1.0 |
| `business_rationale` | Why this makes sense for the business |
| `marketing_rationale` | Why this makes sense for marketing |
| `alternatives` | Other options considered |
| `risks` | What could go wrong |
| `expected_outcome` | What we expect to happen |
| `evidence` | Supporting evidence |
| `sources` | Information sources |

---

## Test Coverage

80 tests across 6 test files:

| File | Tests | Coverage |
|------|-------|----------|
| `test_mi_base.py` | 17 | Base classes, Recommendation, EngineOutput, BusinessIntelligenceEngine |
| `test_mi_engines_1.py` | 13 | Audience, Competitor, Objective engines |
| `test_mi_engines_2.py` | 10 | Strategy, Creative Direction, Media Planning engines |
| `test_mi_engines_3.py` | 9 | Budget, Execution, Learning engines |
| `test_mi_brain.py` | 15 | Business Memory, Campaign Brain orchestrator, full pipeline |
| `test_campaign_brain.py` | 16 | DB models, API router, schemas, auth |
| **Total** | **80** | **All engines + brain + memory + API** |

Tests use stub-mode AI (no API keys required) for deterministic, fast execution.
The full 9-engine pipeline test runs in <0.1s.

---

## Usage Examples

### Run a Full Campaign

```python
from prachar_shared.marketing_intelligence import CampaignBrain

brain = CampaignBrain()
campaign = await brain.analyse_full(
    tenant_id=user.tenant_id,
    plan="agency",
    business_name="Acme Coffee",
    website="acme.com",
    goal="increase sales by 30%",
    budget="₹5,00,000",
    locale="en-IN",
    brand_id=brand.id,
)

print(campaign.executive_summary)
print(f"Confidence: {campaign.overall_confidence:.1%}")
print(f"Core message: {campaign.campaign_strategy.core_message}")
print(f"Total cost: {campaign.budget_estimate.total_cost}")
```

### Run a Single Engine

```python
from prachar_shared.marketing_intelligence import BusinessIntelligenceEngine

engine = BusinessIntelligenceEngine()
out = engine.run(
    tenant_id=user.tenant_id,
    plan="agency",
    business_name="Acme Coffee",
    website="acme.com",
)
profile = engine.to_profile(out)
print(profile.industry, profile.usp)
```

### Learn From a Completed Campaign

```python
brain = CampaignBrain()
report = await brain.learn_from_campaign(
    tenant_id=user.tenant_id,
    brand_id=brand.id,
    campaign_plan=campaign.to_dict(),
    performance_data={"ctr": "3.2%", "roas": "3.8x", "conversions": 750},
)
# Business Memory is automatically updated
```

---

## Design Principles

1. **Think before create** — No creative assets without strategy first
2. **Every recommendation has rationale** — business + marketing reasoning
3. **Every output has confidence** — know how much to trust the AI
4. **Memory persists** — campaigns learn from past campaigns
5. **BRO consults the brain** — never answers strategic questions directly
6. **Production quality** — no placeholders, no mock strategy
7. **₹10 crore agency feel** — McKinsey + WPP + OpenAI + Apple thinking
