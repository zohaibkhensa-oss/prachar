# PRACHAR V2 — AI Runtime Specification (Architecture Freeze v2.0)

> **FROZEN** — Approved with 8 amendments. No further architectural changes.
> The Orb never talks to Chat, CampaignBrain, Council, or Creative directly.
> It talks to the AI Runtime. The Runtime plans, decides, executes, and emits events.
> The frontend renders events. It doesn't care where they came from.

---

## 0. Frozen Architecture Diagram

```
User
 ↓
PRACHAR AI Orb
 ↓
AI Runtime
 ↓
Intent Engine
 ↓
Planner
 ↓
Decision Contract
 ↓
Execution Graph
 ↓
Tool Registry
 ↓
CampaignBrain · Agency Council · Creative Studio · Performance
Review · Automation · Memory · Chat · Proactive · Consult
 ↓
Event Bus
 ↓
Workspace Timeline
 ↓
Dashboard
 ↓
Learning Engine
```

---

## 1. The AI Runtime Lifecycle

Every AI request follows this lifecycle. No exceptions.

```
┌─────────────────────────────────────────────────────────────────┐
│  AI REQUEST                                                     │
│  { message, brand_id, modality, context }                       │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  AI CONTEXT OBJECT (Amendment 3)                                │
│  Assembled once. Passed to every tool. No re-queries.           │
│  { brand, campaign, workspace, conversation, memory,            │
│    permissions, billing, connected_channels,                    │
│    user_preferences, active_tasks }                             │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  INTENT ENGINE                                                  │
│  Classifies message → { intent, mode, confidence }              │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  PLANNER                                                        │
│  Reads Tool Manifests (Amendment 4).                            │
│  Builds Execution Graph (Amendment 2) — DAG, not list.          │
│  Parallel branches where independent.                           │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  DECISION CONTRACT (Amendment 1)                                │
│  Structured object created BEFORE execution.                    │
│  Becomes: audit trail, explainability, debugging,              │
│  analytics, learning, replay source.                            │
│  { goal, reasoning, tools, risk_level, requires_approval,       │
│    estimated_duration, expected_outputs, graph }                │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  EXECUTION GRAPH                                                │
│  Runs nodes in dependency order.                                │
│  Parallel branches run concurrently.                            │
│  Pauses at approval nodes.                                      │
│  Supports cancellation.                                         │
│  Emits events before/during/after each node.                    │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  EVENT BUS                                                      │
│  One SSE channel: GET /runtime/stream?session_id=xxx            │
│  Standardised taxonomy (Amendment 5).                           │
│  Frontend subscribes once, renders all events.                  │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  WORKSPACE TIMELINE (Amendment 6)                               │
│  Single source of truth. Replayable. Git-for-marketing.         │
│  Every action, every output, every decision, every learning.    │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  MEMORY UPDATE                                                  │
│  BusinessMemoryRecord · CouncilLearningRecord · Timeline        │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  RESPONSE COMPOSER                                              │
│  Composes conversational response from tool outputs.            │
│  "I've created your Diwali campaign. Council approved 8.5/10.   │
│   10 creative formats are ready. Budget: ₹15,000."              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Amendment 1 — Decision Contract

Every AI decision creates a structured object BEFORE anything executes.

```typescript
interface DecisionContract {
  id: string;                    // UUID, referenced by all events
  session_id: string;            // Runtime session
  timestamp: string;             // ISO 8601

  goal: string;                  // "Create Diwali Campaign"
  reasoning: string;             // Why this plan was chosen
  intent: string;                // "campaign.create"
  mode: RuntimeMode;             // "creation"

  tools: string[];               // ["CampaignBrain", "CreativeStudio", "Review"]
  graph: ExecutionGraph;         // DAG of tool calls (Amendment 2)

  risk_level: "low" | "medium" | "high" | "critical";
  requires_approval: boolean;    // Human-in-the-loop?
  approval_reason?: string;      // Why approval needed

  estimated_duration: string;    // "18 seconds"
  estimated_cost_usd: number;    // 0.12
  expected_outputs: string[];    // ["Campaign", "Image", "Caption", "Budget"]

  context_snapshot: AIContext;   // Full context at decision time (Amendment 3)

