# Product Frontend MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver one independent, locally runnable product front end for uploading a document, running hybrid research, and inspecting a sourced report, with a PRD and interaction map suitable for a product-manager portfolio.

**Architecture:** A React/TypeScript single-page client calls the existing FastAPI endpoints through a local Vite development proxy. Keep API keys, embedding, search, research state, and SQLite in the Python backend; keep the Streamlit client untouched. The running client doubles as the clickable prototype, with a separate annotated interaction map.

**Tech Stack:** React, TypeScript, Vite, CSS, Vitest/Testing Library for client tests, existing FastAPI/Pydantic/Python pytest backend.

**Spec:** `docs/2026-10-24-product-frontend-design.md`

## Global Constraints

- First update `CLAUDE.md` with the new `frontend/` directory and product-document placement/cleanup rules; only then create that directory.
- V1 front end exposes only the hybrid flow; backend `web` and `document` modes remain unchanged.
- Upload limits shown to users: 1–5 PDF/Markdown files, at most 10 MiB each and 30 MiB total. Backend remains authoritative.
- No fabricated stage-by-stage progress: `POST /research` is synchronous.
- Do not put API keys or uploaded document text in frontend source, build output, localStorage, or committed screenshots.
- Do not change `.env`, CI/CD, database schema, or push to GitHub without separate permission.
- Preserve user work in any dirty worktree; stage and commit only task files.

## Review Focus

1. Empty/whitespace topic or absent file must block both upload and research requests; Task 3 test.
2. Too many, wrong-extension, individual oversize, or total oversize files must show a useful message; Task 3 test.
3. A 422/503 HTTP error or network failure must not be displayed as a completed study; Task 2 and Task 3 tests.
4. HTTP 201 with `ResearchState.status="failed"` or missing report must show failure/no-report, not a successful report; Task 3 and Task 4 tests.
5. Double-click/ongoing submission and malicious/untrusted report content must not cause duplicate calls or raw HTML injection; Task 3 and Task 4 tests.

## File Map

- `CLAUDE.md`: new directory rules and verification commands; modified first.
- `docs/2026-10-24-product-frontend-prd.md`: concise PRD with persona, user story, scope, contract and acceptance.
- `docs/2026-10-24-product-frontend-interaction-map.md`: annotated wireframe/state map linked to clickable client.
- `frontend/package.json`, `frontend/package-lock.json`, `frontend/index.html`, `frontend/tsconfig*.json`, `frontend/vite.config.ts`: local client toolchain and `/api` development proxy; lockfile is committed.
- `frontend/src/types.ts`: wire types matching current `ResearchState`, `KnowledgeBaseSummary`, `Evidence`, `ResearchReport` fields used by UI.
- `frontend/src/api.ts`: `uploadKnowledgeBase(files: File[]): Promise<KnowledgeBaseSummary>` and `createHybridResearch(topic: string, knowledgeBaseId: string): Promise<ResearchState>`; one shared error translator.
- `frontend/src/App.tsx`, `frontend/src/components/ResearchForm.tsx`, `frontend/src/components/ReportView.tsx`, `frontend/src/styles.css`: single-page workflow, result presentation and responsive layout.
- `frontend/src/*.test.tsx`: API, form/state and report tests with mocked HTTP; no real providers.
- `README.md`, `docs/assets/`: first-run instructions and non-sensitive product screenshots after browser verification.

---

### Task 1: Product contract and workspace rules

**Files:** Modify `CLAUDE.md`; create `docs/2026-10-24-product-frontend-prd.md` and `docs/2026-10-24-product-frontend-interaction-map.md`.

**Interfaces:** Consumes current `api.py` request/response types and the approved spec. Produces exact UX copy, state transitions, and API mapping for later tasks.

- [ ] **Step 1:** Add `frontend/` placement, no-secret rule, generated `dist/`/`node_modules/` cleanup rule, and `docs/` PRD/prototype asset naming to `CLAUDE.md` before creating `frontend/`.
- [ ] **Step 2:** Write the PRD: target user, one hybrid user story, preconditions, upload/research/report sequence, empty/error/loading states, non-goals, and acceptance criteria from the spec.
- [ ] **Step 3:** Write the interaction map with an annotated desktop/narrow-screen wireframe, each control's action and the exact `POST /knowledge-bases` → `POST /research` mapping; mark the running client as the clickable prototype.
- [ ] **Step 4:** Verify `git diff --check` and manually compare every PRD acceptance criterion to the spec; expected: no missing core-flow or security boundary.
- [ ] **Step 5:** Commit only these three files with `docs: define hybrid research frontend MVP`.

### Task 2: Typed client and local frontend runtime

**Files:** Create the `frontend/` toolchain, `frontend/src/types.ts`, `frontend/src/api.ts`, `frontend/src/api.test.ts`, and a minimal `frontend/src/main.tsx`.

