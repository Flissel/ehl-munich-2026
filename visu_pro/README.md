# BMW Design Studio

Web heat map viewer (React + Three.js) for the 2021 BMW M4 Competition glTF, plus an optional
detailed Unreal Engine 5.8 viewer launched from the web page.

## Start (Windows PowerShell)

```powershell
# Backend (once: create venv + install)
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env          # optional: set OPENAI_API_KEY=... (otherwise keyword demo mode)
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000

# Frontend (second terminal)
cd frontend
npm install
npm run dev                     # copies the glTF into public/models, serves http://127.0.0.1:5173
```

Open http://127.0.0.1:5173. The heat map works without the backend; the prompt and the Unreal
button need it.

Optional, once, for the Unreal button: `.\scripts\build_unreal.ps1` (imports the FBX into the
Unreal project). The first Unreal launch compiles shaders and can take several minutes.

## Web app
- Real model from `2021_bmw_m4_competitionglTF.zip`, extracted to
  `assets/extracted/bmw-m4-competition-2021-gltf/` and copied to `frontend/public/models/`.
- 38 exterior components mapped from glTF node names (`frontend/src/models/bmw-m4-competition-2021.ts`).
  Components marked ≈ are carved out of a merged mesh by position (approximate): the asset's
  `Body` mesh holds hood/roof/fenders/quarters/trunk, `bumpers` holds front+rear, lights and
  skirts hold both sides, mirrors live inside the door meshes.
- Scores are **synthetic demo values** (`frontend/src/data/syntheticScores.ts`), color scale
  `scoreToColor()` in `frontend/src/lib/heatmap.ts`. Interior parts are not scored (neutral grey).
- Click a part or a list row to select it; Esc or ✕ deselects.
- Design prompt → `/api/web/design` (OpenAI Responses API if `OPENAI_API_KEY` is set, otherwise a
  keyword demo). Paint and wheel finish are applied in the web "Design" view; geometry requests
  (e.g. bumper redesign) are shown as "Proposed only".
- **Visualize in Unreal Engine** → `/api/unreal/visualize`: if UE 5.8 and the built project are
  found, launches the local standalone viewer and applies the current web design; otherwise
  reports "not configured". Pixel Streaming can replace the launcher later (`backend/viewer.py`).

## License
Model: "2021 BMW M4 Competition" by Ricy (https://sketchfab.com/ngon_3d), CC-BY-NC-4.0 —
credit required, **no commercial use**. Do not redistribute the model commercially.

## Heat map from customer feedback (EHL dataset)
Clone https://github.com/Flissel/ehl-munich-2026 next to this folder (or set `FEEDBACK_DATASET_DIR`
in `backend/.env`). The backend reads `Dataset/{F70,G60,G70}_feedback_hackathon.xlsx` at startup
(`backend/feedback.py`), maps feature classes (e.g. "Exterior rearview mirror", "Trunk lid",
"Wheels / tires") onto the 3D components and scores each part 0-100 by the rank of its share of
positive feedback (0 = most criticised, 100 = best rated). Parts without specific feedback get a
neutral 50. Select the series (F70 / G60 / G70 / all) in the "Heat map data" box; click a part to
see comment counts and real quotes. The data is for the 1/5/7 Series; the M4 model is a stand-in.

## Design prompt levels (web)
- Level 1: any color + finish (gloss, metallic, matte, satin, chrome, carbon) on the body, the wheels
  or any single component.
- Level 2: scale / move / remove existing parts, ride height, wheel size, track width
  (real 3D transforms in the browser, bounded and validated server-side in `backend/web_design.py`).
- Not possible: generating brand-new geometry; such requests are listed as "Proposed only".

## Interior
Use the viewer buttons **Exterior / Interior / Cutaway**. Interior puts the camera at the driver's eye
(drag to look around, scroll to zoom); Cutaway hides roof, glass and headliner and looks in from above.
18 interior components are mapped (seats, rear seats, instrument cluster, central display, climate
panel, centre console, dashboard, steering wheel, pedals, door trims, overhead console with SOS,
headliner, sills, seat belts, interior mirror, sun visors) with their own feedback classes; exterior and
interior are ranked separately. Feedback without geometry in this model (cooling/fridge, rear-seat
entertainment) is listed separately. Clicks pass through glass to the part behind it.