# Hybrid RAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a portfolio-ready hybrid RAG path that combines Tavily web search with private PDF/Markdown retrieval while preserving the existing bounded research workflow.

**Architecture:** Keep the native Python Agent and add a separate knowledge-base ingestion service plus a `DocumentRetriever` boundary. LangChain loads/splits documents, Qwen Embedding generates vectors, Chroma persists them, and both web/document candidates become the existing citation-safe `Evidence` before reflection and reporting.

**Tech Stack:** Python 3.11+, Pydantic 2, FastAPI, Streamlit, SQLite, LangChain Core/Text Splitters/Community/OpenAI/Chroma, PyPDF, Qwen Embedding API, Chroma, pytest

**Spec:** `docs/2026-10-19-hybrid-rag-design.md`

## Global Constraints

- Preserve the current `ResearchService → ResearchOrchestrator → ReportWriter → ResearchRepository` lifecycle.
- Support only PDF and Markdown in V1; do not add Word, OCR, accounts, queues, LangGraph, multi-Agent, or customer-service features.
- Use `qwen3.7-text-embedding-flash` with 1024 dimensions through the LangChain `Embeddings` interface.
- Use `chunk_size=800`, `chunk_overlap=120`, and Chinese-aware separators from the spec.
- Accept at most 5 files, 10 MiB per file, and 30 MiB total per knowledge-base creation.
- Preserve `web`, `document`, and `hybrid` modes; requests without new fields remain `web`.
- Preserve a single 12-Evidence cap and two research rounds.
- Never read, write, print, or commit the user's local `.env` or credential values.
- Preserve pre-existing uncommitted edits; stage only task-owned hunks, especially in the already modified `CLAUDE.md`.
- Keep uploaded files and Chroma indexes under ignored `data/knowledge_bases/`; never add them to Git.
- Migrate existing SQLite records transactionally; never delete the database and rebuild it.
- Automated tests use fakes and temporary directories; real API calls are limited to explicit smoke verification.
- Before any implementation step that deletes a failed staging directory or user file, stop for explicit user approval; failed staging data may instead remain quarantined and unreferenced.

## Review Focus

- A `document` or `hybrid` request with a missing/not-ready knowledge base must return 422, never silently fall back to another knowledge base (Task 7 test).
- An old SQLite database with web-only Evidence must migrate without row loss and still deserialize as `source_type="web"` (Task 3 test).
- A PDF/Markdown upload that fails midway must not expose a ready knowledge base or usable partial index (Task 5 test).
- A hybrid question where one provider fails must keep the other provider's Evidence, while two empty/failed sources must fail the task instead of generating an unsupported report (Task 6 tests).
- User filenames containing path traversal or duplicate normalized names must be rejected before any write outside the assigned knowledge-base directory (Task 5 tests).

---

## File Structure

### New production files

- `src/mini_researcher/embedding.py` — build the LangChain Qwen Embedding adapter from non-secret settings.
- `src/mini_researcher/retrieval.py` — `DocumentRetriever` protocol, retrieval errors, and Chroma implementation.
- `src/mini_researcher/knowledge.py` — upload value objects, document validation/loading/splitting, staging, manifest, and Chroma indexing.

### New test files

- `tests/test_embedding.py`
- `tests/test_retrieval.py`
- `tests/test_knowledge.py`

### Existing files to modify

- `CLAUDE.md`, `.gitignore`, `.env.example`, `pyproject.toml`
- `src/mini_researcher/config.py`, `models.py`, `evidence.py`, `orchestrator.py`, `service.py`, `repository.py`, `report.py`, `api.py`, `ui.py`
- `tests/fakes.py`, `test_config.py`, `test_models.py`, `test_evidence.py`, `test_orchestrator.py`, `test_service.py`, `test_repository.py`, `test_report.py`, `test_api.py`, `test_ui_smoke.py`
- `README.md`

## Task 1: Project Rules, Dependencies, and RAG Configuration