**Interfaces:** `uploadKnowledgeBase(files: File[]): Promise<KnowledgeBaseSummary>` posts `FormData` to `/api/knowledge-bases`. `createHybridResearch(topic: string, knowledgeBaseId: string): Promise<ResearchState>` posts JSON to `/api/research` with `retrieval_mode: "hybrid"`. Errors carry a safe user-facing message; no credentials are exposed.

- [ ] **Step 1:** Scaffold a local React+TypeScript Vite client with local npm dependencies and a versioned lockfile; configure `/api` proxy to backend `http://127.0.0.1:8000` without changing FastAPI CORS or CI.
- [ ] **Step 2:** Write failing API tests asserting FormData upload, exact hybrid JSON, 422/503 translation, and network-error translation; mock `fetch` and never contact providers.
- [ ] **Step 3:** Run `npm test -- --run src/api.test.ts`; expected: FAIL because the client functions are not implemented.
- [ ] **Step 4:** Implement wire types and the two API functions with response-status checks; never interpolate raw server tracebacks into UI messages.
- [ ] **Step 5:** Run `npm test -- --run src/api.test.ts` and `npm run build`; expected: all targeted tests pass and TypeScript/build exit 0.
- [ ] **Step 6:** Commit only toolchain and API-client files with `feat: add typed frontend API client`.

### Task 3: One hybrid submission workflow

**Files:** Create/modify `frontend/src/App.tsx`, `frontend/src/components/ResearchForm.tsx`, `frontend/src/App.test.tsx`; update the interaction map only if actual labels differ.

**Interfaces:** Consumes Task 2 API functions. Produces state `idle | uploading | researching | completed | failed`, plus a successful `ResearchState` passed to Task 4's `ReportView`.

- [ ] **Step 1:** Write failing UI tests for blank topic, absent/invalid/oversize files, duplicate click while pending, upload error, research HTTP error, `status="failed"`, and a successful one-upload/one-research sequence.
- [ ] **Step 2:** Run `npm test -- --run src/App.test.tsx`; expected: FAIL until the form and state transitions exist.
- [ ] **Step 3:** Implement controlled topic/file inputs, client-side limit checks, explicit upload and research loading copy, and one submission handler. Let the backend remain final validator. No fabricated per-stage progress.
- [ ] **Step 4:** Run targeted tests and `npm run build`; expected: all targeted tests pass, TypeScript/build exit 0.
- [ ] **Step 5:** Commit only form/App/tests and any matched interaction-map change with `feat: add hybrid research submission flow`.

### Task 4: Sourced report, responsive finish, and verification

**Files:** Create `frontend/src/components/ReportView.tsx`, `frontend/src/components/ReportView.test.tsx`, `frontend/src/styles.css`; update `frontend/src/App.tsx`, `README.md`; add only non-sensitive screenshots to `docs/assets/`.

**Interfaces:** `ReportView({state}: {state: ResearchState})` shows report, plan, Evidence and task usage. Markdown rendering must not enable raw HTML injection. Downloads derive only from returned `ResearchReport.markdown/html`.

- [ ] **Step 1:** Write failing report tests: web/document source metadata and links, plan content, Markdown/HTML download content, missing report, and raw HTML in untrusted report text not becoming an executable element.
- [ ] **Step 2:** Run `npm test -- --run src/components/ReportView.test.tsx`; expected: FAIL until the view exists.
- [ ] **Step 3:** Implement the report-first view, safe Markdown rendering, evidence drawer/tabs, download buttons and light responsive CSS. Preserve source IDs and metadata exactly; do not invent semantic fact-checking.
- [ ] **Step 4:** Run `npm test -- --run`, `npm run build`, and `.venv\Scripts\python.exe -m pytest -q`; expected: frontend suite/build and existing backend suite pass. If main checkout lacks `.venv`, use the existing project virtual environment with `PYTHONPATH=src` and verify import path.
- [ ] **Step 5:** Start local API/client with non-sensitive demonstration input; inspect desktop and narrow-screen layout and complete the real API upload → hybrid request → report path once. Record actual success/failure, source view and remaining limitations. Do not trigger real paid APIs without an explicit testing budget/approval; otherwise use a locally injected fake backend and label it as such.
- [ ] **Step 6:** Update README with how to run the new client, screenshots and evidence-bounded verification statement; run `git diff --check`; commit only V1 files with `feat: deliver product frontend MVP`.

## Final Audit

- [ ] Re-read the approved spec and check all V1 deliverables against it.
- [ ] Verify no `.env`, private document, generated `dist/`/`node_modules/`, database, or token is tracked or staged.
- [ ] Report implemented vs unverified boundaries; leave main/remote unchanged until the user separately approves integration/push.
