---
case_id: enterprise-document-agent
source_url: https://github.com/Azure/GPT-RAG/issues/526
captured_at: 2026-10-07
expected_research_points:
  - document-level authorization and identity propagation
  - source connectors and permission trimming
  - citation-grounded answers and refusal behavior
  - evaluation, observability, security, and deployment risks
---

## Sanitized requirement

Research a production-ready enterprise document agent that answers questions over internal files while preserving each user's existing access permissions. The proposed solution should compare viable retrieval approaches, explain how identity and document-level authorization flow through ingestion and query time, and prevent a user from retrieving content they cannot access.

The report should recommend an architecture for multiple enterprise sources, grounded answers with traceable citations, explicit refusal when evidence is insufficient, evaluation and observability, and a staged delivery plan. It must identify open security, privacy, multimodal-document, cost, and operational risks instead of assuming that a generic vector database is sufficient.

## Sanitization note

Only the public functional scope was retained. Usernames, discussion participants, organization-specific tokens, and private attachments are excluded.
