# Data Pipeline Plan

Planning notes from the ideation session for the EHL Munich 2026 BMW challenge:
which data we use, how it flows from source to PM decision, and how we cluster customer feedback.

## How the data flows

Each item is linked to the one before it by an ID:

```
Source → Signal → Requirement → Priority → PM decision → Audit log
```

Every requirement must trace back to its sources, so every source record gets a stable ID from the moment it is ingested.

### 1. Provided BMW data (the internal "voice of customer")

- **Customer feedback text:** reviews, survey verbatims, call-center or customer-care tickets, dealer feedback. This is the main source for complaints and unmet needs.
- **Structured survey and quality data:** satisfaction or NPS scores, quality studies, clinic results. Used to measure severity and frequency.
- **Usage data:** configurator take rates for options and packages, connected-car feature usage, charging sessions. These show what customers actually use and buy, not just what they say.
- **Sales data:** lost-sale reasons and competitor conquest data, if provided. These point to competitor advantages.
- **Current product baseline:** the feature and spec list of the derivative in that market. Critical: without it we will "derive" requirements the car already meets.

### 2. External web enrichment

- **Competitor specs and configurators:** features, range, charging speed, packages and variants for 3–5 competitors in the same segment. These give competitor advantages and gaps.
- **Professional tests and reviews:** e.g. auto motor und sport, ADAC, What Car?, Car and Driver. Expert judgement on comfort, infotainment and driving experience.
- **Owner communities:** forums, Reddit, YouTube comments, App Store reviews of the My BMW app and competitors' apps. Good for digital-service complaints.
- **Market and trend data:** registrations and segment shares (KBA, ACEA, national statistics), EV adoption, charging infrastructure per market, consumer trend reports.
- **Regulatory sources, used only as a filter:** to exclude out-of-scope items. Requirements are not derived from them.

### 3. Reference data (makes the tool reusable)

- **Requirement taxonomy:** the in-scope categories from the brief (comfort, space, infotainment, charging experience, variants, …). Used to classify signals and reject anything out of scope.
- **Configuration per derivative and market:** model, market, language, competitor set, target customer profile. Swapping this config shows the tool isn't a one-off.
- **Multilingual synonym list:** e.g. "Reichweite" = "range" = "autonomía", so signals from different sources and languages cluster together.

### 4. Prioritization inputs

| Factor | Comes from |
| --- | --- |
| Frequency (how many independent sources mention it) | Feedback and web signals |
| Severity (sentiment, impact on satisfaction) | Surveys, quality data |
| Competitor gap | Competitor specs |
| Trend momentum (is it growing?) | Time-stamped signals, market data |
| Fit to target customer | Market config |
| Rough effort (S/M/L) | PM or team estimate (allowed by the brief) |

A transparent weighted score works well, as long as the PM can see and adjust the weights.

### 5. PM loop and audit trail

Data the app generates itself:

- **Decision records:** requirement ID, action (approve, reject, edit, challenge), old and new text, PM comment, user, timestamp.
- **System events:** ingestion runs, model version, prompts, scoring weights used, who viewed what.

Stored as an **append-only log**, never overwritten. That gives the complete chronological record the brief asks for.

### Minimum set for a strong demo

For one derivative in one market:

- The provided customer feedback
- The current feature list
- Specs for about three competitors from the web
- Owner forum or app review data
- A configuration file for the derivative and market
- The decision log

## The provided datasets

We have customer feedback, satisfaction studies, option lists and sales volumes. The obvious gap is competitor data, which comes from web research.

| File | What's in it | Pipeline stage |
| --- | --- | --- |
| F70 / G60 / G70 feedback (~4–5k rows each) | Verbatim customer comments with country, engine type (ICE/PHEV/BEV), source (A–D), feedback type (Likes / Wants / Difficult to Use / Defect), and a BMW category tree (Vfc level 2 and 3) | **Signal extraction.** Core evidence. "Wants" and "Difficult to Use" map directly to unmet needs and complaints. |
| Customer studies | Two sheets. `CN_EU_2025`: mean scores on ~30 attributes (seat comfort, infotainment ease of use, rear roominess…) for F70, G60, G68, G70. `US_2025`: rating distributions from "I hate it" to "I love it" on detailed items (door handles, wheel design…) for G60 and G70. | **Severity and validation.** Shows whether a complaint is confirmed by a large sample, and how badly an attribute scores. |
| Option lists (PDF, German price lists, mid-2026) | Standard equipment, packages (M Sportpaket, Pro, …), option codes, prices, package dependencies | **Product baseline.** Check whether a "want" is already available. Also feeds variant/package requirements and a rough cost/effort factor. |
| `sales_volumes` | Volumes for 2024, 2025, 2030 by region (EU, CN, US, RoW) per derivative | **Prioritization weight.** More volume counts for more. |
| Web (we add this) | Competitor specs and packages, expert reviews, forums, app reviews | **Competitor advantages and trends.** Not covered by the provided data. |