**Files:**
- Modify: `CLAUDE.md:15-24`
- Modify: `.gitignore:1-10`
- Modify: `.env.example`
- Modify: `pyproject.toml:10-26`
- Modify: `src/mini_researcher/config.py:5-20`
- Modify: `tests/test_config.py`

**Interfaces:**
- Consumes: existing `Settings` environment loading.
- Produces: validated settings `dashscope_api_key`, `dashscope_base_url`, `dashscope_embedding_model`, `dashscope_embedding_dimension`, `rag_top_k`, `rag_chunk_size`, and `rag_chunk_overlap`. The key remains optional at Settings construction and is required only when an Embedding-backed path is invoked.

- [ ] **Step 1: Register the knowledge-base storage rule before creating product directories**

Add `data/knowledge_bases/` to `CLAUDE.md` as ignored private runtime data containing documents, indexes, manifests, and quarantined failed staging directories. State that cleanup requires explicit user approval.

- [ ] **Step 2: Write failing configuration tests**

Add assertions equivalent to:

```python
assert settings.dashscope_embedding_model == "qwen3.7-text-embedding-flash"
assert settings.dashscope_embedding_dimension == 1024
assert settings.rag_top_k == 3
assert settings.rag_chunk_size == 800
assert settings.rag_chunk_overlap == 120
```

Also assert `rag_chunk_overlap < rag_chunk_size` and reject non-positive values.
Construct Settings without `DASHSCOPE_API_KEY` and assert existing web-only configuration still loads.

- [ ] **Step 3: Run the focused tests and confirm failure**

Run: `.venv\Scripts\python.exe -m pytest tests/test_config.py -q`

Expected: FAIL because the RAG fields do not exist.

- [ ] **Step 4: Add dependencies and settings definitions**

Add these bounded ranges to `pyproject.toml`:

```text
langchain-core>=1.6,<2
langchain-text-splitters>=1.1,<2
langchain-community>=0.4,<1
langchain-openai>=1.7,<2
langchain-chroma>=1.1,<2
pypdf>=6.21,<7
python-multipart>=0.0.32,<1
```

Update `.env.example` with names and safe non-secret defaults only. Do not modify `.env`.

- [ ] **Step 5: Install only into the existing project virtual environment**

Run: `.venv\Scripts\python.exe -m pip install -e ".[dev]"`

Expected: installation succeeds without creating another virtual environment or global packages.

- [ ] **Step 6: Verify configuration and dependency health**

Run: `.venv\Scripts\python.exe -m pytest tests/test_config.py -q`

Expected: PASS.

Run: `.venv\Scripts\python.exe -m pip check`

Expected: `No broken requirements found.`

- [ ] **Step 7: Commit**

```powershell
git add .gitignore .env.example pyproject.toml src/mini_researcher/config.py tests/test_config.py
git add -p CLAUDE.md
git commit -m "build: add hybrid rag dependencies and settings"
```

## Task 2: Unified Web and Document Evidence Models

**Files:**
- Modify: `src/mini_researcher/models.py:41-99`
- Modify: `src/mini_researcher/evidence.py:9-64`
- Modify: `src/mini_researcher/report.py:37-96`
- Modify: `tests/test_models.py`
- Modify: `tests/test_evidence.py`
- Modify: `tests/test_report.py`

**Interfaces:**
- Consumes: existing `SearchResult`, `ResearchQuestion`, and source numbering.
- Produces: `RetrievalMode`, `EvidenceSourceType`, `DocumentResult`, expanded `Evidence`, `EvidenceManager.add_search_results`, and `EvidenceManager.add_document_results`.

- [ ] **Step 1: Write failing model tests**

Cover these exact conditions:

```python
assert web.source_type == EvidenceSourceType.WEB
assert document.document_name == "handbook.pdf"
assert document.page_number == 12
```

Reject a web Evidence without an HTTP/HTTPS URL and a document Evidence without `document_name`. Accept Markdown Evidence with `page_number=None`.

- [ ] **Step 2: Run model tests and confirm failure**

Run: `.venv\Scripts\python.exe -m pytest tests/test_models.py -q`

