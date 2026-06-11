# Theseus ERP — Architecture Design Spec

**Date:** 2026-04-15
**Status:** Draft
**Author:** Justin + Claude (brainstorming session)

---

## 1. Vision & Philosophy

### 1.1 What Is Theseus ERP?

An open-source, AI-first ERP system for small manufacturing and trade businesses (1–100 people). Named after the Ship of Theseus — every module can be rebuilt, no two implementations are alike, and the system evolves continuously with the business.

### 1.2 Core Problems We're Solving

Existing ERPs suffer from:
- **Poor interconnectivity** between modules — data doesn't flow naturally across the system
- **Canned modules** that require heavy customization yet still don't perfectly fit the business
- **Critical features behind paywalls** — reporting, advanced workflows, etc.
- **Difficult customization** — changing anything risks breaking everything
- **Poor UI/UX** — dated interfaces, steep learning curves, no modern interaction patterns
- **Painful migrations** — switching ERPs is expensive, risky, and often fails

### 1.3 Core Differentiators

1. **AI-generated custom modules** — the Shipwright builds tailored Planks from natural language, not canned modules requiring customization
2. **Natural language as primary interface** with full traditional UI fallback
3. **Provider-agnostic AI** — supports Claude, GPT, Llama, local models. No vendor lock-in.
4. **Progressive complexity** — scales from solo operator to 100-person organization
5. **100% of features free and open source** — monetize convenience, not features
6. **Plank-by-plank migration** — transition from existing systems gradually with AI assistance

### 1.4 Naming Convention

| Concept | Theseus Term |
|---------|-------------|
| Core platform/framework | **The Keel** |
| Modules | **Planks** |
| AI assistant/builder | **The Shipwright** |
| Setting up your business | **Building your ship** |
| Module marketplace | **The Shipyard** |
| Schema definitions (YAML/MD) | **Blueprints** |
| Migration & transition engine | **The Drydock** |
| Design system | **The Hull** |
| A single Plank migration | **Refit** |
| Parallel validation period | **Sea Trial** |
| Plank go-live moment | **Commissioning** |
| All users | **Crew** |
| Admin/IT | **Helmsman** |
| Department leads | **Bosuns** |
| Day-to-day users | **Deckhands** |

---

## 2. Target Users

### 2.1 Primary Audience

Small manufacturing and trade businesses:
- Solo to micro (1–5 people): owner wears all hats
- Small (5–25 people): a few distinct roles
- Small-to-mid (25–100 people): real departments, multiple locations

### 2.2 Progressive Complexity

The system scales in complexity as the business grows:
- Solo operator sees a simple, focused interface
- As roles, locations, and processes are added, features reveal themselves
- No business should have to migrate to a different ERP when they outgrow the simple version

---

## 3. Architecture — The Living Business Model

### 3.1 Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    AI LAYER                          │
│  The Shipwright — natural language ↔ business logic  │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│              SEMANTIC LAYER                          │
│  Knowledge Graph (relationships + meaning)           │
│  Blueprints (YAML — source of truth for modules)     │
│  Business rules, workflows, constraints              │
└──────┬──────────────────────────────────┬───────────┘
       │                                  │
┌──────▼──────────┐          ┌───────────▼────────────┐
│  TRANSACTION     │          │   EVENT STORE          │
│  LAYER           │          │                        │
│  PostgreSQL      │          │   Append-only log of   │
│  Generated       │◄────────►│   every business event │
│  tables, ACID    │          │   Full audit trail     │
│  integrity       │          │   AI context + sync    │
└─────────────────┘          └────────────────────────┘
```

### 3.2 Key Architectural Principles

1. **Blueprints are the source of truth** — YAML definitions describe what entities exist. The database is a generated artifact.
2. **Events capture everything** — every business action is an immutable event. Current state is derived.
3. **Knowledge graph connects everything** — cross-Plank relationships are graph traversals, not SQL JOINs.
4. **Single PostgreSQL instance** — transactional data, event store, knowledge graph (ltree), conversations. No external dependencies for v1.
5. **Progressive infrastructure** — start simple (one Postgres), scale later (add Neo4j, Kafka, etc.) as needed.

---

## 4. The Keel (Core Platform)

### 4.1 Blueprint Engine

Reads human-readable YAML Blueprint files and translates them into a working system.

**Blueprint format example:**
```yaml
plank: inventory
entity: StockItem
version: 1
description: A trackable item in inventory

fields:
  sku:
    type: string
    unique: true
    required: true
  name:
    type: string
    required: true
  category:
    type: enum
    values: [raw_material, component, finished_good, consumable]
  unit_of_measure:
    type: string
    default: "each"
  reorder_point:
    type: decimal
    default: 0
  current_stock:
    type: decimal
    computed: true

