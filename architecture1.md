# Frontend Architecture (Zephyr Test Case UI)

## Goal

Build an internal, org-wide web UI for **Zephyr regression test cases** on top of the existing FastAPI backend:

- Search and review existing test cases
- Impact analysis for regression scope (Phase 4)
- Summarize coverage + identify gaps
- Coverage report (Phase 16)
- Quality report (Phase 17: duplicates/stale/incomplete)
- Generate new test cases from a test plan (future: push back to Zephyr)

Key requirement: **future Okta SSO** without exposing access tokens in the browser.

---

## Delivery Plan (Day 1 vs Day 2)

### Day 1: Functionality First (Local, No Auth)
- **Framework**: Vite SPA (React + TypeScript), aligned with `cron-job-frontend`.
- Run UI + API locally with **no Okta/JWT** and **no route protection**.
- Prioritize building the 6 screens and validating end-to-end UX with real data:
  - Search → Summarize/Gaps
  - Coverage → Quality
  - Generate Test Cases (create/review flow)
- Keep API calls simple: UI calls FastAPI endpoints directly (or via a dev proxy).
- Architectural guardrails (to keep Day 2 easy):
  - All HTTP calls go through **one** `apiClient` module (no direct fetch/axios in pages).
  - Prefer relative URLs like `/api/v1/...` (so a future gateway can proxy without rewriting UI).
  - No tokens stored in browser (no `localStorage`/`sessionStorage` auth logic).
  - No workflow restrictions: QA can generate and use features freely.

### Day 2: Security Hardening (Okta + Protected Backend)
- Add a **BFF/Auth Gateway (Next.js)** in front of the SPA to integrate with Okta.
- Token-safety goal: **no access tokens in browser storage**.
  - Browser stores only an **httpOnly session cookie** issued by the BFF.
  - Okta token exchange/refresh happens **server-side** in the BFF.
  - SPA calls same-origin `/api/...` with cookies; BFF calls FastAPI server-to-server.
- Add backend authorization for protected endpoints (roles/groups).
- Enable route protection (Settings/Admin, and future write actions like push-to-Zephyr once implemented).

### Day 3: Review Workflow + Controlled Push (Enterprise)
- Add a “Draft → Review → Approve → Push” workflow for generated test cases:
  - QA1 generates and saves a draft (relational DB)
  - QA1 requests review from QA2 (access limited to creator + requested reviewers)
  - QA2 reviews and either requests changes or approves (approval is **per draft**; feedback can be per test case)
  - “Push to Zephyr” is enabled only after approval
- Add audit trail (who generated/reviewed/approved/pushed).

---

## Frontend Development Phases (Smallest Units)

This is the recommended development breakdown for the UI build, optimized for incremental delivery and review.

### Phase 0: Project + UI Foundations (Day 1)
- ✅ 0.1 Create the web app (Vite SPA + React + TypeScript)
- ✅ 0.2 Add Tailwind CSS + theme tokens (light/dark)
- ✅ 0.3 Add shadcn/ui and baseline components (button/input/select/table/tabs/dialog/badge)
- ✅ 0.4 Add env config for local API base URL (e.g., `VITE_API_URL` or relative `/api`)
- ✅ 0.5 Add a single typed API client module + normalized error handling

### Phase 1: App Shell (Day 1)
- ✅ 1.1 Header + sidebar + responsive layout (mobile sidebar overlay)
- ✅ 1.2 Left navigation (6 routes): Search, Summarize/Gaps, Coverage, Quality, Generate, Settings/Admin
- ✅ 1.3 Global loading + empty/error states (toast/snackbar optional)

### Phase 2: Data Layer + URL State (Day 1)
- ✅ 2.1 TanStack Query provider + request caching defaults
- ✅ 2.2 URL-driven filters (shareable URLs; back/forward works)
- ✅ 2.3 Export helpers (download JSON of current response)

### Phase 3: Search (Zephyr Corpus) (Day 1)
- ✅ 3.1 Unified input: change description / user story
- ✅ 3.2 Zephyr scope filters: `zephyr_root_folder`, `zephyr_team`, `zephyr_module`, `zephyr_folder_path_prefix`, `feature`
- ✅ 3.3 Results table (TanStack Table): sort + column toggles (MVP)
- ✅ 3.4 Test case details drawer/modal + “Open in Zephyr” link
- ✅ 3.5 Section A: Impacted Regression TCs (Phase 4B) via `POST /api/v1/impact/analyze`
- ✅ 3.6 Section B: Similar TCs (Context) (Phase 4) via `POST /api/v1/search` (`source_filter: "zephyr"`)