Expected: FAIL because the new enums/fields/types do not exist.

- [ ] **Step 3: Implement the data contracts**

Add:

```python
class RetrievalMode(StrEnum):
    WEB = "web"
    DOCUMENT = "document"
    HYBRID = "hybrid"

class EvidenceSourceType(StrEnum):
    WEB = "web"
    DOCUMENT = "document"
class DocumentResult(BaseModel):
    document_name: str
    content: str
    page_number: int | None = None
    chunk_index: int
    score: float | None = None
```

Give `Evidence.source_type` a `WEB` default so existing web-only callers remain valid. Extend `ResearchState` with `retrieval_mode: RetrievalMode = WEB` and `knowledge_base_id: str | None = None`. Use one model-level validator on `Evidence` for source-specific requirements.

- [ ] **Step 4: Write failing EvidenceManager tests**

Test that webpage results and document results share consecutive IDs, document duplicates use `(document_name, page_number, chunk_index)`, and alternating mixed additions never exceed 12.

- [ ] **Step 5: Implement the two EvidenceManager entry points**

Keep the existing `add` method as a compatibility wrapper for web results until all callers migrate. Add exact signatures:

```python
def add_search_results(
    self, question: ResearchQuestion, results: list[SearchResult]
) -> list[Evidence]

def add_document_results(
    self, question: ResearchQuestion, results: list[DocumentResult]
) -> list[Evidence]
```

- [ ] **Step 6: Write and implement document reference rendering tests**

Assert web references remain clickable and document references render as `文件名，第12页` or only the filename when the page is absent. Keep unknown `S` IDs raising `InvalidCitationError`.

- [ ] **Step 7: Run the focused suite**

Run: `.venv\Scripts\python.exe -m pytest tests/test_models.py tests/test_evidence.py tests/test_report.py -q`

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add src/mini_researcher/models.py src/mini_researcher/evidence.py src/mini_researcher/report.py tests/test_models.py tests/test_evidence.py tests/test_report.py
git commit -m "feat: unify web and document evidence"
```

## Task 3: Transactional SQLite Schema Migration

**Files:**
- Modify: `src/mini_researcher/repository.py:29-231`
- Modify: `tests/test_repository.py`

**Interfaces:**
- Consumes: expanded `ResearchState` and `Evidence` from Task 2.
- Produces: schema version 2 that persists retrieval mode, knowledge-base ID, and document provenance while reading version-1 databases.

- [ ] **Step 1: Write a failing legacy migration test**

Create a version-1 SQLite database directly in `tmp_path`, insert one task and one web Evidence, call `initialize()`, and assert:

```python
assert migrated.evidence[0].source_type == EvidenceSourceType.WEB
assert migrated.evidence[0].url == "https://example.com/source"
assert migrated.retrieval_mode == RetrievalMode.WEB
```

Also assert original row counts and foreign keys remain valid.

- [ ] **Step 2: Run the migration test and confirm failure**

Run: `.venv\Scripts\python.exe -m pytest tests/test_repository.py -q`

Expected: FAIL on missing columns or model fields.

- [ ] **Step 3: Implement versioned initialization and migration**

Use `PRAGMA user_version`. Treat an existing table set with `user_version=0` as the current legacy schema; treat `user_version=0` with no tables as a new database. Version 2 adds `retrieval_mode`, `knowledge_base_id`, `source_type`, `document_name`, `page_number`, and `chunk_index`; rebuild the Evidence table transactionally so `url` becomes nullable. Copy old rows as web sources and set `user_version=2` only after validation.

- [ ] **Step 4: Extend round-trip and rollback tests**

Round-trip one web and one document Evidence. Force an invalid document row during save and assert the prior snapshot remains unchanged.

- [ ] **Step 5: Run repository tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_repository.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/mini_researcher/repository.py tests/test_repository.py
git commit -m "feat: migrate storage for document evidence"
```

## Task 4: Qwen Embedding Adapter and Chroma Retrieval Boundary

