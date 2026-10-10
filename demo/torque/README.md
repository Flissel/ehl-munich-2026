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
- **Vault to Torque:** the product and topic notes go to `data/rowboat.json`. Torque shows them in Data and workflow, links every driver to its notes and gives the facts to its copilot.
- Only notes with `managed_by: torque` are rewritten. Delete that line in a note to keep your own edits.

## Not in git

`data/` stays local: `quotes.json` (customer comment texts), `logo.png` (brand mark), `torque.json` (decisions) and `rowboat.json` (vault snapshot). For the demo PC copy `data/` from Peter's machine. The build itself comes from `docs/prototype/rowboat/deploy.py` in Peter's prototype repo.

## Concept 3D

The Concept 3D page embeds the customer feedback heat map from `demo/visu/` (built into `dist/visu/`). Run `python demo/visu/prepare_local.py --model <glTF zip>` once per PC for its data and car model; see `demo/visu/README.md`.
