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

1. **Download the car model** (free Sketchfab account needed):
   https://sketchfab.com/3d-models/2021-bmw-m4-competition-d3f07b471d9f4a2c9a2acf79d88a3645#download
   and choose **glTF** (gives `2021_bmw_m4_competitionglTF.zip`). Keep the zip outside the repo.
2. Generate the data and install the model:

```bash
pip install openpyxl
python demo/visu/prepare_local.py --model <path>/2021_bmw_m4_competitionglTF.zip
```

This writes two **local, gitignored** folders next to the build:
- `dist/visu/data/feedback-<series>[-<market>].json`: scores per part for every series and market, with sample customer quotes (kept out of git like Torque's `quotes.json`).
- `dist/visu/models/bmw-m4-competition-2021/`: the car. "2021 BMW M4 Competition" by Ricy
  (sketchfab.com/ngon_3d), **CC-BY-NC-4.0**: credit required, no commercial use. Download link in
  step 1 (or get the zip from a teammate). It stands in for the 1/5/7 Series.

Then install Torque as in `demo/torque/README.md`; the 3D view is at Concept 3D.

## Data in Rowboat's knowledge graph

The part data lives in the vault, so Rowboat (and its AI) is where it is changed:

```bash
python demo/dataset_to_notes.py --out ~/.rowboat/knowledge   # WP1: Projects/ and Topics/ (models, themes, markets)
python demo/torque/sync.py                                    # Torque: Purchase Drivers/
python demo/visu/vault.py notes                               # Vehicle Parts/: hub, sides, areas, 56 parts
python demo/visu/vault.py sync --watch                        # keep running: vault -> dist/visu/data/visu.json
```

- **Graph:** `Vehicle Parts/Vehicle` → `Exterior` / `Interior` → 11 areas (Wheels and brakes, Lighting, Seats,
  Cockpit and displays, …) → one note per part. Each part note links to its purchase drivers
  (`Purchase Drivers/…`), WP1 themes (`Topics/…`) and the models (`Projects/F70` …).
- **Fixed links:** what belongs to what (part ↔ area ↔ driver ↔ theme, feature classes per part) is
  `demo/torque/dist/visu/graph.json`, built by `vault.py graph` and committed. The UI only uses this map, so
  editing or deleting links in a note never breaks the 3D view. Notes are found by `part_id` in their front
  matter, so a renamed note still feeds the same part.
- **Editable data:** the tables in each part note ("Customer feedback heat map" per model and market,
  "Options today" per model). Change a value in Rowboat, by hand or by asking the AI, and Concept 3D shows it
  within a few seconds (heat colour, counts and options in the card). The card names the note ("In Rowboat: …").
- `vault.py notes` only creates missing notes; `--refresh` rewrites notes that still have
  `managed_by: ehl-visu` (remove that line to protect a note). Quotes never go into the vault (spec D8);
  they stay in the local `data/feedback-*.json`.

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
