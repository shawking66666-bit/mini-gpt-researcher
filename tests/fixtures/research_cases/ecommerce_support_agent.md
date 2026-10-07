---
case_id: ecommerce-support-agent
source_url: https://github.com/iamdanielkitchen/ecomm-support-agent/blob/main/CLAUDE.md
captured_at: 2026-10-07
expected_research_points:
  - authenticated order lookup and customer-data isolation
  - deterministic return eligibility and action guardrails
  - policy-grounded answers and human escalation
  - auditability, testing, evaluation, and rollout controls
---

## Sanitized requirement

Research an e-commerce customer-support agent that can answer shipping and return-policy questions, look up an authenticated customer's order, determine return eligibility, initiate an allowed return, and hand unsupported or risky cases to a human agent.

The report should separate LLM decisions from deterministic business rules, prevent disclosure of another customer's order, require tool results before stating order facts, define safe handling for refunds, payment disputes, suspected fraud, tool failures, and emotional or ambiguous requests, and propose measurable evaluation and staged rollout. It should compare integration options for a storefront, order-management system, policy knowledge base, and helpdesk without assuming that every action should be fully autonomous.

## Sanitization note

Brand names, sample customer identities, order numbers, emails, and generated label links from the public example were removed. The functional and safety scope remains.