relations:
  suppliers:
    type: many_to_many
    target: contacts.Contact
    filter: { type: supplier }
  bom_components:
    type: one_to_many
    target: manufacturing.BOMLine

behaviors:
  on_stock_below_reorder:
    trigger: current_stock < reorder_point
    action: emit_event
    event: RestockNeeded
```

**Blueprint Engine responsibilities:**
1. Validate Blueprints against a meta-schema
2. Generate PostgreSQL migrations (CREATE TABLE, ALTER TABLE, indexes, foreign keys)
3. Register entities in the knowledge graph
4. Generate API endpoints (CRUD with validation)
5. Generate UI schemas for the adaptive interface
6. Register event handlers from behavior definitions

**Key principle:** Blueprints are declarative — they describe *what*, the Keel handles *how*.

### 4.2 Schema Engine (Migration Manager)

- Generates versioned migrations from Blueprint Engine output (Alembic-style)
- Tracks applied migrations
- Non-destructive changes (add field, add entity) are automatic
- Destructive changes (remove field, change type) require explicit confirmation and data backup
- All migrations are recorded as events in the event store

### 4.3 Event Store

Every business action is an immutable event.

**Event structure:**
```json
{
  "event_id": "evt_abc123",
  "event_type": "inventory.StockAdjusted",
  "entity_type": "StockItem",
  "entity_id": "item_456",
  "timestamp": "2026-04-15T10:30:00Z",
  "actor": { "type": "user", "id": "user_789" },
  "data": {
    "quantity_change": -50,
    "reason": "shipped_to_customer",
    "related_order": "order_321"
  },
  "metadata": {
    "source": "shipwright",
    "blueprint_version": 1
  }
}
```

**Implementation:**
- PostgreSQL append-only `events` table, partitioned by month
- Events are immutable — no UPDATE or DELETE
- Current state derived by event replay with materialized views for performance
- LISTEN/NOTIFY for pub/sub (no Kafka dependency for v1)
- Offline events from PWA clients are queued and synced — event sourcing makes this natural

### 4.4 Knowledge Graph

The semantic backbone that enables cross-Plank interconnectivity.

**Technology:** PostgreSQL `ltree` extension + recursive CTEs, with an abstraction layer for future swap to Neo4j if needed.

**What it stores:**
- Entity types and relationships (from Blueprints)
- Instance relationships (from data)
- Semantic metadata (entity X is part of Plank Y)
- Business rules (trigger conditions, workflow transitions)

**What it enables:**
- The Shipwright traverses relationships instead of joining tables
- Cross-Plank reporting is graph queries
- Impact analysis ("if I change this supplier, what's affected?")
- Conflict detection during setup (two Bosuns defining overlapping requirements)

### 4.5 LLM Abstraction Layer

Provider-agnostic AI integration.

```
Shipwright (application logic)
    ↓
LLM Gateway (routing, caching, rate limiting)
    ↓
Provider Adapters
    ├── AnthropicAdapter (Claude)
    ├── OpenAIAdapter (GPT)
    ├── OllamaAdapter (local models)
    └── CustomAdapter (any OpenAI-compatible API)