**Files:**
- Create: `src/mini_researcher/embedding.py`
- Create: `src/mini_researcher/retrieval.py`
- Create: `tests/test_embedding.py`
- Create: `tests/test_retrieval.py`
- Modify: `tests/fakes.py`

**Interfaces:**
- Consumes: Task 1 settings and Task 2 `DocumentResult`.
- Produces: `create_dashscope_embeddings(settings: Settings) -> Embeddings`, `DocumentRetriever.retrieve(knowledge_base_id, query, top_k)`, `ChromaDocumentRetriever`, `RetrievalError`, and `FakeDocumentRetriever`.

- [ ] **Step 1: Write the failing Embedding factory test**

Monkeypatch `OpenAIEmbeddings` and assert the factory passes the configured model, 1024 dimensions, base URL, and a secret value without logging or returning the raw key. Assert calling this factory without `DASHSCOPE_API_KEY` fails with a sanitized configuration error while importing the API app and running web-only mode do not.

- [ ] **Step 2: Implement `create_dashscope_embeddings`**

Use `langchain_openai.OpenAIEmbeddings`; validate a nonblank API key and preserve the LangChain `Embeddings` return contract.

- [ ] **Step 3: Write failing retriever tests**

Use a fake Chroma object returning `Document` plus scores. Assert conversion to `DocumentResult`, `top_k` forwarding, missing index handling, blank query rejection, and provider-error mapping to `RetrievalError`.

- [ ] **Step 4: Implement `DocumentRetriever` and `ChromaDocumentRetriever`**

Exact protocol:

```python
def retrieve(
    self,
    knowledge_base_id: str,
    query: str,
    top_k: int,
) -> list[DocumentResult]
```

The implementation resolves only `data/knowledge_bases/{id}/index`, opens the named Chroma collection with the same Embeddings configuration, and never accepts an arbitrary filesystem path from the request.

- [ ] **Step 5: Add `FakeDocumentRetriever`**

Store deterministic responses by `(knowledge_base_id, query)` and record calls for orchestration assertions.

- [ ] **Step 6: Run focused tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_embedding.py tests/test_retrieval.py -q`

Expected: PASS without network calls or model downloads.

- [ ] **Step 7: Commit**

```powershell
git add src/mini_researcher/embedding.py src/mini_researcher/retrieval.py tests/test_embedding.py tests/test_retrieval.py tests/fakes.py
git commit -m "feat: add qwen embedding and chroma retrieval"
```

## Task 5: Knowledge-Base Ingestion Service

**Files:**
- Create: `src/mini_researcher/knowledge.py`
- Create: `tests/test_knowledge.py`

**Interfaces:**
- Consumes: LangChain Loader/Splitter, Embeddings, Chroma, and Task 1 limits.
- Produces: `UploadedDocument`, `KnowledgeBaseSummary`, `KnowledgeBaseError`, and `KnowledgeBaseService.create(files) -> KnowledgeBaseSummary`.

- [ ] **Step 1: Write failing upload validation tests**

Reject more than 5 files, files over 10 MiB, totals over 30 MiB, unsupported suffixes, empty files, `../` path traversal, absolute paths, and duplicate case-insensitive normalized names.

- [ ] **Step 2: Implement framework-independent upload value objects and validation**

Use:

```python
class UploadedDocument(BaseModel):
    name: str
    content: bytes

def create(self, files: list[UploadedDocument]) -> KnowledgeBaseSummary
```

Do not import FastAPI's `UploadFile` into this module.

- [ ] **Step 3: Write failing loader/splitter tests**

Create small Markdown and generated text-PDF fixtures under `tmp_path`. Assert Markdown keeps its filename, PDF chunks keep 1-based page numbers, chunk indexes are stable, and blank extracted text fails ingestion.

- [ ] **Step 4: Implement loading and Chinese-aware splitting**

Use `TextLoader`, `PyPDFLoader`, and `RecursiveCharacterTextSplitter` with the exact values in Global Constraints. Normalize metadata to filename, optional page number, and chunk index before indexing.

- [ ] **Step 5: Write failing atomic-readiness tests**

Inject an Embeddings or Chroma failure and assert no `ready` manifest exists and no returned `knowledge_base_id` can be retrieved. Leave failed staging unreferenced/quarantined rather than deleting it automatically.

- [ ] **Step 6: Implement staging, Chroma indexing, and manifest publication**

Create a random server-side ID, write only inside its assigned staging directory, build the collection, then atomically publish a `ready` manifest containing model, dimensions, document count, chunk count, and safe filenames. Never store full user paths or secrets.

- [ ] **Step 7: Run ingestion tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_knowledge.py -q`