### Phase 4: Summarize / Gaps (Day 1)
- ✅ 4.1 “Summarize results” action (summarize the current search results payload)
- ✅ 4.2 Style selector: `concise | detailed | bullet`
- ✅ 4.3 Render summary + gaps + optional metrics

### Phase 5: Coverage Report (Phase 16) (Day 1)
- ✅ 5.1 Filters + call `GET /api/v1/reports/coverage`
- ✅ 5.2 Coverage breakdown tables (priority/status/type)
- ⏳ 5.3 Charts (Recharts) for quick scan (optional Day 1; required before org-wide rollout)

### Phase 6: Quality Report (Phase 17) (Day 1)
- ✅ 6.1 Filters + call `GET /api/v1/reports/quality`
- ✅ 6.2 Tabs: Duplicates / Stale / Incomplete
- ✅ 6.3 Deep links for each issue to Zephyr URLs

### Phase 7: Generate Test Cases (Day 1 core + Day 2 extensions)
- ✅ 7.1 Wizard input: test plan/user story/acceptance criteria
- ✅ 7.2 Options: `num_testcases`, `include_negative`, optional `component` (feature context)
- ✅ 7.3 Render generated TCs + allow basic edits + export JSON
- ⏳ 7.4 Push to Zephyr (Day 3 approval-gated; not available on Day 1/Day 2)

### Phase 8: Settings/Admin (Day 1: read-only)
- 8.1 Status panels: `/api/v1/health`, `/api/v1/stats`
- 8.2 Read-only configuration summary (models/styles/limits)

### Phase 9: Security + Deployment (Day 2)
- 9.1 Okta login via BFF session (httpOnly cookie), no tokens in browser storage
- 9.2 Protect routes: Settings/Admin + generation/push + admin-only screens
- 9.3 Deploy UI + API behind the same gateway (no CORS pain)

### Phase 10: Impact Page (Enterprise) (Future)
- 10.1 Dedicated Impact page (power workflow) for saved runs/history
- 10.2 Export/share impact runs (JSON/CSV) + stable share links
- 10.3 Audit trail metadata (who ran, when, parameters) (ties into Day 3/enterprise governance)

## Product Requirements (MVP)

### Navigation (Left Sidebar)
1. **Search** (Impact + Similar)
2. **Summarize / Gaps**
3. **Coverage Report**
4. **Quality Report**
5. **Generate Test Cases**
6. **Settings / Admin**

### Screens (MVP behavior)

**1) Search**
- Single input: change description / user story (copy-paste from PR/ticket/release note)
- On submit, run two calls and show two sections on the same page (no tab switching):
  - **Section A (primary): Impacted Regression TCs** via `POST /api/v1/impact/analyze`
  - **Section B (secondary): Similar TCs (Context)** via `POST /api/v1/search` (`source_filter: "zephyr"`)
- Filters: root/team/module/feature/folder prefix
- Result lists/tables include: `test_key`, `test_name`, `priority`, `status`, `relevance/similarity`, Zephyr URL
- Open a test case details drawer/modal + “Open in Zephyr” deep link

**Future enhancement**
- Add a dedicated **Impact Analysis** page only for “power” workflows (saved runs, export, audit history, approvals).

**2) Summarize / Gaps**
- Use the same filters/query as Search
- Run summarization on retrieved results
- Show summary + gaps list + optional coverage metrics

**3) Coverage Report**
- Filters: `zephyr_root_folder`, `zephyr_team`, `zephyr_module`, `zephyr_folder_path_prefix`, `feature`
- Display counts + simple charts (priority/status/type) + last updated

**4) Quality Report**
- Filters: same scope as coverage
- Controls: `min_similarity`, `stale_days`, include toggles
- Display tabs: Duplicates / Stale / Incomplete

**5) Generate Test Cases**
- Wizard flow:
  - Input: Test plan/user story/acceptance criteria
  - Options: number of cases, include negative/edge
  - Output: editable generated testcases list + coverage summary
  - Save/export result (future: push to Zephyr when enabled)

**6) Settings / Admin**
- Model/config visibility (read-only)
- Access/roles view (future: Okta groups mapping)
- System status panels (optional): `/api/v1/health`, `/api/v1/stats`

---

## Technology Choices (Recommended)

### Day 1 (Selected): Vite SPA (React + TypeScript)

**Why**
- Fastest iteration and simplest mental model for a dashboard-style internal tool.
- Matches `cron-job-frontend` patterns (React Router, Tailwind, tables, pages).
- No server-side concepts needed on Day 1 (auth is explicitly deferred).

**Frontend/Web App**
- **Vite** + **React** + **TypeScript**
- Routing: **react-router-dom**
- Styling: **Tailwind CSS**
- Components: shadcn-style components (Radix primitives + Tailwind)
- Forms: **react-hook-form** + **zod**
- Data fetching: **TanStack Query**
- Tables: **TanStack Table**
- Charts: **Recharts** (start) / ECharts (later if needed)