```

**Features:**
- Unified tool/function calling interface across providers
- Structured output validation
- Quality-aware routing (complex tasks → stronger model, simple tasks → faster model)
- Graceful degradation (AI unavailable → traditional UI still works)
- Domain-specific prompt templates for ERP tasks

### 4.6 The Drydock (Migration & Transition Engine)

Handles transitioning businesses from existing systems to Theseus, Plank by Plank.

#### Refit Phases

**Phase 1: Discovery (Shipwright-led)**
- Structured conversation with the relevant Bosun about their current process
- Analysis of uploaded data exports (Excel, CSV, database exports)
- Identification of inefficiencies in current workflows
- This is a business improvement opportunity, not just data migration

**Phase 2: Blueprint Generation**
- Shipwright generates custom Blueprints based on discovery
- Shows what's different from the old system and why
- Human review and approval required before applying

**Phase 3: Data Import**
- Import adapters for common sources:
  - Excel/CSV (most common for small businesses)
  - Odoo (API or database export)
  - QuickBooks (API)
  - Common ERPs (Dynamics, SAP — via standard export formats)
  - Generic database (JDBC/ODBC)
- Data mapping, cleaning, deduplication
- Validation report before committing

**Phase 4: Sea Trial (Parallel Running)**
- Business continues using old system for real work
- Theseus receives periodic data updates and runs alongside
- Reconciliation reports: where the two systems agree and disagree
- Confidence dashboard: sync status, discrepancy log, user activity
- Each Plank has its own independent Sea Trial

**Phase 5: Commissioning**
- Shipwright walks through a go-live checklist
- Snapshot event recorded at exact moment of cutover
- Old system data archived (never deleted)
- Plank goes live as system of record

#### Multi-User Migration Flow

Different Crew members handle different Planks:
- Helmsman (IT) installs Theseus, initial config, invites Bosuns with domain scopes
- Each Bosun talks to the Shipwright about their domain independently
- Shipwright maintains separate conversation contexts per user but unified system awareness
- Cross-domain conflict detection: Shipwright identifies when two Bosuns' requirements conflict
- Helmsman gets a setup dashboard showing all Planks' status, conflicts, and dependencies

### 4.7 Crew Roles & Dynamic Assignment

Roles are scoped to Planks and emerge from the actual business structure:

| Role | Access | Scope |
|------|--------|-------|
| **Helmsman** | Full system admin, Blueprint approval, Crew management | All Planks |
| **Bosun** | Configure and manage specific Planks, Shipwright Architect mode | Assigned Planks |
| **Deckhand** | Day-to-day operations within permitted Planks | Assigned Planks |

**Dynamic role assignment:**
- No predefined org chart — roles emerge from Shipwright conversation
- A solo operator is Helmsman + Bosun + Deckhand for everything
- As the business grows, roles can be delegated to new Crew members
- The Shipwright suggests role restructuring as complexity increases

---

## 5. The Shipwright (AI Engine)

### 5.1 Operating Modes

| Mode | When | Capabilities |
|------|------|-------------|
| **Architect** | Setup, Refits, new Planks | Discovery conversations, Blueprint generation, conflict detection |
| **Operator** | Daily use | Quick actions, queries, data entry via natural language |
| **Analyst** | Reporting, insights | Cross-Plank analytics, trend detection, anomaly alerts |
| **Mentor** | Training, onboarding | Guides new users, explains system, suggests better approaches |

Mode switching is automatic based on context but manually overridable.

### 5.2 Context Architecture

```
┌─────────────────────────────────────────┐
│ Layer 1: KEEL CONTEXT (static)          │
│ What Theseus is, tools, capabilities    │
├─────────────────────────────────────────┤
│ Layer 2: SHIP CONTEXT (per-business)    │
│ Blueprints, knowledge graph, rules,     │
│ crew roles                              │
├─────────────────────────────────────────┤
│ Layer 3: CREW CONTEXT (per-user)        │
│ Role, scope, permissions, preferences,  │
│ past conversations                      │
├─────────────────────────────────────────┤
│ Layer 4: VOYAGE CONTEXT (per-session)   │
│ Current conversation, active task,      │
│ what's on screen                        │
└─────────────────────────────────────────┘
```

### 5.3 Tool System

**Architect tools:** generate_blueprint, modify_blueprint, detect_conflicts, import_data, assign_scope

**Operator tools:** create_entity, update_entity, query_entities, execute_workflow, traverse_graph

**Analyst tools:** aggregate_events, compare_periods, detect_anomalies, generate_report

**Mentor tools:** explain_entity, show_workflow, suggest_action

### 5.4 Safety & Validation

- Architect actions require Helmsman approval — no autonomous schema changes
- Operator actions respect Crew permissions and Plank scopes
- Destructive actions require explicit confirmation with impact summary
- All Shipwright actions are events in the event store (complete audit trail)
- Blueprint changes go through validation: meta-schema check, conflict detection, dry-run migration

---

## 6. The Adaptive Interface

### 6.1 Interface Modes

| Mode | Trigger | Layout |
|------|---------|--------|
| **Conversational** (default) | First-time setup, complex tasks, new users | Full-screen chat with inline cards/forms/data |
| **Command Bar** | Cmd-K, quick actions | Overlay on current view |
| **Panel** | Browsing data + asking questions | Sidebar chat alongside traditional UI |

Default starting experience is full conversational mode. The Shipwright greets new users and walks them through setup. Interface adapts as users gain experience.

### 6.2 Generated UI (Blueprint-Driven)

The UI is not handcrafted — it's generated from Blueprints:
- List views (sortable, filterable tables)
- Detail views (form with related entities and event history)
- Create/edit forms (validated inputs with proper field types)
- Dashboard widgets (counts, charts, activity)

Blueprint `ui` hints allow customization:
```yaml
fields:
  status:
    type: enum
    values: [draft, sent, paid, overdue]
    ui:
      component: status_badge
      colors:
        draft: neutral
        sent: info
        paid: success
        overdue: danger
