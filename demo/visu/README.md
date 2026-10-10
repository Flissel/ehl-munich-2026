# Torque Concept 3D: customer feedback heat map

Source of the 3D view in Torque's **Concept 3D** page (replaces the procedural concept car). A React +
Three.js app that colours every part of a real car model by customer feedback from `Dataset/`
(`F70`/`G60`/`G70_feedback_hackathon.xlsx`) and lets you restyle the car with a design prompt.
Built into `demo/torque/dist/visu/`; Torque embeds it in an iframe and passes the selected model
(1 Series → F70, 5 Series → G60, 7 Series → G70).

## Set up on a PC (once)

```bash
pip install openpyxl
python demo/visu/prepare_local.py --model <path>/2021_bmw_m4_competitionglTF.zip
```

This writes two **local, gitignored** folders next to the build:
- `dist/visu/data/feedback-*.json`: scores per part, with sample customer quotes (kept out of git like Torque's `quotes.json`).
- `dist/visu/models/bmw-m4-competition-2021/`: the car. "2021 BMW M4 Competition" by Ricy
  (sketchfab.com/ngon_3d), **CC-BY-NC-4.0**: credit required, no commercial use. Get the zip from
  Sketchfab or a teammate. It stands in for the 1/5/7 Series.

Then install Torque as in `demo/torque/README.md`; the 3D view is at Concept 3D.

## How it works

- **Heat map:** score = rank of the weighted positive share of comments per part (0 = most criticised,
  100 = best rated), exterior and interior ranked separately (`feedback.py`). Click a part for counts and quotes.
- **Design prompt:** sent to the model configured in Rowboat (`/_rowboat/llm/generate`, Torque's `llm`
  capability). Outside Rowboat a keyword matcher answers. Every action is validated and clamped in
  `src/lib/interpret.ts` (colors and finishes; scaling, moving or hiding parts, ride height, wheel size,
  track width, body proportions). New geometry is never generated.

## Change the app

```bash
cd demo/visu
npm ci
npm run dev     # http://127.0.0.1:5174, uses the local data/ and models/
npm run build   # rebuilds demo/torque/dist/visu/assets (commit the result)
```
