# Torque Concept 3D: customer feedback heat map

The 3D view of Torque's **Concept 3D** page. Same layout as before: the car on the left, the top 10
purchase drivers on the right, an info card on the car. Instead of the procedural concept car it shows a real
car model coloured part by part with the customer comments from `Dataset/` (`F70`/`G60`/`G70_feedback_hackathon.xlsx`).

- **Same selection as Torque:** "Successor of" picks the series (1 → F70, 5 → G60, 7 → G70), "Market"
  picks the comments by country (Europe, USA, Rest of world; China see below).
- **Driver ↔ part:** clicking a top 10 driver flies to its part (`PART` in `demo/torque/dist/index.html`,
  e.g. R-11 → wheels, R-14 → front seats). Clicking a part focuses its best ranked driver. The card
  shows Torque's driver, status, rank and evidence plus the part's heat score, comment counts and a quote.
- **Counts as in Torque:** "comments" are unique comment IDs (one comment has one row per classification,
  shown as "classified mentions"), so the numbers match Torque's data chip.
- **China:** no owner comments, so parts are coloured by Torque's own China customer study values
  (`BMW.study`, G68/G70) of their linked drivers, ranked like the comment heat map.
- **Options:** the card lists Torque's option for the driver plus matching entries of the model's price list
  (`outputs/markdown/options/processed/*_options_features.md` → `data/options-<model>.json`, `options.py`).
- **Design prompt** (Design / Design prompt buttons) and **Visualize in Unreal Engine** as in the
  stand-alone app.

The frame is created once and laid over the stage, so switching model, market or decisions does not
reload the car.

## Set up on a PC (once)