```

### 6.3 Progressive Density

UI density scales based on:
- **User experience level:** new → guided and spacious; power user → data-dense with keyboard shortcuts
- **Business complexity:** solo → simplified; larger org → full navigation, approval queues, audit logs

The Shipwright tracks usage patterns and offers density upgrades.

### 6.4 The Hull (Design System)

**Consistent layer (non-negotiable):**
- Typography, colors, spacing tokens
- Core components: buttons, inputs, tables, cards, modals, toasts
- Layout primitives: page structure, sidebar, header, content area
- Interaction patterns, accessibility standards
- Shipwright chat components (bubbles, inline cards, action buttons)

**Flexible layer (Blueprint-driven):**
- Field-level rendering hints override defaults
- Per-Plank dashboard layouts
- Custom view overrides in `views/overrides/` (must use Hull design tokens)
- Business branding (colors, logo, typography) on top of base system

### 6.5 PWA Architecture

Web application with Progressive Web App capabilities:
- **Installable** on desktop (standalone window + taskbar icon), tablet, and phone
- **Offline-capable** via Service Workers + IndexedDB
  - App shell cached for instant load
  - Core operations (create, edit) queue locally as events
  - Sync automatically when connectivity returns
  - Event sourcing makes offline sync natural — offline actions are just events appended on reconnection
- **Online-only features:** Shipwright (needs LLM API unless local model), complex cross-Plank reports, Blueprint modifications, permission changes
- **Clear offline indicator** showing status and pending sync count

---

## 7. Plank Architecture (Module System)

### 7.1 Plank Structure

```
planks/
  inventory/
    blueprints/
      stock-item.blueprint.yaml
      warehouse.blueprint.yaml
      stock-movement.blueprint.yaml
    events/
      stock-adjusted.event.yaml
      restock-needed.event.yaml
      item-received.event.yaml
    workflows/
      receive-goods.workflow.yaml
      cycle-count.workflow.yaml
    views/
      overrides/
    tests/
      stock-movement.test.yaml
    README.md
```

Everything is YAML/markdown. Everything is human-readable. A Plank is a directory of Blueprints, event definitions, and workflow definitions. The Keel does the rest.

### 7.2 Inter-Plank Communication

Planks don't import from each other. They declare relationships through the knowledge graph:

```yaml
# planks/invoicing/blueprints/invoice-line.blueprint.yaml
relations:
  product:
    type: many_to_one
    target: inventory.StockItem
```

If the referenced Plank isn't installed:
- Fall back to freeform text field
- Shipwright suggests installing the missing Plank

Planks are independent but interconnected. Install Invoicing without Inventory, but adding Inventory later creates the connection automatically.

### 7.3 Core Planks (Phase 1)

| Plank | What It Tests |
|-------|--------------|
| **Contacts** | Basic entities, relationships, search |
| **Inventory** | Event sourcing, computed state, triggers |
| **Invoicing** | Financial transactions, ACID, cross-Plank references |

### 7.4 Future Planks (Post-Phase 1)

| Plank | Key Challenge |
|-------|--------------|
| Sales/Quoting | Workflow engine (quote → order → invoice) |
| Purchasing | Reverse invoicing flow, supplier management |
| Manufacturing/BOM | Complex entity hierarchies, production scheduling |
| Accounting | Double-entry bookkeeping, chart of accounts |
| HR | Sensitive data isolation, payroll |
| Reporting | Cross-Plank aggregation, ultimate interconnectivity test |

---

## 8. Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Backend | Python (FastAPI) | Async, fast, AI ecosystem, team expertise |
| Database | PostgreSQL | All-in-one: relational data, event store, knowledge graph (ltree) |
| Frontend | TypeScript + framework TBD | PWA, offline-capable, responsive |
| AI Gateway | LiteLLM or custom | Provider-agnostic LLM routing |
| Deployment | Docker Compose | Single-command self-hosting |
| Blueprints | YAML | Human-readable, AI-writable, git-friendly |

### 8.1 Deployment Architecture

```
┌─────────────────────────────────────────┐
│              Theseus Instance            │
│                                         │
│  ┌──────────┐  ┌──────────────────────┐ │
│  │ Frontend  │  │   Backend (FastAPI)  │ │
│  │ (PWA)     │◄─►  Blueprint Engine   │ │
│  └──────────┘  │  Schema Engine       │ │
│                │  Event Store          │ │
│                │  Knowledge Graph      │ │
│                │  Shipwright           │ │
│                │  Drydock              │ │
│                └─────────┬────────────┘ │
│                          │              │
│                ┌─────────▼────────────┐ │
│                │   PostgreSQL         │ │
│                │  (all data stores)   │ │
│                └──────────────────────┘ │
└─────────────────────────────────────────┘
```

**Self-hosting target:**
```bash
docker compose up -d
```

Two containers: the app + PostgreSQL.

### 8.2 Project Structure

```
theseus/
  keel/
    blueprint_engine/
    schema_engine/
    event_store/
    knowledge_graph/
    llm_gateway/
    drydock/
    auth/
  shipwright/
    modes/
    tools/
    prompts/
    context/
  planks/
    contacts/
    inventory/
    invoicing/
  hull-ui/
    design-system/
    generators/
    shells/
  docker/
  docs/
  tests/