### Data issues to handle

- **Repeated IDs.** One comment appears in several rows when it has several category tags. F70 has 4,076 rows but only 2,128 unique comments. Count frequency per unique comment, not per row.
- **Missing classifications.** ~10–25% of rows are `no_class_found` or have an empty feedback type. Classifying these with an LLM is a good showcase for the AI part.
- **Different source formats.** Source A is the customer's own words, B is a dealer/agent paraphrase ("Customer stated…"), C is survey answers including the question text, D is short free text. Show which source each piece of evidence comes from.
- **Personal data.** At least one comment includes a customer's name and an email placeholder. Mask names before showing comments in the app, and log the masking in the audit trail.
- **Broken cell in sales volumes.** F70 China contains the formula `=-D3-C10`, pointing at empty cells. Treat F70 China as 0 / "no data", and say so.
- **Uneven market coverage:**
  - F70 is mostly Great Britain and Japan, ICE only.
  - G60 and G70 are mostly US, with all four sources and all three engine types.
  - China appears only in the studies (G68 and G70), with no comments.
- **Mixed languages.** Option lists are German, feedback is English, so we need a German–English mapping.

### Feedback sources A–D (inferred, to be confirmed with the organisers)

The dataset anonymises sources as A–D with no descriptions. These are inferences from the wording, not facts.

| Source | Size and markets | What it looks like | Likely origin |
| --- | --- | --- | --- |
| A | ~3,700 comments; GB, US, JP, KR and others. Only source for F70. | First-person owner reviews in lowercase, some mentioning ratings ("I only knock off one mark") | Owner review/rating platform or online owner survey, collected in many countries and translated into English |
| B | ~5,500 comments; US only | "Customer stated…", "Customer inquired… Writer explained…" | BMW customer care / call-centre logs (US Customer Relations), written by an agent |
| C | ~700 comments; US only | "I had a minor problem with Head-up display – DTU…", NPS questions, "one comment you would share with the manufacturer" | Structured new-vehicle quality survey in the style of J.D. Power IQS ("DTU" = difficult to use), plus NPS |
| D | ~270 comments; US only | "…That is the one thing I love most about the driving feel of my vehicle." | Sentence-completion survey in the style of J.D. Power APEAL |

Implications for the app:

- **Weighting.** A and D are the customer's own words; B is an agent's paraphrase and includes questions, not only complaints; C is a structured survey with reliable problem codes. Give each source a reliability weight and show it next to the evidence.
- **Market bias.** B, C and D are US only. A G60/G70 US demo can use all four sources; anything outside the US (including all of F70) relies on Source A alone.
- **Audit trail.** Record the source type with every piece of evidence, so the PM sees e.g. "6 call-centre logs + 3 quality-survey complaints".

**Action:** ask the organisers what A–D are — naming the real source types makes the evidence chain more convincing.

## Recommended demo: G60 (BMW 5 Series) in the US

This combination has the most evidence that fits together:

- Four feedback sources, ~4,400 US rows
- ICE, PHEV and BEV, so charging and range can be shown as the customer experiences them
- The detailed US study
- Second-largest market for G60, ~78k units in 2025

Then show it's not a one-off by switching the configuration to **F70 in Great Britain** with the same code.

### Data flow for G60 US

1. **Feedback** filtered to G60 + US: cluster the Wants, Difficult to Use and Defect comments into signals, keeping comment IDs as evidence.
2. **US study:** add a severity score per signal, e.g. share of "Unsatisfactory" or worse for that attribute.
3. **Option list:** check each signal against existing equipment; tag as existing feature, new feature, or package change.
4. **Web competitor data:** e.g. Mercedes E-Class, Audi A6, Tesla Model S. Flag where a competitor already offers what customers want.
5. **Sales volumes:** weight each requirement by its market.
6. **PM review and audit log.**

