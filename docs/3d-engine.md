# The 3D engine: Concept 3D

Concept 3D shows the successor car as a 3D model. Each part is coloured by what customers say about it, from
red (most criticised) to green (best rated). The view is linked to Torque's purchase drivers: click a driver
and the camera flies to its part, click a part and its driver opens. A design prompt reshapes the car's
proportions. It runs in the browser inside the Torque app in Rowboat.

## Stack

| Layer | Technology |
| --- | --- |
| Rendering | [three.js](https://threejs.org) 0.186 |
| Scene graph in React | [@react-three/fiber](https://github.com/pmndrs/react-three-fiber) 9.8 and [@react-three/drei](https://github.com/pmndrs/drei) 10.7 (`useGLTF`, `Environment` with light formers, `ContactShadows`, `OrbitControls`) |
| UI | React 19, TypeScript |
| Build | Vite 8: `demo/visu` builds into `demo/torque/dist/visu/` (the build is committed, so nobody needs Node to run the demo) |
| Data preparation | Python 3.12 (`demo/visu/feedback.py`, `options.py`, `prepare_local.py`, `vault.py`) |

The source is in `demo/visu/src/`:

| File | Role |
| --- | --- |
| `viewer/CarViewer.tsx` | Canvas, lights, shadows, camera presets (exterior, interior, cutaway), loading and scaling the car |
| `lib/segmentation.ts` | Splits the car's meshes into named components |
| `lib/heatmap.ts` | Maps a score from 0 to 100 to a colour |
| `lib/design.ts`, `lib/deform.ts` | Proportion edits, such as a longer hood or a lower roof |
| `lib/interpret.ts` | Turns a design prompt into validated design actions |
| `models/template.ts`, `cars.ts`, `registry.ts` | The catalogue of 56 components, plus a profile per car (materials, dimensions, absent parts) |

## Pipeline

```
Dataset/{F70,G60,G70}_feedback_hackathon.xlsx ─ feedback.py ─┐
outputs/markdown/options/processed/*.md ──────── options.py ──┤ prepare_local.py ─► dist/visu/data/feedback-*.json
Sketchfab glTF zips (X1, X5, X7) ───────────────────────────┘                    dist/visu/data/options-*.json
                                                                                  dist/visu/models/<car>/scene.gltf
Rowboat vault Components/ ── vault.py sync --watch ─► dist/visu/data/visu.json  (every 2 s)
                                       vault.py graph ─► dist/visu/graph.json   (driver ↔ part links)

browser:  useGLTF ─► scale to real length ─► segmentModel ─► score per component ─► scoreToColor ─► per-part materials
Torque ◄── postMessage (visu:context / visu:ready / visu:select) ──► Concept 3D iframe (visu/index.html?embed=1)
```

## 1. Models

The Dataset covers the 1, 5 and 7 Series (F70, G60, G70). The viewer uses one free Sketchfab model from each
family as a stand-in: a 2020 BMW X1, a 2019 BMW X5 and a 2019 BMW X7, all by Ddiaz Design under
CC BY-NC-SA 4.0. The models are not in git. Each user downloads them, and `prepare_local.py --cars` unzips
them into `dist/visu/models/<car>/` (run through `scripts/install.py`).

There is no offline conversion. In the browser the car is scaled to its real length (4.447 m, 4.922 m or
5.151 m) and placed on the ground.

## 2. Segmentation into 56 components

Sketchfab models are not split into BMW parts, so `segmentModel` does the split at runtime in two ways:

- **Material roles.** Each car's profile in `cars.ts` assigns its glTF materials to roles: paint, trim,
  glass, lights, tyres, rims, seats and so on.
- **Regions.** Each triangle's centroid is placed in a normalised car frame (x −1…1, y 0…1, z −1…1).
  Regions cut a role into parts, for example paint into the front-left fender or the hood.

The split only creates new index buffers. Geometry is not copied. Parts cut out by region are approximate
and marked ≈ in the UI. Parts a model does not have are listed as absent: the front splitter on all three
cars, and the rear diffuser on the X7. The 56 component IDs are shared by the heat map, Torque's purchase
drivers and the Rowboat notes in `Components/`.

## 3. Heat map

`feedback.py` reads every classified comment. A comment's feature class ("Vfc level2 Name", for example
"Wheels / tires") points to one or more components through the `SPECIFIC` table. The feedback type sets the
weight:

| Feedback type | Weight |
| --- | --- |
| Likes | +1 |
| Wants | −0.5 |
| Difficult to Use | −1 |
| Defect | −1.5 |

For each component:

```
positive share = (positive + 2) / (positive + negative + 4)      # prior of 2 pseudo-counts per side
score          = rank of that share among the car's exterior (or interior) components, 0…100
```

- **Why a rank.** Absolute shares differ a lot between exterior and interior, and between markets. A rank
  shows what is most criticised *on this car*.
- **No specific feedback.** A component without specific feedback gets a neutral 50 and is flagged.
- **Per series and market.** Scores exist for every series (all, F70, G60, G70) and market (EU, US, CN,
  RoW), taken from each comment's country.

`heatmap.ts` maps the score to colour through five stops:

| Score | Colour | Name |
| --- | --- | --- |
| 0 | `#ff2020` | red |
| 25 | `#ff7a1a` | orange |
| 50 | `#ffe600` | yellow |
| 75 | `#9be22d` | light green |
| 100 | `#20d65a` | green |

Each component gets its own material. Glass stays half-transparent, and meshes that map to no component are
neutral grey.

**Order of precedence** when several sources have a score for a part:

1. Torque's China override, based on the customer study, because there are no Chinese comments.
2. Rows edited in Rowboat's `Components/` notes.
3. The feedback JSON.
4. Synthetic scores.

So when Rowboat's agent or a PM edits a component note, the car changes colour within seconds.

## 4. Inside Torque

Torque's Concept 3D page embeds the viewer once as an iframe: `visu/index.html?embed=1`. The two sides talk
through `postMessage`:

- **`visu:context`** (Torque → viewer): model, market, the focused purchase driver and the China override.
- **`visu:ready`** and **`visu:select`** (viewer → Torque): the viewer has loaded, or the user clicked a part.

Changing the model or market does not reload the car. The info card shows the part's score, its comment
counts, a customer quote and the matching options from the price list.

## 5. Design prompt

The PM can type a change such as "make the hood longer and the roof lower". `interpret.ts` sends it to the
model the user set in Rowboat, through the app API `/_rowboat/llm/generate`. It then validates every
returned action against an allowed list and clamps the values. `deform.ts` applies the edits as vertex
offsets on the existing geometry. No new geometry is created, and design mode shows the original materials.

## 6. Experimental: Unreal Engine (branch `feat/visu-pro`, not merged)

`feat/visu-pro` is the ancestor of this engine. It is a "BMW Design Studio" built around one M4 model, with
a FastAPI backend and an **Unreal Engine 5.8** project for photoreal renders. `heatmap.ts` and
`segmentation.ts` are identical on both branches. On `main` the Python scoring moved into static JSON, and
the three Dataset cars replaced the M4. The "Visualize in Unreal" button stays disabled for X1, X5 and X7.

## Licences

- three.js, React Three Fiber, drei, React and Vite: MIT.
- Car models: Ddiaz Design, CC BY-NC-SA 4.0 (attribution, non-commercial, never committed). The credit is
  shown in the viewer (`cars.ts`).

See [NOTICE](../NOTICE).