```

---

## 9. Build Sequence (Hybrid Approach)

### Phase 1: Thin Keel (4–6 weeks)
- Blueprint parser and validator
- Schema engine (generates real PostgreSQL tables from YAML)
- Event store skeleton (append, replay, basic subscriptions)
- Knowledge graph bootstrap (ltree setup, basic traversal)
- LLM abstraction layer (at least one provider working)
- Auth foundation (Crew roles, Plank scopes)

### Phase 2: Parallel Plank Development
Build 3 Planks simultaneously to stress-test the Keel:
- **Contacts** — basic entities, relationships, search
- **Inventory** — event sourcing, computed state, triggers
- **Invoicing** — financial transactions, ACID, cross-Plank refs

### Phase 3: Integration Point
- Connect the three Planks through the knowledge graph
- An invoice references a Contact AND Inventory items
- This is the critical test of interconnectivity

### Phase 4: Shipwright Integration
- Build the Shipwright with Operator mode first (daily use)
- Add Architect mode (Blueprint generation from conversation)
- Add Mentor mode (user onboarding)
- Add Analyst mode (reporting and insights)

### Phase 5: Adaptive Interface
- Build the Hull design system
- Blueprint-to-UI generation pipeline
- Conversational mode (default experience)
- Command bar and panel modes
- Progressive density system
- PWA setup (Service Worker, offline queue, sync)

### Phase 6: The Drydock
- Import adapter framework
- Shipwright-led discovery flow
- Sea Trial infrastructure (reconciliation, confidence dashboard)
- Commissioning workflow

### Phase 7: The Shipyard (Future)
- Marketplace infrastructure
- Blueprint publishing and discovery
- Community contribution workflows

---

## 10. Business Model

### 10.1 License

AGPL v3 — all features free and open source. Anyone who modifies and hosts it as a service must share modifications.

### 10.2 Revenue Streams

| Tier | Price | What You Get |
|------|-------|-------------|
| **Self-hosted** | Free forever | Full ERP, local AI models, community support |
| **Cloud-hosted** | ~$49–199/mo | Managed instance, backups, updates, SSL, monitoring |
| **AI Plus** | ~$29–99/mo add-on | Frontier model access (Claude, GPT) for stronger Shipwright |
| **The Shipyard** | Revenue share | Community-built Blueprints, integrations, industry packs |

**Philosophy:** Monetize convenience, not features. Self-hosters are never punished.

---

## 11. Testing Strategy

- **Keel unit tests** — each subsystem in isolation
- **Blueprint validation tests** — suite of valid and invalid Blueprints
- **Plank integration tests** — YAML-defined, run against real database
- **Shipwright tests** — conversation scenarios with expected tool calls
- **Event replay tests** — verify replaying events produces correct state
- **Migration tests** — verify schema changes are non-destructive and reversible
- **Offline sync tests** — verify queued events resolve correctly after reconnection

---

## 12. Open Questions for Implementation Planning

- Specific frontend framework (React, Vue, Svelte)
- Knowledge graph: ltree vs Apache AGE vs other PostgreSQL graph extension
- Event store partitioning strategy
- Shipwright prompt engineering approach and testing methodology
- The Hull design system: build custom vs adopt/extend existing (Radix, Shadcn, etc.)
- CI/CD pipeline design
- Documentation platform for open-source community
- Blueprint behavior expression language — how triggers like `current_stock < reorder_point` are parsed and evaluated
- Inter-Plank fallback migration — when a referenced Plank isn't installed and data is entered as freeform text, how is that data mapped to structured entities when the Plank is later installed?
- Shipwright quality-aware routing criteria — what defines "complex" vs "simple" tasks for model selection
- Progressive density tracking — how the system measures user experience level to adjust UI density
- Offline conflict resolution strategy — when the same entity is modified both online and offline before sync
