# Torque in Rowboat

Torque Decision Cockpit as a local Rowboat app: the top 10 purchase drivers per BMW model and market, the review with reasons, the audit trail and the market map.

## Install

From the repo root, with Rowboat running (`npm run dev`):

```bash
ln -s "$PWD/demo/torque" ~/.rowboat/apps/torque      # Windows: mklink /J %USERPROFILE%\.rowboat\apps\torque demo\torque
python3 demo/torque/sync.py --watch                  # keep it running next to Rowboat
```

Rowboat lists Torque under Apps and serves it on `http://torque.apps.localhost:3210`.

## What syncs

- **Torque to vault:** every decision makes Torque write `data/torque.json` (rankings of every model and market plus the decisions). `sync.py` turns it into one note per purchase driver and one top 10 note per model in `~/.rowboat/knowledge/Purchase Drivers`, linked to the product, theme and market notes.
- **Vault to Torque:** the product and topic notes, Yunes' dataset graph (`BMW/`) and car parts (`Vehicle Parts/`) go to `data/rowboat.json`. Torque shows per purchase driver its customer themes with the comment numbers of the model and its car parts with their heat, lists the most criticised car parts of the model and market on the overview, and gives all of it to its copilot.
- Only notes with `managed_by: torque` are rewritten. Delete that line in a note to keep your own edits.

## Essentials and Analyst

Essentials (black) is for deciding: the top 10 with a recommendation, the decision and the car parts customers criticise. Analyst (grey background, blue switch and badge) adds every number: scores, weightings, robustness, evidence, simulator and audit trail.

## Not in git

`data/` stays local: `quotes.json` (customer comment texts), `logo.png` (brand mark), `torque.json` (decisions) and `rowboat.json` (vault snapshot). `python demo/torque/make_quotes.py` writes `quotes.json` from `Dataset/` (masked with the research pipeline's PII masking); `scripts/install.py` runs it. `dist/index.html` is the cockpit's source: a single hand-written HTML/JS file, not a minified build.

## Concept 3D

The Concept 3D page embeds the customer feedback heat map from `demo/visu/` (built into `dist/visu/`), on the car of the selected model (X1 for the 1 Series, X5 for the 5 Series, X7 for the 7 Series). Run `python demo/visu/prepare_local.py --cars "<folder with the three car zips>"` once per PC (download links in the top-level README). Without the cars, the stage says how to install them.
