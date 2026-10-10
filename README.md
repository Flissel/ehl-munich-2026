# ehl-munich-2026
EHL Munich 2026 Grand Finale hackathon project

## Team & Setup

**Event:** EHL Munich 2026 Grand Finale (10–11 Oct 2026, Garching)  
**Agent Sessions:** Tracked with [Entire](https://github.com/anthropics/entire)

## Run the demo on your PC (Torque in Rowboat)

Torque (`demo/torque`) is the decision cockpit, shown as an app inside Rowboat. Its content comes from the
Dataset, the Rowboat knowledge graph, the agent and the RAG; nothing is hardcoded in the page. Steps, Windows
(PowerShell) and macOS:

1. **Rowboat in dev mode** and the tools (Git, Python 3.12, Node 22/24, pnpm 10, Docker Desktop): follow
   [SETUP.md](SETUP.md). Set a model provider in Rowboat with your own key (Nordi and the design prompt use it).
2. **This branch:** `git fetch origin && git switch feat/ehl-demo-visu` (or `main` once PR #7 is merged).
3. **Download the three 3D cars** (free Sketchfab account, format **glTF**) into one folder, e.g. `car models/`,
   keep the zip names:
   - 1 Series (F70) → [2020 BMW X1 xDrive18d](https://sketchfab.com/3d-models/2020-bmw-x1-xdrive-18d-4ca3a2247af44e51919074565ed93486#download) → `2020_bmw_x1_xdrive_18d.zip`
   - 5 Series (G60) → [2019 BMW X5 xDrive30d](https://sketchfab.com/3d-models/2019-bmw-x5-xdrive30d-850fb32f984c4630969840fc61f44902#download) → `2019_bmw_x5_xdrive30d.zip`
   - 7 Series (G70) → [2019 BMW X7 xDrive40i](https://sketchfab.com/3d-models/2019-bmw-x7-xdrive40i-a4b1edf1ec614f06b5d4db7208fe9650#download) → `2019_bmw_x7_xdrive40i.zip`

   All by Ddiaz Design, CC-BY-NC-SA-4.0 (credit the author, no commercial use). They never go into git.
4. **Install the cars and the local data** (feedback scores per part, option lists):
   ```bash
   pip install openpyxl
   python demo/visu/prepare_local.py --cars "<path>/car models"
   ```
5. **Fill your Rowboat knowledge** (Brands, Models, Components, Feature Classes, Assumptions, Requirements and
   `Data/BMW Dataset.xlsx`, all from the Dataset and the committed agent output; registers the note types):
   ```bash
   python demo/visu/vault.py notes
   python demo/visu/vault.py sync --watch          # keep running: Rowboat notes -> Torque
   ```
6. **RAG for Nordi** (optional; without it Nordi answers from Torque's data only). Docker must be running:
   ```bash
   docker compose -f docker-compose.qdrant.yml up -d
   python -m venv search/.venv
   search/.venv/Scripts/python -m pip install -r requirements.txt     # macOS: search/.venv/bin/python
   # put OPENAI_API_KEY=... into search/.env (copy search/.env.example; never commit it)
   search/.venv/Scripts/python scripts/ingest_qdrant.py --chunks-path outputs/chunks/chunks.jsonl
   search/.venv/Scripts/python -m uvicorn app:app --port 8100       # keep running
   ```
7. **Add Torque to Rowboat** (once), then open Rowboat → Apps → Torque:
   ```bash
   # Windows (cmd):  mklink /J %USERPROFILE%\.rowboat\apps\torque demo\torque
   # macOS:          ln -s "$PWD/demo/torque" ~/.rowboat/apps/torque
   ```

Optional: regenerate the agent's driver texts (needs RAG and the key): `search/.venv/Scripts/python
demo/visu/generate_texts.py`. Market MCP for Rowboat's agent: see [market/README.md](market/README.md).
Details: [demo/visu/README.md](demo/visu/README.md) (3D concept, data, agent, RAG).

## Docs

- [Deliverables](docs/deliverables.md): what the challenge expects, the requirement and audit-log schemas, and the AI vs. human workflow split
- [Data pipeline plan](docs/data-pipeline-plan.md): data sources, the provided datasets, the recommended G60 US demo, and the clustering approach