Expected: PASS without an external Embedding call.

- [ ] **Step 8: Commit**

```powershell
git add src/mini_researcher/knowledge.py tests/test_knowledge.py
git commit -m "feat: ingest private documents into chroma"
```

## Task 6: Hybrid Retrieval Orchestration and Service Lifecycle

**Files:**
- Modify: `src/mini_researcher/orchestrator.py:11-84`
- Modify: `src/mini_researcher/service.py:10-65`
- Modify: `tests/test_orchestrator.py`
- Modify: `tests/test_service.py`

**Interfaces:**
- Consumes: Task 2 modes/Evidence, Task 4 `DocumentRetriever`, existing `SearchProvider`.
- Produces: mode-aware `ResearchOrchestrator.run(topic, state=state)` and `ResearchService.create_research(topic, retrieval_mode, knowledge_base_id)`.

- [ ] **Step 1: Write failing orchestration tests for all modes**

Assert `web` never calls the document retriever, `document` never calls Tavily, and `hybrid` calls both for first- and second-round questions.

- [ ] **Step 2: Write failure/degradation tests**

Assert Tavily failure plus document success retains document Evidence; document failure plus Tavily success retains web Evidence; both empty/failed produce no Evidence and ultimately `FAILED` rather than a report.

- [ ] **Step 3: Write deterministic interleaving tests**

For two web and two document results, assert source IDs alternate web/document and remain consecutive. Assert one short side lets the other fill remaining capacity without exceeding 12.

- [ ] **Step 4: Implement mode-aware retrieval**

Inject `document_retriever: DocumentRetriever | None` and `rag_top_k`. Pass the `knowledge_base_id` explicitly on every document lookup. Keep one `EvidenceManager` across both rounds.

- [ ] **Step 5: Extend the service signature and no-evidence rule**

Exact signature:

```python
def create_research(
    self,
    topic: str,
    retrieval_mode: RetrievalMode = RetrievalMode.WEB,
    knowledge_base_id: str | None = None,
) -> ResearchState
```

Persist the initial mode/knowledge-base choice and raise a controlled failure before ReportWriter when `state.evidence` is empty. Replace the old test that expected an evidence-free task to complete.

- [ ] **Step 6: Run orchestration and service tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_orchestrator.py tests/test_service.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add src/mini_researcher/orchestrator.py src/mini_researcher/service.py tests/test_orchestrator.py tests/test_service.py
git commit -m "feat: orchestrate hybrid web and document research"
```

## Task 7: FastAPI Knowledge-Base and Research Contracts

**Files:**
- Modify: `src/mini_researcher/api.py:19-143`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes: `KnowledgeBaseService`, expanded `ResearchService`, and settings factories.
- Produces: `POST /knowledge-bases` plus backward-compatible `POST /research` request validation.

- [ ] **Step 1: Write failing API tests for knowledge-base upload**

Use an injected fake service and multipart files. Assert HTTP 201 plus `knowledge_base_id`, `document_count`, `chunk_count`, and `status="ready"`; validation failures return 422 without exposing internal paths.

- [ ] **Step 2: Write failing research request tests**

Assert the old `{"topic": "..."}` request still calls web mode. Assert valid hybrid requests forward the ID. Assert document/hybrid without an ID, missing IDs, and not-ready IDs return 422.

- [ ] **Step 3: Implement dependency factories and routes**

Extend `create_app(...)` with optional injected `knowledge_service` and knowledge-base validator/retriever dependencies. Lazily build real Embeddings/Chroma components only on upload or document retrieval, so `/docs` and web-only queries do not require DashScope initialization.

- [ ] **Step 4: Verify API boundaries**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py -q`