## Clustering the feedback

BMW already tags every comment with a category, so we cluster in three layers, from broad to specific.

### Layer 1: Theme (hand-written lookup table)

Each comment carries a component tag (`Vfc level2`, 221 values such as "Seats", "Electric Range", "Apple CarPlay") and an issue tag (`Vfc level3`, 82 values such as "Not user-friendly", "Customer request: function", "Range, not OK").

221 components are too many for a PM. Map them by hand, in one table, to ~10 themes from the brief's scope:

- Comfort & seats
- Space & storage
- Infotainment & operation
- Connectivity & digital services
- Range & charging
- Driving experience
- Exterior design
- Interior design & quality perception
- Access & convenience (doors, trunk, locking)
- Assistance & parking

The same table gives scope filtering for free:

- Engineering, safety or regulatory components get the tag `out_of_scope` — kept, but hidden from the PM.
- "Defect" comments mostly go to quality rather than requirements. Keep them only when they point to a design weakness.

### Layer 2: Issue cluster within each theme (the AI part)

The tags are too broad: "Body equipment, overall technology" + "Not user-friendly" can mean ten different problems. Inside each component/theme, group comments by meaning:

1. **Prepare the text.** Unique comments only, personal data masked, boilerplate stripped (Source C's question text, Source D's "That is the one thing I love most…", Source B's "Customer stated").
2. **Embed** each comment with a multilingual sentence model (e.g. `paraphrase-multilingual-MiniLM` or an API embedding model). Multilingual matters once German or Japanese web reviews come in.
3. **Cluster** with HDBSCAN (or BERTopic, which bundles embedding, clustering and labelling). It finds the number of clusters itself and marks one-off comments as noise.
4. **Name** each cluster with an LLM: it reads ~10 example comments and writes a label such as "Kick-to-open trunk sensor unreliable" or "Missing physical buttons for climate". Keep comment IDs as evidence.

For G60 US this is manageable: ~1,600 unique "Wants" / "Difficult to Use" comments. Top components include electric range (47), seats (42), kick-to-open trunk lid (40), public charging (33), Apple CarPlay (24).

**Simpler alternative:** skip embeddings and send each theme's comments in batches to an LLM, asking it to group them and return cluster labels with comment IDs. Easier to build, but harder to reproduce run to run. Embeddings are the stronger choice for the audit trail.

### Layer 3: Link clusters across the other datasets

| Link | How |
| --- | --- |
| Untagged comments (`no_class_found`, ~10–25%) | An LLM assigns them to an existing component or cluster. Log that the AI assigned it, not BMW's tagging. |
| Customer studies | Map each study item (e.g. "Ease of use of infotainment", "Rear roominess", "Exterior door handles") to a theme/cluster in the same lookup table. Each cluster then gets a survey score as severity. |
| Option list | Match cluster to option code. E.g. a "want ventilated seats" cluster is checked against the option list: offered? standard? only in a package? |
| Web and competitors | Assign new web snippets to the nearest existing cluster by embedding similarity, or start a new cluster. |
| Other derivatives | Run the same clustering on G70 and F70. A problem on several models is a platform signal (e.g. touchscreen operation), which strengthens its priority. |

### What one cluster looks like at the end

```
Cluster: "Trunk opens unintentionally / kick sensor unreliable"
Theme: Access & convenience   | Scope: in
Evidence: 27 comments (B:18, C:7, A:2)  BEV 15 / ICE 12
Feedback mix: 70% Difficult to Use, 20% Defect, 10% Wants
Survey link: US study "Ease of opening trunk" → 9% unsatisfactory
Option list: "Komfortzugang" option code …, standard on …
Competitor: (web) …
→ candidate requirement for PM review
```

That one record has everything prioritization needs: frequency, severity, source mix, market and competitor gap.

## Next steps

1. Build Layer 1 (component → theme lookup table) — quick, and makes everything after it explainable.
2. Ingestion script: clean the files into one evidence table (masked personal data, unique comments, mapped categories).
3. Run Layer 2 on G60 US and review the first list of clusters.
4. Ask the organisers what sources A–D are.