  status: "pending" | "approved" | "executing" | "completed" | "cancelled" | "failed";
  approved_by?: string;          // user_id if human-approved
  approved_at?: string;
}
```

**This single object becomes:**
- Audit trail (what was decided, when, why)
- Explainability (user can ask "why did you do X?")
- Debugging (replay the exact decision)
- Analytics (which plans succeed/fail)
- Learning (improve future planning)
- Replay (re-execute with different inputs)

**Stored in:** `workspace_timeline` as `entry_type: "decision_contract"`.

**API:** Every execution references its `decision_id`. Every event carries `decision_id`.

---

## 3. Amendment 2 — Execution Graph

The Planner builds a DAG, not a list. Parallel branches run concurrently.

### Graph Structure

```typescript
interface ExecutionGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];    // dependencies
}

interface GraphNode {
  id: string;
  tool: string;                    // "campaign_brain.analyse"
  input: Record<string, any>;      // can reference other nodes' outputs: "${node_2.result.profile}"
  deps: string[];                  // node IDs that must complete first
  parallel_group?: string;         // nodes in same group run concurrently
  needs_approval?: boolean;        // pause here for human approval
  timeout_ms?: number;
  retry_policy?: RetryPolicy;
}

interface GraphEdge {
  from: string;   // node id
  to: string;     // node id
  type: "dependency" | "data_flow";
}
```

### Example: Campaign Creation Graph

```
                    ┌─────────────────────┐
                    │ campaign_brain.     │
                    │ analyse             │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                 ▼
    ┌─────────────────┐ ┌──────────────┐ ┌──────────────┐
    │ campaign_brain. │ │ campaign_    │ │ campaign_    │
    │ strategy        │ │ brain.       │ │ brain.       │
    │                 │ │ creative     │ │ media        │
    └────────┬────────┘ └──────┬───────┘ └──────┬───────┘
             │                 │                │
             └────────┬────────┘                │
                      ▼                         │
             ┌─────────────────┐                │
             │ campaign_brain. │◄───────────────┘
             │ budget          │
             └────────┬────────┘
                      ▼
             ┌─────────────────┐
             │ campaign_brain. │
             │ execution       │
             └────────┬────────┘
                      ▼
             ┌─────────────────┐
             │ council.review  │ ← needs_approval: true
             └────────┬────────┘
                      ▼
             ┌─────────────────┐
             │ creative_studio.│
             │ generate        │
             └────────┬────────┘
                      ▼
             ┌─────────────────┐
             │ memory.update   │
             └─────────────────┘
```

**Parallel execution:** `strategy`, `creative`, `media` run concurrently after `analyse` completes. `budget` waits for both `strategy` and `media`. This cuts total time significantly vs sequential.

### Execution Engine Responsibilities

1. Topological sort the graph
2. Run nodes with no unmet deps (in parallel if same `parallel_group`)
3. When a node completes, check which dependents can now start
4. At `needs_approval` nodes, emit `approval.requested` and pause
5. On `approval.granted`, resume execution
6. On `session.cancelled`, terminate all running nodes
7. Emit `tool.started` / `tool.progress` / `tool.completed` for every node

---

## 4. Amendment 3 — AI Context Object

Assembled ONCE at request start. Passed to EVERY tool. No tool re-queries.

```typescript
interface AIContext {
  // Identity
  tenant_id: string;
  user_id: string;
  brand_id: string;

  // Brand (from Brand table)
  brand: {
    id: string;
    name: string;
    website: string;
    category: string;
    customer_type: "business" | "creator";
    locales: string[];
    tone: Record<string, any>;
    visibility_score: number;
  };

  // Active campaign (if any)
  campaign?: {
    id: string;
    name: string;
    goal: string;
    status: string;
    budget: string;
  };

  // Workspace timeline (recent activity)
  workspace: {
    recent_timeline: TimelineEntry[];   // last 20 entries
    active_tasks: ActiveTask[];         // currently running workers
  };

  // Conversation (current + recent)
  conversation: {
    current_message: string;
    history: ConversationMessage[];     // last 10 messages
  };

  // Memory (BusinessMemoryRecord)
  memory: {
    best_practices: string[];
    audience_insights: string[];
    creative_insights: string[];
    channel_insights: string[];
    total_campaigns: number;
    average_roi: string;
  };

  // Permissions
  permissions: {
    role: "owner" | "admin" | "member";
    can_approve: boolean;
    can_publish: boolean;
    can_manage_billing: boolean;
  };

  // Billing
  billing: {
    plan: "starter" | "growth" | "agency";
    ai_tokens_used: number;
    ai_budget: number;
    videos_used: number;
    videos_limit: number;
    images_used: number;
    images_limit: number;
  };

  // Connected channels
  connected_channels: {
    channel: string;
    status: "active" | "expired" | "pending";
  }[];

