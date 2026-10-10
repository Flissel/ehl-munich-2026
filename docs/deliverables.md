# Expected Deliverables

From the challenge brief:

1. **Concept and demonstrable prototype** of an AI-powered product requirements application that processes heterogeneous inputs, derives product requirements, supports prioritization, and integrates human review.
2. **A structured sample list of derived product requirements.** Each requirement should include a unique identifier, a clear and actionable description, its linked findings and sources, a priority or score, the applied prioritization rationale, an evidence level, the key future-facing assumptions and uncertainties, and its current decision status.
3. **A clearly defined end-to-end workflow** showing how inputs are processed into proposed and prioritized requirements, which activities the AI performs autonomously, and where human review is mandatory.
4. **A demonstrable audit trail** that makes each requirement traceable from its underlying findings and sources through consolidation, scoring, prioritization, and human decision-making. It should record relevant changes to requirement content, scores, priorities, evidence, and status, including who or what initiated each change, when it occurred, and the documented rationale.

> Teams are free to choose their technical approach, architecture, prioritization logic, and user experience. The deliverables describe the capabilities and outcomes to demonstrate, not a prescribed solution design. They may be presented as one integrated solution or as a combination of connected concepts, prototypes, models, and visualizations.

## How our plan maps to them

See [data-pipeline-plan.md](data-pipeline-plan.md) for the full plan.

| Deliverable | Covered by | Still to define |
| --- | --- | --- |
| 1. Prototype | G60 US demo, then config switch to F70 GB | App/UI stack |
| 2. Requirement list | Cluster record → candidate requirement | Evidence level, assumptions & uncertainties (see schema below) |
| 3. Workflow | Source → Signal → Requirement → Priority → PM decision → Audit log | Explicit AI-autonomous vs. human-mandatory split (below) |
| 4. Audit trail | Append-only decision log + system events | Must also log **score, priority, evidence and status changes**, not only PM decisions |

## Requirement record (draft schema)

Every field from deliverable 2:

| Field | Example / source |
| --- | --- |
| `id` | `REQ-G60-US-0007` (stable, never reused) |
| `description` | Clear, actionable: "Kick-to-open trunk sensor shall not trigger unintentionally when walking past the vehicle" |
| `findings` | Linked cluster IDs → comment IDs, study items, option codes, web snippets (each with source type A–D / web) |
| `score` / `priority` | Weighted score + rank / bucket (Must / Should / Could) |
| `rationale` | Factor breakdown and weights used (frequency, severity, competitor gap, trend, fit, effort) |
| `evidence_level` | e.g. **High**: ≥2 independent source types + survey confirmation; **Medium**: one source type with volume; **Low**: few comments or web-only |
| `assumptions` | Future-facing, e.g. "BEV share in US rises, so charging complaints grow", "Competitor X keeps feature in MY2027" |
| `uncertainties` | e.g. "Sources A–D inferred, not confirmed", "Source B is agent paraphrase", "Small sample (n=12)" |
| `status` | `proposed` → `in_review` → `approved` / `rejected` / `challenged` / `edited` |

## Workflow: AI vs. human

| Step | Who |
| --- | --- |
| Ingest, assign stable IDs, mask personal data | AI / system (autonomous, logged) |
| Classify untagged comments, cluster, name clusters | AI (autonomous, logged as AI-assigned) |
| Link clusters to studies, option list, competitors | AI (autonomous), lookup table maintained by humans |
| Draft requirement text, evidence level, assumptions | AI (proposal only) |
| Compute score with current weights | System (autonomous, weights version logged) |
| Set / adjust weights and effort (S/M/L) | **Human (mandatory)** |
| Approve / reject / edit / challenge each requirement | **Human (mandatory)** — no requirement reaches `approved` without a PM |
| Re-score after edits or new evidence | System, change logged with old/new values |

## Audit log entry (draft schema)

Append-only, one row per change:

| Field | Example |
| --- | --- |
| `event_id`, `timestamp` | `EVT-000123`, ISO 8601 |
| `requirement_id` | `REQ-G60-US-0007` |
| `change_type` | `content` / `score` / `priority` / `evidence` / `status` |
| `old_value` → `new_value` | `score 0.62` → `0.71` |
| `actor` | `ai:clusterer@v1` / `system:scorer@weights-v3` / `user:pm.name` |
| `rationale` | "PM raised weight of competitor gap" / "3 new web snippets linked" |
