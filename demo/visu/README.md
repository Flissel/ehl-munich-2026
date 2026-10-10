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

All Dataset values live in the vault as one tree; Rowboat (and its AI) is where they are changed:

```bash
python demo/visu/vault.py notes                 # writes missing notes of <vault>/Brands (brand.py), ~870 notes
python demo/visu/vault.py sync --watch          # keep running: component notes -> dist/visu/data/visu.json
```

```
knowledge/Brands/
├── Brands.md
└── BMW/                                   ← brand (a second brand gets Brands/<Brand>/)
    ├── BMW.md
    └── Models/
        ├── Models.md
        ├── 1er F70/                       ← one folder per model (3D car = placeholder for every model)
        │   ├── 1er F70.md
        │   ├── Components/  Exterior|Interior / <area> / <part>.md   ← 56 parts, editable heat + option tables
        │   ├── VFC/         VFC.md + one note per feature class (level 3 and 2+3 tables inside)
        │   ├── ID/          ID.md (every comment ID, no text)
        │   ├── Country/     Country.md + one note per country
        │   ├── Engine/      Engine.md + ICE / PHEV / BEVE
        │   ├── Source/      Source.md + Source A … D
        │   ├── Feedback/    Feedback.md + Likes, Defect, Difficult to Use, Wants
        │   ├── Sales/       Sales.md
        │   ├── Studies/     Study Europe / USA / China 2025
        │   └── Options/     Options.md (price list, linked to components)
        ├── 5er G60/  …
        ├── 5er G68/  Sales, Studies (China), Options only: no feedback in the Dataset
        └── 7er G70/  …
```

- Every folder has a hub note with its name, so the graph mirrors the folders. All values come from `Dataset/`
  (and `outputs/markdown/options`); comment texts never go into the vault (spec D8).
- **Fixed links:** what belongs to what (part ↔ area ↔ feature classes ↔ purchase drivers) is
  `demo/torque/dist/visu/graph.json` (`vault.py graph`, committed). The UI only uses this map; notes are found by
  `part_id` + `model` in their front matter, so editing links or renaming a note never breaks the 3D view.
- **Editable data:** the "Customer feedback heat map" and "Options today" tables in each component note. Change a
  value in Rowboat, by hand or via the AI, and Concept 3D shows it within a few seconds (the card names the note).
- `vault.py notes` only creates missing notes; `--refresh` rewrites notes that still have `managed_by: ehl-visu`.

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
