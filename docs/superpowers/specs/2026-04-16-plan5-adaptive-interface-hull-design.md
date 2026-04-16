# Plan 5: Adaptive Interface + The Hull — Design Spec

**Date:** 2026-04-16
**Status:** Draft
**Author:** Justin + Claude (brainstorming session)
**Depends on:** Plans 1, 2, 4 (all complete)

---

## 1. Overview

Plan 5 builds the Theseus frontend — a React application that makes the backend usable by real humans. The interface is **chat-first**: new users land in a full-screen Shipwright conversation, and traditional data views emerge from use rather than being predefined.

The central architectural piece is the **Blueprint-to-Component rendering pipeline**, a two-layer system that interprets View Definitions (YAML/JSON layout configs) into composed React components, with an AI-generated component layer for novel visuals and operations that the predefined library can't express.

This plan also designs (but only partially implements) a **Workflow Engine** — a new Keel subsystem that lets the Shipwright create automations, triggers, and multi-step business processes from conversation.

### 1.1 What's in v1

- Chat-first interface with three stages (pure chat → inline data → split view)
- The Hull design system (Shadcn/Radix/Tailwind, dark+light themes, 3 density levels)
- Blueprint-to-Component rendering pipeline (interpreted layer + generated layer with sandbox)
- View Definitions as first-class artifacts (saved, versioned, editable via Shipwright)
- Emergent navigation (dock, Cmd+K command bar, breadcrumbs)
- Hybrid routing (conversation URLs + data view URLs)
- Typed API client with Blueprint-aware dynamic hooks
- Backend additions: auth endpoints, Blueprint introspection, filtering/pagination, WebSocket streaming, View CRUD, entity delete
- Workflow Engine: full design, manual triggers implemented

### 1.2 What's NOT in v1

