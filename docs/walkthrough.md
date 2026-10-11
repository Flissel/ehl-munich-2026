# Walkthrough: the app step by step

A tour through the running demo. For each step: what you see, and what we built on top of Rowboat. Set up the
demo first: [README → Run it](../README.md#run-it).

**Legend.** *Rowboat* = comes with Rowboat (unmodified, commit `72e9d8c`). *Ours* = built for this project,
in this repository.

## 1. Rowboat with our knowledge vault

Open Rowboat and go to the knowledge view.

- **What you see.** Folders `Brands/`, `Models/` (F70, G60, G68, G70), `Components/` (56 car parts),
  `Feature Classes/`, `Assumptions/`, `Requirements/` and `Data/BMW Dataset.xlsx`. The graph links each
  requirement to its model, parts and topics.
- **Rowboat.** The vault, the Markdown editor, the graph from `[[links]]`, and note types.
- **Ours.** All notes and their link structure (`demo/visu/vault.py notes`). Our note types are registered
  in `config/notes.json` (`demo/visu/brand.py`), so Rowboat's note agents write new notes in the same shape.

## 2. Open Torque from Rowboat's Apps

Apps → Torque, served at `http://torque.apps.localhost:3210`.

- **Rowboat.** App hosting, the app data store `/_rowboat/data/*`, and the model through
  `/_rowboat/llm/generate`.
- **Ours.** The whole cockpit (`demo/torque/dist/index.html`) and its manifest (`rowboat-app.json`).

At the top, choose the **model** (1, 5 or 7 Series successor), the **market** (Europe, USA, China, Rest of
World) and the **level**:

- **Essentials** is for deciding: the top 10, a recommendation for each, the decision and the criticised parts.
- **Analyst** adds every number and the views marked *Analyst* below.

## 3. Decide → Overview

*Successor of the chosen model in the chosen market.*

- **What you see.** The top 10 purchase drivers, each with a recommendation and a decision button. The overview
  tiles show the drivers decided, the drivers waiting, and the most criticised car parts. The **Rowboat
  knowledge graph** card lists the vault notes that link to this model.
- **Ours.** Ranking and scoring of purchase drivers from `Dataset/`, the decision flow, and the vault card
  (fed by `demo/torque/sync.py`).

## 4. Decide → Concept 3D

*The successor car, built live from your decisions.*

- **What you see.** The X1, X5 or X7 stand-in, coloured from red (most criticised part) to green. Click a
  driver and the camera flies to its part. Click a part to see its score, comment counts, a customer quote
  and the matching options from the price list. A design prompt edits the car's proportions.
- **Ours.** The whole engine: segmentation, heat map, link to the drivers, design prompt. See
  [The 3D engine](3d-engine.md).

## 5. Decide → Review log

*Decisions on the successor.*

- **What you see.** Every decision: when, which driver, what changed, the reason, and who decided.
- **Ours.** The review flow. Decisions are also written to Rowboat notes in `Purchase Drivers/` (only notes
  marked `managed_by: torque` are rewritten).

## 6. Analyse → Purchase drivers *(Analyst)*

*The customer needs that make people buy, not what they wish for.*

- **What you see.** Every driver with its score, weighting, robustness and evidence level, plus customer quotes
  with comment IDs. The quote texts come from `Dataset/`, masked (`demo/torque/make_quotes.py`).
- **Ours.** Scoring, the evidence model and quote selection. Requirement texts (target, acceptance criterion,
  assumptions) come from the `Requirements/` notes that an agent drafted with the RAG backend
  (`demo/visu/generate_texts.py`).

## 7. Analyse → Simulator *(Analyst)*

*What if: which spec wins customers and which loses them.*

- **What you see.** Toggle drivers in or out of the spec and watch the expected buyers and sales upside per
  market change.
- **Ours.** The choice model and sales projection.

## 8. Analyse → Audit trail *(Analyst)*

*Append-only record of every change to content, score, priority, evidence and status.*

- **What you see.** One row per change: the old and new value, the actor (for example `system:privacy@v1`,
  an AI step, or a named user), the time and the reason. You can search it. Read top to bottom, it traces
  each requirement from ingest through scoring to the human decision.
- **Ours.** The audit model, following the schema in [deliverables](deliverables.md).

## 9. Evidence → Customer voice, Feature map, Competitors *(Analyst)*

- **Customer voice.** What BMW owners say and what makes them buy.
- **Feature map.** The vector space of real customer comments: what belongs together and what is new.
- **Competitors.** Rivals of the model: what owners compare, and the perception benchmark.
- **Ours.** All three views, plus the research pipeline behind them (`research/`: cleaning, PII masking,
  clustering).

## 10. Evidence → Data and workflow *(Analyst)*

*The BMW data behind every number, how it flows, and where a human decides.*

- **What you see.** The workflow from ingest to decision. Each step is marked **autonomous, logged** (AI or
  system) or **human** (weights, effort, approve, reject, edit, challenge). This is deliverable 3.
- **Ours.** The workflow and its documentation.

## 11. Assist → Copilot (Nordi)

*Ask Nordi about the data on screen.*

- **What you see.** A chat that answers from the cockpit's data and, with the RAG backend running, from the
  indexed source documents with evidence.
- **Rowboat.** The model, through the app API.
- **Ours.** Nordi's prompt and context, and the RAG backend (`app.py`, `src/rag_backend/`, Qdrant, port 8100).

## 12. Rowboat's agent with the market MCP

Back in Rowboat, ask the agent, for example: "How do EV registrations in the US relate to the charging
complaints for the 5 Series?"

- **Rowboat.** The agent, tool use, and the MCP client.
- **Ours.** The `ehl-market` server (`market/`): sources, live World Bank, Eurostat and NHTSA data,
  correlation tools.

The agent can also edit a `Components/` or `Requirements/` note. The change appears in Torque and on the 3D
car within seconds. Decisions in Torque appear as notes in Rowboat.

## 13. Export the brief

From Torque, export a **brief**, short or detailed. It contains the decisions on the top 10, the evidence,
targets and acceptance criteria, open evidence requests, the sales upside by market, and the review log.
