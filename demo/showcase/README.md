# Pitch showcase

`index.html` is one self-contained page for the pitch and the jury: data basis, customer voice, workflow,
requirement records, audit trail, live demo steps and, at the end, the knowledge graph and the top 10
attributes. Open it in a browser; nothing to install.

It doubles as the fallback if a live Rowboat step fails on stage (WP1 spec, section 6).

## Two data blocks

| Block | Content | Who writes it |
|---|---|---|
| `<script id="data-real">` | Aggregates from `Dataset/` and `demo/link-targets.json`: feedback counts and pain points per derivative, study means (CN and EU 2025), sales plan, top 10 study gaps, graph base nodes | `fill_data.py` only |
| `<script id="data-team">` | Product name, claim, requirement texts and scores, audit events, demo screenshots, companies, closing line | the team, by hand |

Every value written as `{"ph": "what goes here", "from": "where it comes from"}` renders as a dashed
placeholder. The button **Placeholders N** in the header counts them and switches the marking off for a
dry run; the list at the bottom of the page shows each one with its JSON path. Replace the object with a
plain string (or an image path or URL for screenshots) and the placeholder disappears.

Requirement records only need the fields that exist; missing ones (title, description, score, priority,
evidence, rationale, assumptions, uncertainties) show as placeholders. `signal` (`pain|<category>`) and
`study` (attribute name) are looked up in the real data, so the counts stay correct after a refresh.

## Refresh the real data

```bash
pip install pandas openpyxl
python demo/showcase/fill_data.py            # reads Dataset/, rewrites only the data-real block
python -m pytest demo/showcase -q
```

Only counts, means and volumes leave the script. No comment text, names or contact details (spec D8).