  // User preferences
  user_preferences: {
    locale: string;
    voice_enabled: boolean;
    auto_approve_threshold: number;   // council score above which auto-approve
    notification_channels: string[];
  };

  // Active background tasks
  active_tasks: {
    task_id: string;
    task_type: string;
    status: string;
    started_at: string;
  }[];
}
```

### Why This Matters

- **Performance**: 10 tools don't each query the brand, memory, billing. One query, passed to all.
- **Consistency**: All tools see the same snapshot. No race conditions.
- **Auditability**: The Decision Contract stores `context_snapshot` — exact state at decision time.
- **Cost**: Fewer DB queries = lower latency = better UX.

### Assembly

```python
async def assemble_context(brand_id, user, message) -> AIContext:
    # Parallel queries
    brand, memory, billing, connections, timeline, tasks = await asyncio.gather(
        get_brand(brand_id),
        get_memory(brand_id),
        get_billing(user.tenant_id),
        get_connections(brand_id),
        get_recent_timeline(brand_id, limit=20),
        get_active_tasks(brand_id),
    )
    return AIContext(...)
```

---

## 5. Amendment 4 — Tool Manifest

Every tool exposes metadata. The Planner reasons about tools automatically.

```typescript
interface ToolManifest {
  // Identity
  name: string;                    // "campaign_brain.analyse"
  display_name: string;            // "Business Intelligence Engine"
  description: string;             // "Analyzes business positioning, USP, market"
  category: ToolCategory;          // "campaign" | "creative" | "review" | ...

  // Schema
  input_schema: JSONSchema;        // What inputs it accepts
  output_schema: JSONSchema;       // What it returns

  // Cost & Time
  estimated_cost_usd: number;      // 0.02
  estimated_time_ms: number;       // 5000
  estimated_tokens: number;        // 2500

  // Capabilities
  supports_streaming: boolean;     // Can emit progress events?
  supports_cancellation: boolean;  // Can be cancelled mid-execution?
  supports_retry: boolean;

  // Requirements
  requires_brand: boolean;         // Needs brand_id?
  requires_user_approval: boolean; // Always needs approval? (e.g., publish)
  requires_active_subscription: boolean;

  // Behaviour
  retry_policy: RetryPolicy;
  timeout_ms: number;
  side_effects: "none" | "reads" | "writes" | "external";  // publish = external

  // Permissions
  required_role: "owner" | "admin" | "member";
  required_permissions: string[];  // ["can_approve", "can_publish"]
}
```

### Registered Tools (Initial Set)

| Tool Name | Category | Cost | Time | Approval | Streaming |
|-----------|----------|------|------|----------|-----------|
| `chat.respond` | conversation | $0.01 | 3s | no | yes |
| `campaign_brain.analyse` | campaign | $0.03 | 8s | no | yes |
| `campaign_brain.strategy` | campaign | $0.03 | 8s | no | yes |
| `campaign_brain.creative` | campaign | $0.02 | 6s | no | yes |
| `campaign_brain.media` | campaign | $0.02 | 6s | no | yes |
| `campaign_brain.budget` | campaign | $0.02 | 6s | no | yes |
| `campaign_brain.execution` | campaign | $0.02 | 6s | no | yes |
| `campaign_brain.full_campaign` | campaign | $0.15 | 45s | no | yes |
| `council.review` | review | $0.10 | 30s | no | yes |
| `creative_studio.generate` | creative | $0.08 | 30s | no | yes |
| `creative_studio.generate_image` | creative | $0.02 | 10s | no | yes |
| `creative_studio.generate_video` | creative | $0.08 | 20s | no | yes |
| `performance.story` | analytics | $0.02 | 5s | no | no |
| `performance.why` | analytics | $0.02 | 5s | no | no |
| `performance.next` | analytics | $0.02 | 5s | no | no |
| `proactive.notifications` | notification | $0.00 | 1s | no | no |
| `review.publish` | execution | $0.00 | 2s | **yes** | no |
| `review.approve` | execution | $0.00 | 1s | **yes** | no |
| `memory.retrieve` | memory | $0.00 | 1s | no | no |
| `memory.update` | memory | $0.00 | 1s | no | no |
| `consult.understand` | onboarding | $0.05 | 15s | no | yes |
| `creator.repurpose` | creative | $0.03 | 10s | no | yes |
| `creator.youtube_plan` | creative | $0.03 | 10s | no | yes |

### Adding New Tools

```python
@tool(
    name="seo.analyse",
    display_name="SEO Analysis Engine",
    description="Analyzes website SEO, identifies ranking opportunities",
    category="analytics",
    estimated_cost_usd=0.02,
    estimated_time_ms=8000,
    supports_streaming=True,
    requires_brand=True,
)
async def seo_analyse(ctx: AIContext, input: SEOInput) -> SEOReport:
    ...