1. **Download the three cars** (free Sketchfab account, format **glTF**) into one folder, e.g. `car models/`:
   - 1 Series (F70) → [2020 BMW X1 xDrive18d](https://sketchfab.com/3d-models/2020-bmw-x1-xdrive-18d-4ca3a2247af44e51919074565ed93486#download) → `2020_bmw_x1_xdrive_18d.zip`
   - 5 Series (G60) → [2019 BMW X5 xDrive30d](https://sketchfab.com/3d-models/2019-bmw-x5-xdrive30d-850fb32f984c4630969840fc61f44902#download) → `2019_bmw_x5_xdrive30d.zip`
   - 7 Series (G70) → [2019 BMW X7 xDrive40i](https://sketchfab.com/3d-models/2019-bmw-x7-xdrive40i-a4b1edf1ec614f06b5d4db7208fe9650#download) → `2019_bmw_x7_xdrive40i.zip`

   All by Ddiaz Design (sketchfab.com/ddiaz-design), **CC-BY-NC-SA-4.0**: credit the author, no commercial use,
   share alike. Keep the zips outside the repo.
2. Generate the data and install the cars:

```bash
pip install openpyxl
python demo/visu/prepare_local.py --cars "<path>/car models"
```

This writes two **local, gitignored** folders next to the build:
- `dist/visu/data/feedback-<series>[-<market>].json`: scores per part for every series and market, with sample customer quotes (kept out of git like Torque's `quotes.json`).
- `dist/visu/models/bmw-x1-2020/`, `bmw-x5-2019/`, `bmw-x7-2019/`: the cars. The selected model family shows its
  car (Torque's "Successor of", or the data selector in the stand-alone page).

**How the cars are mapped** (`src/models/template.ts`, `cars.ts`): the 56 components (same ids everywhere: heat
map, Torque drivers, Rowboat `Components/` notes) are built from each car's material roles (paint, trim, glass,
lights, tyres, rims, seats, dashboard, ...) plus regions in the normalized car frame; spatial parts are
approximate (≈ in the list). The front splitter (all three) and the rear diffuser (X7) do not exist on these SUVs.
The Unreal viewer only has the M4 imported, so its button is disabled for these cars.

Then install Torque as in `demo/torque/README.md`; the 3D view is at Concept 3D.

## Data in Rowboat's knowledge graph

Rowboat's own schema (checked in `rowboat/apps/x`): every note is a graph node, every `[[link]]` an edge, the
graph colours nodes by **top-level folder**, and its note agents know note types from `config/notes.json`. So the
data uses one top-level folder per type, flat inside, with the hierarchy in the links:

```
knowledge/
├── Brands/            BMW                                    (a second brand: Brands/Audi.md)
├── Models/            1er F70, 5er G60, 5er G68, 7er G70     summary tables + links
├── Components/        56 parts of the 3D car: editable heat-map + options tables per model (feed Concept 3D)
├── Feature Classes/   70 VFC level 2 classes that colour a component
└── Data/
    └── BMW Dataset.xlsx   analysis workbook: Feedback (one row per classified mention, no text), Heat, Sales,
                           Studies, Options
```

Links: Brand ↔ Models ↔ Components ↔ Feature Classes; Models and Brand link the workbook. Country, market,
engine, source, feedback type and VFC level 3 are workbook columns (and model summary tables), not nodes, which
keeps the graph at about 130 nodes.

```bash
python demo/visu/vault.py graph                 # fixed link map demo/torque/dist/visu/graph.json (committed)
python demo/visu/brand.py --register            # notes + workbook; --register adds the 4 types to config/notes.json
python demo/visu/vault.py sync --watch          # keep running: Components notes -> dist/visu/data/visu.json
```

- **Fixed links:** the UI only uses `graph.json`; Components notes are found by `part_id` in their front matter,
  so editing links or renaming a note never breaks the 3D view.
- **Editable data:** the "Customer feedback heat map" and "Options today" tables in each Components note. Change
  a value in Rowboat, by hand or via the AI, and Concept 3D shows it within seconds.
- Notes are only created when missing; `--refresh` rewrites notes that still have `managed_by: ehl-visu`. The
  workbook is regenerated on every run. Comment texts never go into the vault (spec D8).

## Agent, RAG and data (2026-10-10)

Torque's page holds cockpit logic and UI wording only; content comes from data files and Rowboat:

| What | Source | Edit in |
|---|---|---|
| Dataset aggregates (`BMW`) | `dist/bmw.json`, checked against `Dataset/` by `check_bmw.py` (0 mismatches) | regenerate |
| Driver texts (title, motive, target, acceptance, assumptions, evidence, conflict, successor feature) | agent: `generate_texts.py` (gpt-4.1, `research/AGENT.md` rules, RAG + findings + `bmw.json`; cited comment IDs checked against the Dataset) | Rowboat `Requirements/` |
| Values without a Dataset source (competitors, feature prices, segments, weights, dimensions, feasibility, external research) | seed `dist/assumptions.seed.json` | Rowboat `Assumptions/` (JSON block per note) |
| Nordi answers | Rowboat model + RAG passages (`src/rag_backend`, `/search` on :8100), cited as [S1] … | — |

```bash
# once per PC (after Docker is running)
docker compose -f docker-compose.qdrant.yml up -d
python -m venv search/.venv && search/.venv/Scripts/python -m pip install -r requirements.txt   # OPENAI_API_KEY in search/.env
search/.venv/Scripts/python scripts/ingest_qdrant.py --chunks-path outputs/chunks/chunks.jsonl
search/.venv/Scripts/python -m uvicorn app:app --port 8100                                       # keep running (RAG)
python demo/visu/assumptions.py notes                                                             # Assumptions/ notes
search/.venv/Scripts/python demo/visu/generate_texts.py                                           # Requirements/ notes (agent)
python demo/visu/vault.py sync --watch                                                            # keep running
```

Market MCP (`market/`, from main): `ehl-market` in `~/.rowboat/config/mcp.json` gives Rowboat's agent the
correlation tools (see `market/README.md`). UI wording (view names, method definitions, the tour) stays in
the page.

## How it works

- **Heat map:** score = rank of the weighted positive share of comments per part (0 = most criticised,
  100 = best rated), exterior and interior ranked separately (`feedback.py`). Click a part for counts and quotes.
- **Design prompt:** sent to the model configured in Rowboat (`/_rowboat/llm/generate`, Torque's `llm`
  capability). Outside Rowboat a keyword matcher answers. Every action is validated and clamped in
  `src/lib/interpret.ts` (colors and finishes; scaling, moving or hiding parts, ride height, wheel size,
  track width, body proportions). New geometry is never generated.

## Unreal Engine button

Needs UE 5.8 and the `visu_pro` backend (PR #6) running on this PC:
`cd visu_pro/backend; .\.venv\Scripts\python -m uvicorn app:app --port 8000`, with
`http://torque.apps.localhost:3210` in its `CORS_ORIGINS`. Without it the button shows "Backend offline";
the rest of the view works.

## Change the app

```bash
cd demo/visu
npm ci
npm run dev     # http://127.0.0.1:5174, uses the local data/ and models/
npm run build   # rebuilds demo/torque/dist/visu/assets (commit the result)
```