### Day 2 (Selected): BFF/Auth Gateway for Okta (token-safe)

**Why**
- Keeps OAuth access tokens out of browser storage.
- Enables Okta SSO and route protection without rewriting Day 1 pages.

**How**
- Add a Next.js gateway BFF service that:
  - performs Okta OIDC code exchange server-side
  - stores tokens server-side
  - issues an **httpOnly session cookie** to the browser
  - proxies `/api/v1/*` to FastAPI server-to-server

**Token safety**
- Browser stores only an **httpOnly cookie** (JS cannot read it).
- No access tokens in `localStorage`/`sessionStorage`.

**Implementation options**
- ✅ **Selected**: Next.js gateway (App Router route handlers + Auth.js) in a separate `gateway/` service.
- Alternative: Node/Express gateway (Okta SDK + session store).

## Selected Approach (Day 1 + Day 2)

### Selected for Day 1: Vite SPA
- **Vite + React + TypeScript**, following the structure and styling approach of `cron-job-frontend`.
- Goal: deliver all functional screens quickly (no auth).

### Selected for Day 2: BFF/Auth Gateway for Okta
- Add a **Next.js gateway** service to:
  - handle Okta login (OIDC code flow)
  - store tokens server-side (session store)
  - issue an **httpOnly session cookie** to the browser
  - proxy `/api/v1/*` to FastAPI (same-origin), attaching identity server-to-server
- Outcome: **no access tokens stored in browser storage**; JS cannot read the session cookie.

## Integration with Existing Backend API

### Day 1 (Vite SPA)
- SPA calls FastAPI directly during local development (or via a Vite dev proxy).
- Use a single `apiClient` and keep endpoints centralized.

### Day 2 (BFF/Auth Gateway)
- SPA calls same-origin routes served by the BFF (e.g., `/api/v1/*`).
- BFF proxies to FastAPI and handles Okta/session server-side.

This avoids CORS and keeps tokens out of browser storage.

### Alignment with `docs/ZEPHYR_INGESTION_PLAN.md`

This UI is designed around the three workflows described in the plan:
- **IMPACT ANALYSIS** (Phase 4)
- **NEW Module** generation (Phases 6–14)
- **EXISTING Module** analysis (Phases 15–17)

| Workflow | Plan Phase | UI Screen | Backend Endpoint |
|----------|------------|-----------|------------------|
| Impact analysis | Phase 4B | Search (Section A: Impacted) | `POST /api/v1/impact/analyze` |
| Zephyr search corpus | Phase 4 | Search (Section B: Similar/Context) | `POST /api/v1/search` (`source_filter: "zephyr"`) |
| Gap summarization | Phase 15 | Summarize / Gaps | `POST /api/v1/search/summarize` |
| Coverage metrics | Phase 16 | Coverage Report | `GET /api/v1/reports/coverage` |
| Quality checks | Phase 17 | Quality Report | `GET /api/v1/reports/quality` |
| TC generation | Phase 7 | Generate Test Cases | `POST /api/v1/testcases/generate` |
| Push to Zephyr | Phase 12–13 | Day 3 Review workflow | `POST /api/v1/testcases/push` (enabled only after approval) |

**Day 1 scope note**
- All endpoints are called without auth (local development).
- Push-to-Zephyr is not available on Day 1; it is introduced on Day 3 with an approval gate.

### Endpoint Notes (UI responsibilities)

**Search (Unified entry)** → `POST /api/v1/impact/analyze` + `POST /api/v1/search`
- Primary result set (impact): `POST /api/v1/impact/analyze`
  - UI sends `change_description`, `top_k`, `min_score`.
  - Keep `include_reasoning=false` by default on Day 1 (faster/cheaper); enable later as an option.
- Secondary result set (context): `POST /api/v1/search`
  - UI sets `source_filter: "zephyr"`.
  - UI sends `query` (reuse change description by default), `max_results`, `min_score`.

**Summarize / Gaps** → `POST /api/v1/search/summarize`
- UI passes `query` + the `results` it got from search.
- UI can provide `style` ("concise" | "detailed" | "bullet") and `include_metrics`.

**Coverage Report** → `GET /api/v1/reports/coverage`
- UI builds query params: `zephyr_root_folder`, `zephyr_team`, `zephyr_module`, `zephyr_folder_path_prefix`, `feature`, `component`, `limit`.
- Note: backend maps `component` → `feature` if `feature` is not provided.

**Quality Report** → `GET /api/v1/reports/quality`
- UI builds query params: same scope filters + `min_similarity`, `stale_days`, include toggles, `component`, `limit`.
- Note: backend maps `component` → `feature` if `feature` is not provided.