```

The Planner automatically discovers this tool via the registry. No hardcoded intent mapping needed.

---

## 6. Amendment 5 — Event Taxonomy (Standardised)

### Namespaces

| Namespace | Covers |
|-----------|--------|
| `runtime.*` | Session lifecycle, cancellation, errors |
| `planner.*` | Intent classification, plan creation, decision contract |
| `tool.*` | Generic tool execution (started/progress/completed/error) |
| `memory.*` | Memory retrieval and updates |
| `voice.*` | Speech recognition and TTS |
| `campaign.*` | CampaignBrain engine events |
| `creative.*` | Creative Studio events |
| `review.*` | Review and approval events |
| `approval.*` | Human-in-the-loop approval |
| `automation.*` | Worker-triggered autonomous actions |
| `notification.*` | Proactive alerts |
| `analytics.*` | Performance analysis |
| `workspace.*` | Timeline updates |

### Event Envelope (unchanged)

```typescript
interface AIEvent {
  session_id: string;
  decision_id: string;           // NEW: links to Decision Contract
  timestamp: string;
  type: string;                  // e.g. "campaign.analysis.completed"
  phase: string;
  tool?: string;
  data?: any;
  orb_state?: OrbState;
  progress?: { completed: number; total: number; label: string };
}
```

### Complete Event Catalogue

#### runtime.*
| Event | When | Orb State |
|-------|------|-----------|
| `runtime.session.started` | Runtime accepts request | `understanding` |
| `runtime.session.completed` | All tools done, response composed | `completed` |
| `runtime.session.cancelled` | User cancelled | `cancelled` |
| `runtime.session.error` | Unrecoverable error | `error` |
| `runtime.session.timeout` | Session timed out | `error` |

#### planner.*
| Event | When | Orb State |
|-------|------|-----------|
| `planner.intent.classified` | Intent classified | `understanding` |
| `planner.plan.created` | Execution graph built | `planning` |
| `planner.decision.created` | Decision Contract created | `planning` |
| `planner.decision.approved` | User approved the plan | `executing` |
| `planner.decision.rejected` | User rejected the plan | `completed` |

#### tool.*
| Event | When | Orb State |
|-------|------|-----------|
| `tool.started` | Any tool begins | `executing` |
| `tool.progress` | Tool reports intermediate progress | `reasoning` |
| `tool.completed` | Tool finishes successfully | `generating` |
| `tool.error` | Tool fails (may retry) | `reasoning` |
| `tool.cancelled` | Tool cancelled | `cancelled` |

#### campaign.*
| Event | When | Orb State |
|-------|------|-----------|
| `campaign.analysis.started` | BusinessIntelligenceEngine starts | `reasoning` |
| `campaign.analysis.completed` | Engine finishes | `reasoning` |
| `campaign.strategy.completed` | StrategyEngine finishes | `reasoning` |
| `campaign.creative.completed` | CreativeDirectionEngine finishes | `generating` |
| `campaign.media.completed` | MediaPlanningEngine finishes | `reasoning` |
| `campaign.budget.completed` | BudgetEngine finishes | `reasoning` |
| `campaign.execution.completed` | ExecutionPlanner finishes | `generating` |
| `campaign.full.completed` | All 9 engines done | `generating` |

#### creative.*
| Event | When | Orb State |
|-------|------|-----------|
| `creative.image.started` | Image generation starts | `generating` |
| `creative.image.completed` | Image ready | `generating` |
| `creative.caption.completed` | Caption generated | `generating` |
| `creative.video.started` | Video generation starts | `generating` |
| `creative.video.completed` | Video ready | `generating` |
| `creative.format.completed` | One of 10 formats done | `generating` |

#### review.*
| Event | When | Orb State |
|-------|------|-----------|
| `review.queue.updated` | Review queue changed | `idle` |
| `review.council.started` | Council review begins | `reasoning` |
| `review.council.completed` | Council reaches consensus | `generating` |

#### approval.*
| Event | When | Orb State |
|-------|------|-----------|
| `approval.requested` | Runtime needs human approval | `waiting_approval` |
| `approval.granted` | User approves | `executing` |
| `approval.denied` | User denies | `completed` |

#### agency.* (subset of review)
| Event | When | Orb State |
|-------|------|-----------|
| `agency.director.started` | A director begins review | `reasoning` |
| `agency.director.completed` | A director finishes | `reasoning` |
| `agency.consensus.started` | ConsensusEngine begins | `reasoning` |
| `agency.consensus.completed` | Consensus reached | `generating` |

#### voice.*
| Event | When | Orb State |
|-------|------|-----------|
| `voice.started` | Mic starts recording | `listening` |
| `voice.transcribing` | Transcript arriving | `transcribing` |
| `voice.completed` | Final transcript | `understanding` |
| `voice.speaking.started` | TTS begins | `speaking` |
| `voice.speaking.finished` | TTS ends | `idle` |
| `voice.interrupted` | User interrupts TTS | `listening` |

#### memory.*
| Event | When | Orb State |
|-------|------|-----------|
| `memory.retrieved` | Memory loaded for context | `understanding` |
| `memory.updated` | Learning persisted | `idle` |

#### notification.*
| Event | When | Orb State |
|-------|------|-----------|
| `notification.created` | Proactive anomaly detected | `idle` |
| `notification.dismissed` | User dismissed | `idle` |

#### analytics.*
| Event | When | Orb State |
|-------|------|-----------|
| `analytics.story.completed` | Performance story generated | `speaking` |
| `analytics.why.completed` | Root cause analysis done | `reasoning` |
| `analytics.next.completed` | Recommendations generated | `reasoning` |

#### automation.*
| Event | When | Orb State |
|-------|------|-----------|
| `automation.overnight.started` | Overnight review begins | `idle` |
| `automation.overnight.completed` | Overnight review done | `idle` |
| `automation.budget.reallocated` | Worker reallocated budget | `idle` |
| `automation.campaign.published` | Worker published campaign | `idle` |
| `automation.learning.stored` | LearningEngine updated memory | `idle` |

#### workspace.*
| Event | When | Orb State |
|-------|------|-----------|
| `workspace.timeline.appended` | New timeline entry written | `idle` |

### Why Standardise Now

Adding "SEO Agent" tomorrow:
- `seo.audit.started` / `seo.audit.completed` / `seo.optimize.completed`
- Fits naturally into `seo.*` namespace
- Frontend already handles `*.started` / `*.completed` patterns
- Zero new protocol

---

## 7. Amendment 6 — Workspace Timeline (Source of Truth)

### Concept

Not "chat history" — the **single source of truth** for the workspace. Replayable. Git-for-marketing.

### Timeline Flow

```
Voice request
 ↓