- PWA offline support (Service Workers, IndexedDB, sync)
- Event/schedule/condition workflow triggers
- The Shipyard (marketplace)
- Business branding customization (custom colors, logos)
- Multi-language / i18n
- Multi-crew real-time sync (WebSocket push for other users' changes)

---

## 2. Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Framework | React 19 + Vite | Runtime component composition for Blueprint-driven UI; Vite for fast dev without SSR overhead |
| Language | TypeScript (strict) | Type safety for dynamic component system |
| Routing | React Router v7 | Hybrid routing (conversation + data view URLs) |
| Styling | Tailwind CSS v4 + Radix UI | Shadcn pattern — owned components, accessible primitives, utility-first styling |
| Server State | TanStack Query | API caching, refetching, optimistic updates, cache invalidation |
| Client State | Zustand | UI mode, density, preferences, dock state |
| Charts | Recharts or Victory (TBD during implementation) | Composable React chart components |

---

## 3. Project Structure

```
hull-ui/
  src/
    components/             # The Hull design system components
      primitives/           #   Buttons, inputs, badges, modals, etc. (Shadcn-style)
      data/                 #   Tables, detail cards, lists, stat cards, charts
      chat/                 #   Chat bubbles, inline cards, action chips, typing indicator
      layout/               #   Grid, split panel, tabs, collapsible, stack
    engine/                 # The Blueprint-to-Component rendering pipeline
      interpreter/          #   View Definition → component tree (interpreted layer)
      sandbox/              #   AI-generated component runtime (generated layer)
      registry/             #   Component registry (maps type strings to React components)
    views/                  # The three interface stages
      conversation/         #   Stage 1: full-screen Shipwright chat
      split/                #   Stage 3: data panel + chat sidebar
      command-bar/          #   Cmd-K overlay
    api/                    # API client layer
      client.ts             #   Base fetch wrapper (auth headers, error handling, base URL)
      hooks/                #   TanStack Query hooks
        useEntities.ts      #     Dynamic CRUD for any Blueprint entity
        useShipwright.ts    #     Chat (POST + WebSocket streaming)
        useBlueprints.ts    #     Fetch Blueprint definitions
        useViews.ts         #     View Definition CRUD
        useAuth.ts          #     Login, session, crew member info
        useEvents.ts        #     Entity event history
    stores/                 # Zustand stores
      ui.ts                 #   Interface mode, density, dock items, theme
      auth.ts               #   JWT token, current crew member
    router/                 # React Router config
      routes.tsx            #   Route definitions + hybrid routing logic
      guards.tsx            #   Auth guards
    theme/                  # Design tokens, Tailwind config
      tokens.css            #   CSS custom properties (dark + light)
      tailwind.config.ts    #   Tailwind theme extension
  public/
  index.html
  vite.config.ts
  tsconfig.json
  package.json
```

---

## 4. The Rendering Pipeline (Two-Layer Architecture)

The rendering pipeline is the architectural spine of the frontend. All data views — whether predefined, Shipwright-generated, or AI-created — flow through it.

### 4.1 View Definitions

A View Definition is a JSON/YAML document that describes a screen. The Shipwright generates these from conversation, and users can save, modify, and share them.

**View Definition schema:**

```yaml
view:
  id: string                    # Unique identifier (e.g., "view_outstanding_invoices")
  name: string                  # Human-readable name
  route: string                 # URL path (e.g., "/invoicing/invoices/outstanding")
  created_by: string            # "shipwright" | "crew:{user_id}"
  version: integer              # Incremented on each edit
  layout:
    type: grid | stack | split | tabs
    columns?: integer           # For grid layout
    gap?: string                # Spacing between items
    areas:
      - component: string       # Component type from registry
        span?: integer          # Grid column span
        props?: object          # Static props passed to component
        data?:                  # Data binding
          source: string        # "{plank}.{entity}" reference
          filter?: object       # Field-value filter pairs
          sort?: object         # Field-direction pairs
          aggregate?: string    # count | sum | avg | min | max
          field?: string        # For aggregation — which field
          limit?: integer       # Max records
          include_relations?: string[]  # Related entities to join
        columns?: object[]      # For data_table — column definitions
        actions?: object[]      # Buttons/actions wired to tools or workflows
        children?: object[]     # Nested layout (recursive)
```

**View Definitions are stored server-side** via new backend endpoints and rendered client-side by the ViewInterpreter.

### 4.2 Layer 1: Interpreted Layer

The interpreted layer handles the standard case — mapping View Definition component types to React components from the Hull library.

**Rendering flow:**

```
View Definition (JSON)
    → ViewInterpreter
        → parses layout tree recursively
        → resolves each component type via ComponentRegistry
        → resolves data bindings via TanStack Query hooks
        → composes the React component tree
            → renders to the DOM
```

**ComponentRegistry:**

```typescript
// Maps component type strings to React components
const registry: Record<string, React.ComponentType<any>> = {
  // Data components
  data_table:     DataTable,
  detail_card:    DetailCard,
  stat_card:      StatCard,
  entity_list:    EntityList,
  timeline:       EventTimeline,

  // Visualization
  status_badge:   StatusBadge,
  progress_bar:   ProgressBar,
  chart_bar:      BarChart,
  chart_line:     LineChart,
  chart_pie:      PieChart,

  // Input
  entity_form:    EntityForm,
  action_button:  ActionButton,
  inline_edit:    InlineEdit,

  // Layout
  grid:           GridLayout,
  stack:          StackLayout,
  split:          SplitLayout,
  tabs:           TabsLayout,
  collapsible:    CollapsibleSection,

  // Contextual
  chat_panel:     ChatPanel,
  notification:   NotificationBanner,
};
```

The registry is extensible — new components can be added without modifying the interpreter.

**Data binding:** Each component in a View Definition can declare a `data` block. The ViewInterpreter translates this into TanStack Query hooks:

```
data:
  source: invoicing.Invoice
  filter: { status: overdue }
  sort: { due_date: asc }

→ useEntities("invoicing", "Invoice", {
    filter: { status: "overdue" },
    sort: { due_date: "asc" }
  })
```

Components receive data, loading state, and error state as props. They don't know or care where the data comes from.

### 4.3 Layer 2: Generated Layer (AI-Created Components)

When the interpreted layer can't express what the user needs, the Shipwright generates a custom React component.

**When this triggers:**
1. User requests a novel visual: "I need a drag-and-drop board showing jobs on machines"
2. Shipwright recognizes no matching component in the registry
3. Shipwright generates a React component (JSX + Tailwind + Hull design tokens)
4. Component is saved as a Custom Component artifact
5. View Definition references it as `custom/{component_id}`

**Custom Component schema:**

```yaml
custom_component:
  id: string                    # e.g., "cc_machine_job_board"
  name: string                  # Human-readable name
  created_by: shipwright
  promoted: boolean             # false = sandboxed, true = full access
  source: string                # React component source code (JSX)
  data_requirements:            # Declared data dependencies
    - source: string            # "{plank}.{entity}"
      filter?: object
  permissions:
    read: string[]              # Entities it can read
    write: string[]             # Entities it can modify (only after promotion)
```

**Sandbox Runtime:**

Generated components run in an isolated context that provides:
- Data access only through constrained hooks: `useEntityData(plank, entity, filter)` and `useEntityAction(plank, entity, action)`
- Hull design tokens and primitives (component looks consistent with the rest of the UI)
- Current theme (dark/light) automatically applied
- No access to: auth state, routing, other components' state, raw fetch, localStorage

**Sandboxed → Promoted:** A Helmsman can promote a custom component to full access. This exits the sandbox and grants write permissions. For a solo operator (who is the Helmsman), this is a single confirmation step.

**Error isolation:** If a generated component throws an error, the sandbox catches it and renders a fallback error card. The rest of the view continues to work.

### 4.4 How the Two Layers Connect

The ViewInterpreter treats both layers uniformly:

```
Component type: "data_table"
    → ComponentRegistry lookup → finds built-in DataTable → render directly

Component type: "custom/cc_machine_job_board"
    → ComponentRegistry lookup → finds custom component → wrap in SandboxRuntime → render
```

This means a single View Definition can mix built-in and custom components freely.

---

## 5. Chat-First Interface Flow

### 5.1 Stage 1: Conversational Mode (Full-Screen Chat)

The default experience. Users land here on first launch and for new conversations.

**URL:** `/c/new` (new conversation) or `/c/{conversation_id}` (existing)

**Layout:** Full-screen chat centered on the page (max-width for readability). Message input fixed at the bottom. Cmd+K hint in the footer.

**Shipwright greeting (first launch):**
The Shipwright introduces itself and asks about the business. This is the "Building your ship" experience — setup happens through dialogue, not a configuration wizard.

**Message types:**
- **User messages:** Right-aligned bubbles
- **Shipwright text:** Left-aligned bubbles with "Shipwright" label
- **Tool call cards:** Collapsible cards showing what the Shipwright did (created entity, updated record, etc.)
- **Inline data cards:** View Definition fragments rendered inside the chat flow (see Stage 2)

### 5.2 Stage 2: Inline Data Cards

Not a separate mode — an evolution of Stage 1. When the Shipwright returns data, it renders as interactive cards embedded in the conversation.

**Inline card types:**
- **Compact table:** 3-5 rows with key columns, "Open full view" link, "Show all" link
- **Entity summary:** Key fields for a single entity with quick-action buttons
- **Stat block:** Aggregated number with label (e.g., "4 Outstanding — $12,340")
- **Quick form:** Inline create/edit form for simple entities
- **Status indicator:** Visual status with context (e.g., "Inventory: 3 items below reorder point")

Inline cards are mini View Definitions — they use the same rendering pipeline but are constrained to chat-column width. Each card has an "Open full view" action.

### 5.3 Stage 3: Split View (Data Panel + Chat Sidebar)

Triggered by:
- Clicking "Open full view" on an inline card
- Navigating to a data URL directly (bookmark, back button, Cmd+K)
- Shipwright deciding to open a full view contextually

**Layout:**
- Data view panel: ~70% width (main content area)
- Chat sidebar: ~30% width (resizable via drag handle)
- Divider is draggable to resize
- Collapse button on chat sidebar → full-width data view (chat hidden, accessible via button)
- Expand button on chat sidebar → return to full-screen chat (Stage 1)

**URL transition:** When "Open full view" is clicked, the URL changes from `/c/{id}` to the data route (e.g., `/invoicing/invoices?status=overdue`). The conversation ID is preserved in session storage so the chat sidebar maintains context.

**Contextual chat:** The Shipwright is aware of the current view. If the user is looking at outstanding invoices, the Shipwright can proactively suggest actions ("Acme's invoice is 7 days overdue — want me to send a reminder?"). The Voyage Context layer includes the current route and view definition.

### 5.4 Breadcrumb Navigation

When in Stage 3, a breadcrumb trail appears at the top of the data panel:

```
Shipwright > Invoicing > Outstanding
```

- "Shipwright" links back to the conversation (Stage 1)
- Plank name links to the Plank's default entity list
- Current view name is the terminal breadcrumb

Breadcrumbs are built from navigation history, not a predefined hierarchy.

---

## 6. Navigation Model

### 6.1 Emergent Dock

No predefined sidebar or top nav at first launch. As users interact with Planks, a minimal **dock** appears.

**Dock behavior:**
- Appears after the user has visited at least 2 different Planks
- Positioned at the left edge, collapsed to icons only (expands on hover for labels)
- Items sorted by frequency of use (most used at top)
- Maximum 8 items visible (overflow in a "More" menu)
- Helmsman can pin items to the dock for all crew members
- Each dock item shows: Plank icon, Plank name (on hover), unread notification count

**Dock items link to:**
- The last View Definition the user had open for that Plank
- Or the Plank's default entity list if no view was saved

### 6.2 Command Bar (Cmd+K)

A search-and-action overlay available on any screen.

**Trigger:** `Cmd+K` (macOS) / `Ctrl+K` (Windows/Linux)

**Search scope:**
- Entities by name/ID across all Planks
- Plank names and entity types
- Saved View Definitions
- Recent conversations
- Available actions ("Create invoice", "Search contacts", "Run workflow")

**Behavior:**
- Results appear as the user types (fuzzy matching)
- Recent items shown by default (before typing)
- Results grouped by category (Entities, Views, Actions, Conversations)
- Selecting an entity opens its detail view (Stage 3)
- Selecting a view opens it (Stage 3)
- Selecting an action executes it (or opens a form)
- If no exact match: "Ask the Shipwright: {query}" option at the bottom — sends the query as a chat message

### 6.3 Hybrid Routing

| URL Pattern | What It Shows | Stage |
|-------------|--------------|-------|
| `/c/new` | New Shipwright conversation | 1 |
| `/c/{conversation_id}` | Existing conversation | 1 |
| `/{plank}/{entity}` | Entity list view | 3 |
| `/{plank}/{entity}?filter=...&sort=...` | Filtered/sorted entity list | 3 |
| `/{plank}/{entity}/{id}` | Entity detail view | 3 |
| `/views/{view_id}` | Saved View Definition | 3 |
| `/views/custom/{component_id}` | Custom component view | 3 |
| `/settings` | User preferences, density, theme | 3 |

**Browser behavior:**
- Back/forward buttons work naturally (React Router manages history)
- Refreshing restores the view (route + query params contain all state)
- Chat sidebar state (open/closed, conversation ID) persisted in `sessionStorage`
- Bookmarkable: any URL can be bookmarked and shared with crew

---

## 7. The Hull Design System

### 7.1 Design Tokens

All components reference tokens via CSS custom properties. Two token sets: dark (default) and light.

**Color tokens:**

```css
/* Semantic colors — used by all components */
--hull-bg-primary           /* Main page background */
--hull-bg-secondary         /* Cards, panels, elevated surfaces */
--hull-bg-elevated          /* Modals, command bar, popovers */
--hull-bg-input             /* Input field backgrounds */
--hull-text-primary         /* Main text */
--hull-text-secondary       /* Descriptions, labels */
--hull-text-muted           /* Placeholders, disabled text */
--hull-accent               /* Primary action color (Theseus blue) */
--hull-accent-hover         /* Primary action hover */
--hull-accent-subtle        /* Light accent background for highlights */
--hull-success              /* Positive states (paid, complete, active) */
--hull-warning              /* Caution states (approaching due, low stock) */
--hull-danger               /* Negative states (overdue, error, failed) */
--hull-info                 /* Informational states (sent, in progress) */
--hull-border               /* Default border color */
--hull-border-strong        /* Emphasized borders (focused inputs, active tabs) */
```

**Spacing scale:** 4px base unit — 1(4px), 2(8px), 3(12px), 4(16px), 6(24px), 8(32px), 12(48px), 16(64px)

**Border radius:** `sm`(4px), `md`(6px), `lg`(8px), `xl`(12px), `full`(9999px)

**Typography:**
- UI font: Inter (clean, readable at all sizes)
- Data/code font: JetBrains Mono (monospaced for IDs, amounts, codes)
- Scale: `xs`(11px), `sm`(13px), `base`(14px), `lg`(16px), `xl`(20px), `2xl`(24px)

**Shadows:** `sm`(subtle card elevation), `md`(dropdowns, popovers), `lg`(modals, command bar)

### 7.2 Theme Implementation

- Dark mode is the default
- Theme toggle in user preferences; also respects OS-level preference
- Implemented via Tailwind's `dark:` variant with `class` strategy
- Root element gets class `hull-dark` or `hull-light`
- All token values swap when the class changes
- Generated components in the sandbox receive theme tokens automatically via CSS inheritance

### 7.3 Progressive Density

Three density levels applied via a CSS class on the root element.

| Level | Root Class | Target User | Visual Changes |
|-------|-----------|------------|----------------|
| Comfortable | `hull-comfortable` | New users, setup | Larger text (base: 15px), generous padding, more whitespace, descriptive labels, helper text visible |
| Default | `hull-default` | Regular use | Standard spacing (base: 14px), full labels, balanced density |
| Compact | `hull-compact` | Power users | Tighter spacing (base: 13px), abbreviated labels, more rows per screen, keyboard shortcut hints visible, reduced padding |

**Density switching:**
- User manually selects in preferences
- The Shipwright suggests upgrades based on usage patterns (e.g., after consistent daily use for 2+ weeks)
- Per-view density override possible (a dashboard might always be compact regardless of global setting)

**Implementation:** Components read the density level from a Zustand store and apply the appropriate Tailwind classes. Density affects padding, font size, gap, and label display — not layout structure.

### 7.4 Component Library

Built as Shadcn-style owned components: Radix provides accessible interaction primitives, we own and style the component source code.

**Primitives (inputs & controls):**
- TextInput, NumberInput, Textarea
- Select, MultiSelect
- DatePicker, DateRangePicker
- Toggle, Checkbox
- EntityPicker (relation fields — searches entities in a referenced Plank)
- FileUpload (for Drydock imports, future)

**Display:**
- Badge, StatusBadge (color from Blueprint UI hints)
- Avatar (crew member display)
- Tooltip
- Skeleton (loading placeholder)
- EmptyState (friendly message + action when no data)

**Layout:**
- Card, Panel
- SplitView (resizable two-pane with drag handle)
- Grid (CSS Grid, responsive, configurable columns)
- Stack (vertical or horizontal flex)
- Collapsible (expandable section with header)
- Tabs (horizontal tab bar with content panels)
- Modal (centered overlay)
- Sheet (slide-in panel from right edge)

**Data:**
- DataTable (sortable columns, filterable, paginated, selectable rows, inline actions)
- DetailView (entity fields rendered from Blueprint, related entities, event timeline)
- StatCard (number + label + trend indicator)
- EventTimeline (chronological event list from Event Store)
- EntityForm (dynamic form generated from Blueprint fields — the core of the rendering pipeline)

**Chat:**
- ChatBubble (user and assistant variants, supports markdown rendering)
- InlineCard (mini View Definition rendered inside chat flow)
- ActionChip (quick-action button in Shipwright responses)
- ToolCallCard (collapsible summary of what the Shipwright did — tool name, args, result)
- TypingIndicator (animated dots while Shipwright is thinking)

**Navigation:**
- CommandBar (Cmd+K overlay with fuzzy search)
- Dock (left-edge icon strip with hover labels)
- Breadcrumb (navigation trail in Stage 3)

**Feedback:**
- Toast (bottom-right notification, auto-dismiss)
- AlertBanner (top-of-view persistent message)
- ConfirmDialog (destructive action confirmation with impact summary)

---

## 8. API Client Layer

### 8.1 Base Client

A typed fetch wrapper that handles:
- Base URL configuration (points to FastAPI backend)
- JWT token injection via `Authorization: Bearer` header
- Token refresh on 401 responses
- JSON serialization/deserialization
- Error normalization (API errors → typed error objects)

### 8.2 Blueprint-Aware Hooks

Entity hooks are dynamic — they accept plank and entity as parameters rather than being hardcoded per entity type.

```typescript
// Fetch a list of entities with optional filtering, sorting, pagination
useEntities(plank: string, entity: string, options?: {
  filter?: Record<string, any>,
  sort?: Record<string, "asc" | "desc">,
  limit?: number,
  offset?: number,
  include_relations?: string[],
})

// Fetch a single entity by ID
useEntity(plank: string, entity: string, entityId: string)

// Create a new entity (returns mutation hook)
useCreateEntity(plank: string, entity: string)

// Update an existing entity (returns mutation hook)
useUpdateEntity(plank: string, entity: string, entityId: string)

// Delete an entity (returns mutation hook)
useDeleteEntity(plank: string, entity: string, entityId: string)

// Fetch Blueprint definitions (for form generation, field type info)
useBlueprints()
useBlueprint(plank: string, entity: string)

// Shipwright chat
useShipwrightChat(conversationId?: string)
  // .sendMessage(text) → POST /api/v1/shipwright/chat
  // .messages → conversation history
  // .isLoading → Shipwright is thinking

// View Definition CRUD
useViews()
useView(viewId: string)
useSaveView()
useUpdateView(viewId: string)

// Auth
useLogin()
useCurrentUser()
useLogout()

// Events
useEntityEvents(entityType: string, entityId: string)
```

### 8.3 Cache Invalidation

When the Shipwright executes tool calls that modify data, the frontend must refresh affected views:

1. Shipwright chat response includes `tool_calls_executed` with plank/entity info
2. After processing the response, the chat hook invalidates TanStack Query caches for those entities:
   - `tool_calls_executed` contains `{ tool: "create_entity", arguments: { plank: "contacts", entity: "Contact" } }`
   - Invalidate all queries matching `["entities", "contacts", "Contact"]`
3. Any open data views showing those entities auto-refresh

This means if a user asks the Shipwright to create a contact while viewing the contacts table in split view, the table updates automatically.

---

## 9. Backend Additions Required

The current backend API needs these additions for the frontend to work.

### 9.1 Auth Endpoints

```
POST /api/v1/auth/register
  Body: { username, password, display_name }
  Response: { crew_member, token }
  Note: First registration creates a Helmsman. Subsequent registrations
        require an existing Helmsman's token.

POST /api/v1/auth/login
  Body: { username, password }
  Response: { crew_member, token }

GET /api/v1/auth/me
  Headers: Authorization: Bearer {token}
  Response: { id, username, display_name, role, plank_scopes }
```

### 9.2 Blueprint Introspection

```
GET /api/v1/blueprints
  Response: [{ plank, entity, version, description, fields, relations }]

GET /api/v1/blueprints/{plank}/{entity}
  Response: { plank, entity, version, description, fields, relations, behaviors, ui }
```

These endpoints expose Blueprint definitions so the frontend can generate forms, tables, and validation rules at runtime.

### 9.3 Enhanced Entity Endpoints

```
DELETE /api/v1/entities/{plank}/{entity}/{id}
  Response: 204 No Content

GET /api/v1/entities/{plank}/{entity}?filter[status]=overdue&sort=due_date:asc&limit=20&offset=0
  Response: { data: [...], total: number, limit: number, offset: number }
```

Filtering uses bracket notation: `filter[field]=value`. Multiple values for the same field: `filter[status]=sent,overdue`. Sorting: `sort=field:direction`. Pagination: `limit` + `offset` with total count in response.

### 9.4 View Definition Endpoints

```
GET /api/v1/views
  Response: [{ id, name, route, created_by, version }]

POST /api/v1/views
  Body: { View Definition JSON }
  Response: { id, ...full view definition }

GET /api/v1/views/{id}
  Response: { full view definition }

PUT /api/v1/views/{id}
  Body: { updated View Definition JSON }
  Response: { updated view definition }

DELETE /api/v1/views/{id}
  Response: 204 No Content
```

### 9.5 Custom Component Endpoints

```
GET /api/v1/components/custom
  Response: [{ id, name, created_by, promoted }]

POST /api/v1/components/custom
  Body: { name, source, data_requirements, permissions }
  Response: { id, ...full component }

GET /api/v1/components/custom/{id}
  Response: { full component including source }

PUT /api/v1/components/custom/{id}
  Body: { updated fields }
  Response: { updated component }

PATCH /api/v1/components/custom/{id}/promote
  Response: { component with promoted: true }
  Note: Helmsman-only
```

### 9.6 WebSocket for Shipwright Streaming

```
WS /api/v1/shipwright/stream
  Client sends: { message: string, conversation_id?: string }
  Server streams:
    { type: "token", content: "partial text" }        # Streaming text tokens
    { type: "tool_call", tool: "...", arguments: {} }  # Tool being called
    { type: "tool_result", tool: "...", result: {} }   # Tool execution result
    { type: "done", message: "full text", conversation_id: "..." }  # Final message
```

The existing POST endpoint remains for non-streaming use. The WebSocket endpoint enables real-time streaming of Shipwright responses for a more responsive chat experience.

### 9.7 Event Query Endpoint

```
GET /api/v1/events/{entity_type}/{entity_id}
  Query params: limit, offset
  Response: { data: [{ event_id, event_type, timestamp, actor, data }], total }
```

### 9.8 Workflow Endpoints (Manual Triggers Only for v1)

```
GET /api/v1/workflows
  Response: [{ id, name, trigger_type }]

POST /api/v1/workflows/{id}/execute
  Body: { input: { ...workflow input parameters } }
  Response: { execution_id, status, steps_completed, result }
```

---

## 10. Workflow Engine (Keel Subsystem — Design)

The Workflow Engine is a new Keel subsystem that executes multi-step business processes. It complements the Blueprint Engine (which defines data) and the Event Store (which records what happened) by defining **what should happen** in response to events and actions.

### 10.1 Workflow Definition Schema

```yaml
workflow:
  id: string                    # Unique identifier
  name: string                  # Human-readable name
  description: string           # What this workflow does
  created_by: string            # "shipwright" | "crew:{user_id}"
  version: integer

  trigger:
    type: manual | event | schedule | condition
    # Manual: triggered by a button click or Shipwright command
    label?: string              # Button label for manual triggers
    # Event: triggered when a specific event occurs
    event_type?: string         # e.g., "invoicing.Invoice.created"
    # Schedule: triggered on a cron schedule
    cron?: string               # e.g., "0 9 * * 1" (Mondays at 9am)
    # Condition: triggered when a field crosses a threshold
    entity?: string             # e.g., "inventory.StockItem"
    condition?: string          # e.g., "current_stock < reorder_point"

  input:                        # Required input parameters
    param_name:
      type: string | entity_ref | number | boolean | date
      source?: string           # For entity_ref: "{plank}.{entity}"
      required?: boolean
      default?: any

  steps:
    - id: string                # Step identifier (for referencing output)
      action: string            # Action type (see below)
      params: object            # Action-specific parameters
      on_error?: skip | fail | retry
```

### 10.2 Step Action Types

**Data actions (v1):**
- `get_entity` — fetch a single entity by ID
- `query_entities` — fetch a filtered list of entities
- `create_entity` — create a new entity
- `update_entity` — update entity fields
- `delete_entity` — soft-delete an entity

**Control flow (v1 — manual triggers only):**
- `condition` — if/else branching based on expression
- `loop` — iterate over a list of entities from a previous step

**Notification (v1 — basic):**
- `notify` — send an in-app notification to a crew member

**Future (post-v1):**
- `wait` — pause for time delay or approval
- `call_workflow` — invoke another workflow
- `shipwright_ask` — pause and ask the Shipwright for a judgment
- `email` — send email via configured SMTP
- `webhook` — call an external URL
- `generate_document` — produce a PDF (invoice, report, etc.)

### 10.3 Expression Language

Workflow steps reference previous step outputs and input parameters using Jinja2-style template expressions:

```
{{ input.invoice_id }}                    # Workflow input parameter
{{ get_invoice.result.status }}           # Output of a previous step
{{ get_invoice.result.total_amount }}     # Nested field access
{{ now() }}                               # Built-in function: current timestamp
{{ format_currency(amount, "USD") }}      # Built-in function: format number
{{ steps.get_items.result | length }}     # Filter: list length
```

Expressions are evaluated at runtime by the Workflow Engine. Only the declared input parameters and previous step outputs are available — no access to raw database or system internals.

### 10.4 Workflow Engine Architecture

```
keel/
  workflow_engine/
    models.py           # Workflow, Step, Trigger, Execution ORM models
    parser.py           # YAML → validated Workflow definition
    executor.py         # Runs workflow steps sequentially
    expressions.py      # Jinja2 expression evaluator (sandboxed)
    registry.py         # Loaded workflows indexed by ID and trigger type
    scheduler.py        # Cron-based trigger scheduling (post-v1)
```

**Execution model:**
1. Workflow is triggered (manual button click, Shipwright command, or future: event/schedule)
2. Executor creates an Execution record (tracks status, current step, outputs)
3. Steps run sequentially; each step's output is stored and available to subsequent steps
4. Expressions are evaluated against the accumulated context
5. On completion: final status recorded, event emitted to Event Store
6. On error: step's `on_error` policy determines behavior (skip, fail entire workflow, or retry)

### 10.5 How the Shipwright Creates Workflows

**Interpreted (standard):** Shipwright generates workflow YAML from conversation. The user says "When an invoice is overdue by 7 days, email the customer a reminder." Shipwright produces the YAML definition and saves it via the workflow endpoint.

**Generated (novel):** For complex business logic that doesn't fit the step-action DSL, the Shipwright can generate a custom step action (a Python function). This follows the same sandbox-first → Helmsman-promoted pattern as custom UI components.

### 10.6 Frontend Integration

Workflows appear in the UI as:
- **Action buttons** in View Definitions: `{ label: "Send Reminder", workflow: "wf_payment_reminder" }`
- **Workflow status cards** in the Shipwright chat (showing execution progress)
- **Workflow history** in entity detail views (which workflows have been run against this entity)

### 10.7 v1 Implementation Scope

- Workflow Definition schema and parser
- Workflow storage (PostgreSQL model + CRUD endpoints)
- Executor with data actions + condition + loop
- Manual trigger support (API endpoint + frontend action buttons)
- Basic in-app notifications
- Shipwright can generate workflow YAML from conversation
- **Deferred:** Event triggers, schedule triggers, condition triggers, wait steps, email, webhooks, document generation

---

## 11. Data Flow Architecture

### 11.1 Overall Data Flow

```
User Interaction (chat, click, form, Cmd+K)
    │
    ├─ Chat message ──────────→ useShipwright hook
    │                              → POST /api/v1/shipwright/chat (or WS /stream)
    │                              → Backend agent loop (LLM + tools)
    │                              → Response with message + tool_calls_executed
    │                              → Invalidate affected entity caches
    │                              → Chat UI updates + data views auto-refresh
    │
    ├─ Direct data action ────→ useCreateEntity / useUpdateEntity / useDeleteEntity
    │                              → POST/PATCH/DELETE to entity endpoint
    │                              → Optimistic update in TanStack Query cache
    │                              → Server confirms → cache finalized
    │
    ├─ View navigation ───────→ React Router
    │                              → Route matched → View Definition fetched
    │                              → ViewInterpreter renders component tree
    │                              → Each component's data hook fetches from API
    │
    └─ Workflow trigger ──────→ POST /api/v1/workflows/{id}/execute
                                   → Backend Executor runs steps
                                   → Response with execution result
                                   → Invalidate affected entity caches
```

### 11.2 State Architecture

```
┌──────────────────────────────────────────────────────────┐
│  SERVER STATE (TanStack Query)                           │
│  Entities, Blueprints, Views, Events, Conversations      │
│  Cached, auto-refetched, invalidated on mutations        │
├──────────────────────────────────────────────────────────┤
│  CLIENT STATE (Zustand)                                  │
│  UI mode (stage 1/2/3), density level, theme (dark/light)│
│  Dock items + order, command bar open/closed              │
│  Current conversation ID, chat sidebar width              │
│  Auth token, current crew member                          │
├──────────────────────────────────────────────────────────┤
│  URL STATE (React Router)                                │
│  Current route, query params (filters, sort, pagination)  │
│  Conversation ID (for Stage 1)                            │
├──────────────────────────────────────────────────────────┤
│  SESSION STATE (sessionStorage)                          │
│  Chat sidebar open/closed, active conversation per view   │
│  Dock expansion state                                     │
└──────────────────────────────────────────────────────────┘
```

Each state layer has a clear responsibility. No overlap, no ambiguity about where a piece of state lives.

---

## 12. Security Considerations

### 12.1 Authentication Flow

1. User visits Theseus → redirected to `/login` if no valid JWT in memory
2. First-ever user → `/register` creates a Helmsman account
3. Login → JWT stored in memory (not localStorage — XSS protection)
4. JWT included in all API requests via `Authorization: Bearer` header
5. Token refresh handled transparently by the API client
6. Logout clears in-memory token and redirects to `/login`

### 12.2 Generated Component Security

AI-generated components are the primary attack surface. Mitigations:

- **Sandbox isolation:** Generated components can only access data through constrained hooks. No raw fetch, no localStorage, no DOM manipulation outside their container.
- **CSP headers:** Content Security Policy prevents inline scripts and unauthorized resource loading.
- **Promotion gate:** Components start sandboxed (read-only data access). Helmsman must explicitly promote to enable write operations.
- **Source review:** Custom component source code is stored and viewable. Helmsman can inspect before promoting.
- **No eval():** Generated components are rendered via a controlled component loader, not `eval()`. The sandboxing mechanism is a React error boundary wrapping a restricted context provider. The context provider supplies only the constrained data hooks and Hull primitives — no globals, no window access, no raw DOM APIs. If stronger isolation is needed (e.g., untrusted third-party components from The Shipyard), iframe sandboxing can be added later without changing the component API.

### 12.3 Input Validation

- All user input validated on both frontend (Blueprint field types → form validation) and backend (existing Pydantic validation)
- Markdown rendering in chat uses a sanitizing renderer (no raw HTML injection)
- View Definition JSON validated against schema before rendering
- Workflow expressions evaluated in a sandboxed Jinja2 environment (no arbitrary Python execution)

---

## 13. Testing Strategy

### 13.1 Unit Tests

- Hull components: render correctly, handle all density levels, theme variants, loading/error states
- Rendering pipeline: ViewInterpreter produces correct component trees from View Definitions
- ComponentRegistry: correct mapping, graceful fallback for unknown types
- API hooks: correct query keys, cache invalidation logic
- Zustand stores: state transitions

### 13.2 Integration Tests

- Chat flow: send message → receive response → inline cards render → tool call cards show
- Split view transition: inline card "Open full view" → URL changes → data panel renders → chat sidebar shows
- Blueprint-driven forms: fetch Blueprint → generate form → validate inputs → submit → entity created
- Command bar: Cmd+K → type query → results appear → select result → navigation occurs
- Cache invalidation: Shipwright creates entity → table view auto-refreshes

### 13.3 E2E Tests

- Full user journey: first launch → Shipwright greeting → setup conversation → create entities → view data → split view → command bar
- Auth flow: register → login → access protected views → logout → redirect
- View Definition lifecycle: Shipwright generates view → saved → reload page → view restores
- Custom component: Shipwright generates component → sandboxed render → Helmsman promotes → full access

---

## 14. Implementation Notes

### 14.1 Build Order Recommendation

1. **Foundation:** Vite project setup, Tailwind config, design tokens, theme switching
2. **Hull primitives:** Core components (Button, Input, Card, etc.) with density support
3. **API client:** Base client + auth hooks + entity hooks
4. **Auth flow:** Login/register pages, JWT management, route guards
5. **Chat interface:** Stage 1 (full-screen chat), message rendering, Shipwright integration
6. **Inline cards:** Stage 2, mini View Definitions in chat
7. **Rendering pipeline:** ViewInterpreter + ComponentRegistry + data binding
8. **Data components:** DataTable, DetailView, EntityForm, StatCard
9. **Split view:** Stage 3, resizable panels, contextual chat
10. **Navigation:** Emergent dock, Command bar, breadcrumbs, hybrid routing
11. **View Definitions:** CRUD endpoints (backend) + save/load in frontend
12. **Generated layer:** Custom component sandbox, storage, promotion flow
13. **Workflow Engine:** Backend subsystem + manual trigger UI
14. **Progressive density:** 3 levels implemented across all components

### 14.2 Backend Changes Needed Before Frontend

These backend additions should be implemented first or in parallel with early frontend work:

1. Auth endpoints (register, login, me) — needed for any authenticated frontend page
2. Blueprint introspection endpoints — needed for the rendering pipeline
3. Entity filtering + pagination — needed for DataTable
4. Entity delete endpoint — needed for entity management
5. View Definition CRUD endpoints — needed for saving/loading views
6. WebSocket streaming — needed for responsive chat experience

### 14.3 Charting Library Decision

Deferred to implementation. Two candidates:
- **Recharts:** Most popular React charting library, composable, Tailwind-friendly
- **Victory:** More customizable, from Formidable, good for custom chart types

Decision should be made when implementing the first chart component based on what the rendering pipeline needs.