**Generate Test Cases** → `POST /api/v1/testcases/generate`
- UI sends `user_story`, `acceptance_criteria`, `num_testcases`, `include_negative`, optional `component` (maps to feature).

---

## Current Implementation Status (Backend vs Frontend)

### Backend (already implemented in this repo)
- ✅ Search: `POST /api/v1/search` (use `source_filter: "zephyr"` for Zephyr corpus)
- ✅ Summarize/Gaps: `POST /api/v1/search/summarize` (supports `style`: concise/detailed/bullet)
- ✅ Coverage report: `GET /api/v1/reports/coverage`
- ✅ Quality report: `GET /api/v1/reports/quality`
- ✅ Impact analysis: `POST /api/v1/impact/analyze`
- ✅ Generation: `POST /api/v1/testcases/generate`
- ✅ Push (deferred in UI): `POST /api/v1/testcases/push` (introduced on Day 3 after approval gate)

### Frontend (in progress)
- ✅ Phase 0: Vite SPA + React + TypeScript scaffold (`web/`)
- ✅ Phase 0: Tailwind theme tokens (light/dark)
- ✅ Phase 0: Baseline UI components (button/input/select/table/tabs/dialog/badge)
- ✅ Phase 0: Env config (`VITE_API_URL`, `VITE_API_BASE_PATH`)
- ✅ Phase 0: Typed `apiClient` + normalized error handling
- ✅ Phase 1: UI shell + routing + sidebar (responsive)
- ✅ Phase 2: TanStack Query provider + caching defaults
- ✅ Phase 2: URL-driven state + export JSON helpers
- ✅ Phase 3: Search (impact + similar) wired
- ✅ TanStack Table (results tables + column toggles)
- ✅ Zephyr deep links (Open in Zephyr)
- ✅ Phase 4: Summarize / gaps (summary + metrics)
- ✅ Phase 5: Coverage report (filters + breakdown tables)
- ✅ Phase 6: Quality report (tabs + issues + links)
- ⏳ Recharts for Coverage/Quality visuals
- ⏳ React Hook Form + Zod for generation wizard forms

---

## Security Model

### MVP (Internal-only)
- Deploy behind an internal gateway
- Restrict by network or VPN
- Optional: basic role separation inside the app

### Future (Okta SSO, recommended design)
- Okta login handled by the Next.js BFF/Auth Gateway
- Browser stores only an **httpOnly session cookie**
- Gateway proxies calls to FastAPI and injects identity server-to-server
- Authorization uses Okta **groups** mapped to app roles:
  - `admin` (settings, exports, future push)
  - `qa_lead` (generate, approve flows)
  - `viewer` (search + reports)

---

## Deployment (Simple)

Deploy a simple local setup for Day 1, then 2 services for Day 2:

- **Day 1 local**:
  - **Web**: Vite dev server
  - **API**: FastAPI

- **Day 2 (org-wide)**:
  - **Gateway (Next.js)**: serves the Vite static build + Okta session + API proxy
  - **API**: FastAPI (current repo)

Environment variables (web, Day 1):
- `VITE_API_URL` (FastAPI base URL for local dev) or use a Vite dev proxy with `/api`

Environment variables (gateway, Day 2):
- `OKTA_ISSUER`, `OKTA_CLIENT_ID`, `OKTA_CLIENT_SECRET`
- `SESSION_SECRET` (or equivalent for your gateway framework)
- `API_BASE_URL` (FastAPI internal URL for server-to-server proxy)

Environment variables (api):
- existing `.env` values (vector store, OpenAI, etc.)

---

## Testing

- Unit: component tests (React Testing Library)
- Integration: gateway proxy route tests (BFF routes) (Day 2)
- E2E (later): Playwright (login → search → report)

---

## Future Plan / Roadmap

### Short term
- Build UI MVP with the 6 left-nav screens
- Keep UI design aligned with `cron-job-frontend` (sidebar layout, Tailwind theme, table-heavy pages)
- Add “export JSON” buttons for reports (client-side download)

### Medium term
- Okta SSO (Auth.js + httpOnly session)
- Role-based access control (Okta groups → app roles)
- Saved views (persist filters) and shareable URLs
- Performance: pagination, table virtualization, caching

### Longer term
- Push-to-Zephyr workflow (Phases 10–14) re-enabled:
  - “Generate → Review → Push” with audit history
- Reporting exports (CSV/PDF), scheduled reports
- Admin audit logs for report usage and generation actions

---

## Open Points / Decisions (for discussion)

- ✅ **Impact page (future)**: add a dedicated Impact page later for saved runs/audit/export, while keeping Search as the primary entry.
- ✅ **Day 3 review workflow**: approval is per draft; feedback can be per test case.