Decision Contract created
 ↓
Campaign created (9 engines)
 ↓
Image generated
 ↓
Caption generated
 ↓
Council review (9 directors)
 ↓
Approval (human)
 ↓
Publish (to Instagram, Facebook, Google)
 ↓
Performance update (12.4K reach, 8 enquiries)
 ↓
Learning stored ("Reels outperform carousels 3x")
 ↓
Memory updated
```

Every step is a timeline entry. Every entry references its `decision_id`. Everything is replayable.

### Storage

```sql
CREATE TABLE workspace_timeline (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL,
  brand_id        UUID REFERENCES brands(id) ON DELETE CASCADE,
  session_id      UUID,                      -- Runtime session (if any)
  decision_id     UUID,                      -- Decision Contract (if any)
  entry_type      VARCHAR(40) NOT NULL,      -- see taxonomy below
  actor           VARCHAR(16) NOT NULL,      -- user, ai, system
  title           VARCHAR(200) NOT NULL,     -- "Diwali Campaign created"
  summary         TEXT,                      -- "9 engines, 8.2/10 confidence"
  detail          JSONB,                     -- full event data
  replayable      BOOLEAN DEFAULT false,     -- can this be re-executed?
  replay_inputs   JSONB,                     -- inputs needed to replay
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_timeline_brand ON workspace_timeline(brand_id, created_at DESC);
CREATE INDEX idx_timeline_session ON workspace_timeline(session_id);
CREATE INDEX idx_timeline_decision ON workspace_timeline(decision_id);
```

### Entry Types

| Entry Type | Actor | Example Title |
|------------|-------|---------------|
| `decision_contract` | ai | "Plan: Create Diwali Campaign" |
| `conversation` | user/ai | "User: Create a campaign / AI: I'll start..." |
| `campaign_created` | ai | "Diwali Campaign created" |
| `campaign_analysis` | ai | "Business analysis completed" |
| `council_review` | ai | "9 directors reviewed, consensus: approved" |
| `creative_generated` | ai | "10 creative formats generated" |
| `image_generated` | ai | "Image: Diwali festival poster" |
| `video_generated` | ai | "Video: 15s product demo" |
| `approval` | user | "User approved Diwali Campaign" |
| `published` | system | "Published to Instagram, Facebook, Google" |
| `performance_update` | system | "12.4K reach, 8 enquiries this week" |
| `proactive_alert` | ai | "Drop detected: Google Ads CTR down 23%" |
| `budget_reallocated` | system | "₹500 moved from Google Ads to Instagram" |
| `memory_updated` | ai | "Learned: Reels outperform carousels 3x" |
| `repurposed` | ai | "Video repurposed into 11 assets" |
| `automation_run` | system | "Overnight review completed for 3 campaigns" |

### API

```
GET /timeline?brand_id=uuid&limit=50&cursor=xxx&entry_type=campaign_created

→ Returns:
{
  "items": [ TimelineEntry ],
  "next_cursor": "xxx"
}
```

### Replay

Any entry with `replayable=true` can be re-executed:

```
POST /timeline/{id}/replay
→ Re-executes the tool with original inputs (or modified inputs)
→ Creates new session, new decision contract, new timeline entries
```

### Why This Is the Biggest Improvement

- **Single source of truth**: Dashboard, activity feed, audit trail, chat history — all read from one table
- **Replayable**: "Run that campaign again with a higher budget" → replay the decision
- **Explainable**: "Why did you create this campaign?" → trace the decision contract
- **Learning**: LearningEngine reads timeline to improve future planning
- **Compliance**: Complete audit trail in one place

---

## 8. Amendment 7 — Runtime Modes

Not every request behaves the same. The Planner changes behaviour based on mode.

| Mode | Behaviour | Example Request |
|------|-----------|-----------------|
| `conversation` | Quick chat response. No tools except chat.respond. | "What's the weather?" |
| `research` | Read-only analysis. No writes. Tools: performance.*, proactive.*, memory.retrieve. | "How are my ads doing?" |
| `planning` | Creates plans but doesn't execute. Returns Decision Contract for review. | "Plan a Diwali campaign" |
| `creation` | Full execution. Creates campaigns, creatives, etc. May require approval. | "Create a Diwali campaign" |
| `review` | Council review mode. Tools: council.review. | "Review my campaign" |
| `execution` | Publishing, budget changes. Always requires approval. | "Publish the campaign" |
| `automation` | Worker-triggered. No user input. Overnight reviews, budget realloc. | (system) |
| `learning` | Post-campaign learning. Tools: campaign_brain.learn, memory.update. | "What did we learn from the last campaign?" |

### Mode Determination

The Intent Engine classifies both `intent` AND `mode`:

```typescript
interface IntentResult {
  intent: string;        // "campaign.create"
  mode: RuntimeMode;     // "creation"
  confidence: number;    // 0.0-1.0
}
```

### Mode → Planner Behaviour

| Mode | Planner Behaviour |
|------|-------------------|
| `conversation` | Only chat.respond. No graph. |
| `research` | Read-only tools. No writes. No approval. |
| `planning` | Build full graph but mark as `dry_run`. Don't execute. Return Decision Contract. |
| `creation` | Build full graph. Execute. Pause at approval nodes. |
| `review` | Only council.review tool. |
| `execution` | Only execution tools (publish, approve). Always approval. |
| `automation` | No user input. Pre-planned graph from worker. |
| `learning` | Only learning tools. |

---

## 9. Amendment 8 — Long-Term Vision (PRACHAR AI)

### The Goal

Users never see "CampaignBrain", "Agency Council", "Creative Studio". They see **PRACHAR AI**.

```
User: "Create a Diwali campaign"
  ↓
PRACHAR AI: "I'll handle that. Analysing your business... Researching competitors...
         Defining strategy... Creating visual direction... Planning media...
         Estimating budget... Reviewing with my team of 9 specialists...
         They approved it 8.5/10. 10 creative formats are ready.
         Budget: ₹15,000. Shall I publish?"
  ↓
User: "Yes"
  ↓
PRACHAR AI: "Published to Instagram, Facebook, and Google. I'll monitor
         performance and let you know how it's doing."
```

### Implementation

The Runtime already achieves this. The Orb calls `POST /runtime/invoke`. The Runtime plans, executes, and composes a conversational response. The user never knows which tools ran.

The Tool names are internal. The Response Composer translates tool outputs into natural language.

### Future Capabilities (Plug-in via Tool Registry)

| Future Tool | What It Does |
|-------------|-------------|
| `seo.audit` | SEO website audit |
| `seo.optimize` | On-page SEO recommendations |
| `website.builder` | Generate landing pages |
| `crm.sync` | Sync leads to CRM |
| `email.campaign` | Email marketing automation |
| `whatsapp.broadcast` | WhatsApp broadcast campaigns |
| `sales.forecast` | Revenue forecasting |
| `competitor.monitor` | Ongoing competitor tracking |

Each registers as a Tool with a Manifest. The Planner discovers them. The Orb handles them. **Zero frontend changes.**

---

## 10. Orb State Machine (13 States, Frozen)

```
idle → wake → listening → transcribing → understanding → planning
→ reasoning → executing → generating → waiting_approval
→ speaking → completed → cancelled → error
```

Every event carries `orb_state`. Frontend sets orb to that state. State machine enforced by Runtime.

| State | Visual | Meaning |
|-------|--------|---------|
| `idle` | Calm breathing glow | No active request |
| `wake` | Brief flash | Wake word detected |
| `listening` | Fast pulse, ripples | User speaking |
| `transcribing` | Subtle pulse | Speech → text |
| `understanding` | Slow rotation | Classifying intent, loading context |
| `planning` | Rotating gradient | Building execution graph, creating decision contract |
| `reasoning` | Rotation + inner glow | Tool running (engine/director/analysis) |
| `executing` | Energetic pulse | Tool performing action |
| `generating` | Bright pulse + sparkles | Tool producing output (image/video/text) |
| `waiting_approval` | Pulsing yellow ring | Needs human approval |
| `speaking` | Energetic pulse, waves | TTS speaking response |
| `completed` | Brief green flash | Success |
| `cancelled` | Brief dim | User cancelled |
| `error` | Brief red flash | Error occurred |

---

## 11. The Contract (4 Endpoints, Frozen)

```
POST /runtime/invoke
  Body: { message, brand_id, modality, context }
  Returns: { session_id, decision_id, stream_url }

GET /runtime/stream?session_id=xxx
  Returns: SSE stream of AIEvent objects

GET /dashboard/overview?brand_id=uuid
  Returns: { greeting, performance, campaigns, notifications, tasks, memory, orb, activity }

GET /timeline?brand_id=uuid&limit=50&cursor=xxx
  Returns: { items: [TimelineEntry], next_cursor }

POST /runtime/approve
  Body: { decision_id, choice: "approve" | "deny", modifications? }
  Returns: { status }

POST /runtime/cancel
  Body: { session_id }
  Returns: { status }

POST /timeline/{id}/replay
  Body: { input_overrides? }
  Returns: { session_id, stream_url }
```

**7 endpoints total. That's the entire Runtime API.**

---

## 12. Revised Roadmap (Frozen)

### Phase 0 — Freeze & Audit ✅
- [x] UI freeze
- [x] Capability audit (87 endpoints, 10 engines, 9 directors, 26 adapters)
- [x] Backend audit (30+ tables, all workers, all memory stores)

### Phase 0.5 — AI Runtime Specification ✅ (THIS DOCUMENT)
- [x] AI Runtime lifecycle (with Decision Contract)
- [x] Execution Graph (DAG, parallel branches)
- [x] AI Context Object (assembled once, passed to all tools)
- [x] Tool Manifest (metadata for Planner reasoning)
- [x] Event Taxonomy (13 standardised namespaces)
- [x] Workspace Timeline (single source of truth, replayable)
- [x] Runtime Modes (8 modes, Planner behaviour changes)
- [x] PRACHAR AI vision (tools are internal, users see PRACHAR AI)
- [x] Orb State Machine (13 states)
- [x] Dashboard Composition (one endpoint)
- [x] **Approved and frozen**

### Phase A — AI Runtime Backend
Build the runtime. No UI changes.

| Item | What |
|------|------|
| A1 | Tool Registry + Tool Manifests for all existing capabilities |
| A2 | AI Context Assembler (parallel queries, one object) |
| A3 | Intent Engine (LLM: message → intent + mode) |
| A4 | Planner (LLM: intent + context + tool manifests → execution graph) |
| A5 | Decision Contract (structured object before execution) |
| A6 | Execution Engine (runs graph, parallel branches, pauses at approval) |
| A7 | Event Bus (SSE endpoint) |
| A8 | Response Composer (LLM: tool outputs → conversational response) |
| A9 | workspace_timeline table + migration |
| A10 | POST /runtime/invoke, GET /runtime/stream, POST /runtime/approve, POST /runtime/cancel |
| A11 | GET /timeline, POST /timeline/{id}/replay |
| A12 | GET /dashboard/overview (composition endpoint) |

**Deliverable**: Backend can accept any request, plan it, decide, execute, stream events, compose response, persist to timeline. All existing capabilities work through the runtime.

### Phase B — Orb & Voice (Frontend)
Wire the orb to the runtime.

| Item | What |
|------|------|
| B1 | OrbStateMachine (13 states, driven by events) |
| B2 | EventSubscriber (one SSE client, handles all event types) |
| B3 | VoiceFlow (Web Speech API → invoke → events → TTS) |
| B4 | ConversationPanel (streaming text, suggested questions) |
| B5 | ApprovalDialog (renders approval.requested events) |
| B6 | ProgressIndicator (step-by-step from tool events) |

### Phase C — Dashboard & Timeline (Frontend)
Make the dashboard real.

| Item | What |
|------|------|
| C1 | DashboardOverview (renders /dashboard/overview) |
| C2 | AITeamGrid (agent statuses) |
| C3 | ActivityFeed (live activity from timeline) |
| C4 | MemoryPanel (recent learnings) |
| C5 | TimelinePage (/app/timeline, infinite scroll) |
| C6 | Real-time dashboard (SSE for live updates) |

### Phase D — Capability Streaming (Backend)
Existing engines emit events through the bus.

| Item | What |
|------|------|
| D1 | CampaignBrain engines emit campaign.* events |
| D2 | Agency Council directors emit agency.* events |
| D3 | Creative Studio emits creative.* events |
| D4 | Consult emits onboarding events |
| D5 | Proactive engine emits notification.* events |

### Phase E — Automation & Overnight
Autonomous marketing.

| Item | What |
|------|------|
| E1 | Overnight Council review on all active campaigns |
| E2 | Auto-approve within rules (score > threshold, no critical risks) |
| E3 | Learning loop after each campaign |
| E4 | Budget auto-realloc with events |
| E5 | Proactive campaign creation with approval dialog |

---

## 13. Runtime Certification Checklist

Before Phase A is considered complete, verify:

| # | Question | Must Be |
|---|----------|---------|
| 1 | Can every tool be invoked through the Runtime? | YES |
| 2 | Does every execution emit events? | YES |
| 3 | Does every execution create a Decision Contract? | YES |
| 4 | Does every execution write to the Timeline? | YES |
| 5 | Does every execution update Memory where appropriate? | YES |
| 6 | Does every execution support cancellation? | YES |
| 7 | Does every execution produce explainable outputs? | YES |
| 8 | Does every execution have an audit trail? | YES |
| 9 | Can every Decision Contract be replayed? | YES |
| 10 | Does the Planner reason about Tool Manifests (not hardcoded)? | YES |

If all 10 are YES, the Runtime is coherent. If any is NO, that's a gap to close before moving to Phase B.

---

## 14. What Does NOT Change

| Component | Status |
|-----------|--------|
| 10 AI engines | ✓ Wrapped as tools |
| 9 AI directors | ✓ Wrapped as a tool |
| 26 channel adapters | ✓ Unchanged (called by workers) |
| All 87 existing endpoints | ✓ Still available for direct API access |
| All workers | ✓ Unchanged |
| All memory stores | ✓ Runtime reads/writes through them |
| Policy gates | ✓ Unchanged |
| Auth/RLS | ✓ Unchanged |

**The Runtime is additive. It sits on top. Nothing is replaced.**

---

## 15. Architecture Freeze v2.0 — Sign-off

| Area | Status |
|------|--------|
| UI Architecture | ✅ Approved |
| AI Runtime | ✅ Approved |
| Event Bus | ✅ Approved |
| Planner | ✅ Approved |
| Tool Registry | ✅ Approved |
| Dashboard Composition | ✅ Approved |
| Workspace Timeline | ✅ Approved |
| Orb State Machine | ✅ Approved |
| Unified Runtime | ✅ Approved |
| Decision Contract (A1) | ✅ Approved |
| Execution Graph (A2) | ✅ Approved |
| AI Context Object (A3) | ✅ Approved |
| Tool Manifest (A4) | ✅ Approved |
| Event Taxonomy (A5) | ✅ Approved |
| Workspace Timeline as Source of Truth (A6) | ✅ Approved |
| Runtime Modes (A7) | ✅ Approved |
| PRACHAR AI Vision (A8) | ✅ Approved |

**Overall: 10/10. Architecture frozen. No further architectural changes.**

**Next step: Phase A implementation.**
