---
case_id: browser-automation-agent
source_url: https://github.com/microsoft/playwright/issues/42089
captured_at: 2026-10-07
expected_research_points:
  - target-loss detection and bounded recovery
  - explicit user approval and visible-tab scoping
  - screenshot fallback without secret extraction
  - failure statuses, auditability, compatibility, and tests
---

## Sanitized requirement

Research a browser-automation agent that operates an explicitly user-approved existing browser tab and remains understandable when a sign-in flow invalidates the current automation target. The design should investigate safe recovery or visible-tab capture options without exporting cookies, passwords, local storage, or hidden page content.

The report should compare normal browser-protocol screenshots with a narrowly scoped fallback, define explicit `target_lost`, timeout, unsupported, and permission-denied outcomes, require human participation for interactive login, and cover compatibility, retries, audit logs, privacy boundaries, and reproducible tests. It must distinguish verified platform capabilities from proposed features and avoid claiming that one observed website failure generalizes to every site.

## Sanitization note

The public issue's user identity, specific observed website, login artifacts, and conversation details were removed. The target-lifecycle, consent, capture, and security requirements were retained.