Expected: PASS with no real API calls.

- [ ] **Step 5: Commit**

```powershell
git add src/mini_researcher/api.py tests/test_api.py
git commit -m "feat: expose knowledge base and hybrid research APIs"
```

## Task 8: Streamlit Upload and Mixed Evidence UI

**Files:**
- Modify: `src/mini_researcher/ui.py:22-197`
- Modify: `tests/test_ui_smoke.py`

**Interfaces:**
- Consumes: Task 7 HTTP contracts and expanded `ResearchState` JSON.
- Produces: PDF/Markdown upload, mode selection, two-step create-KB/create-research calls, and source-aware Evidence rendering.

- [ ] **Step 1: Write failing UI smoke assertions**

Assert source contains a file uploader restricted to `pdf` and `md`, a mode selector with three values, `/knowledge-bases`, `knowledge_base_id`, and document rendering that does not call `_source_domain(None)`.

- [ ] **Step 2: Implement two-step request flow**

When files exist, upload them first and keep only the returned ID in Streamlit session state; then submit the research request. When no files exist, permit only web mode and keep the existing request body compatible.

- [ ] **Step 3: Implement source-aware Evidence rendering**

Web Evidence retains link/domain UI. Document Evidence shows filename, optional page number, and chunk content without a fake hyperlink.

- [ ] **Step 4: Run UI and API tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_ui_smoke.py tests/test_api.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/mini_researcher/ui.py tests/test_ui_smoke.py
git commit -m "feat: add hybrid rag controls to streamlit"
```

## Task 9: Full Verification, Docker, Documentation, and Portfolio Evidence

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md` verification record
- Modify: `docs/assets/` only with non-sensitive screenshots generated from a sanitized demo
- Test: entire `tests/` suite

**Interfaces:**
- Consumes: all previous tasks.
- Produces: reproducible project instructions, verified test record, Docker validation, and sanitized portfolio evidence.

- [ ] **Step 1: Run the complete offline suite**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: all tests pass; record the actual count and duration rather than copying an old number.

- [ ] **Step 2: Run static packaging checks**

Run: `.venv\Scripts\python.exe -m pip check`

Expected: `No broken requirements found.`

Run: `git diff --check`

Expected: no whitespace errors.

- [ ] **Step 3: Perform an explicit real-service smoke test**

After confirming only the presence—not values—of `DEEPSEEK_API_KEY`, `TAVILY_API_KEY`, and `DASHSCOPE_API_KEY`, upload one sanitized PDF and one Markdown file. Verify persistent reopen, expected chunk retrieval, a hybrid report containing both source types, and valid citations. Record actual requests/costs; never print keys or full private content.

- [ ] **Step 4: Rebuild and test Docker**

Build the image, run with an explicitly user-provided env file, check `/openapi.json`, upload sanitized documents, and execute one hybrid task. Verify `data/` is mounted for SQLite/Chroma persistence and the container remains non-root.

- [ ] **Step 5: Update README and project verification record**

Document installation, environment variable names, privacy boundary, three modes, upload limits, startup, example API calls, current limitations, and actual verification commands/results. Add only sanitized screenshots.

- [ ] **Step 6: Run the final suite again after documentation/UI assets**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: all tests pass with the same behavioral coverage.

- [ ] **Step 7: Review Git contents for secrets and runtime data**

Run: `git status --short`

Expected: no `.env`, uploaded files, Chroma index, SQLite database, or credential-bearing logs staged.

- [ ] **Step 8: Commit final verified documentation**

```powershell
git add README.md docs/assets
git add -p CLAUDE.md
git commit -m "docs: verify and present hybrid rag workflow"
```

Do not push. `git push` requires a separate explicit user authorization after final review.
