#!/usr/bin/env python3
"""
prepare_data.py - turns the raw hackathon files into clean, agent-ready tables.

Usage:
    python scripts/prepare_data.py --raw data/raw --out data/processed

Expects in --raw (file names may carry prefixes, matching is by pattern):
    *<DERIV>_feedback_hackathon.xlsx     (one per derivative, e.g. F70, G60, G70)
    *customer_studies.xlsx               (sheets CN_EU_2025, US_2025)
    *sales_volumes.xlsx                  (one sheet per derivative)
    *<DERIV>_OptionList.PDF              (German price / option lists; needs `pdftotext`)

Writes to --out:
    comments.csv        one row per unique customer comment (cleaned, PII-masked)
    evidence_tags.csv   one row per (comment x BMW tag) with theme, scope, signal type
    study_scores.csv    long table of all study results, with theme + derived KPIs
    sales.csv           volumes per derivative x market x year (bad cells flagged)
    options_<D>.txt     full text of each option list (for search)
    options_<D>.csv     parsed option lines: section, name, option code, price
    manifest.json       row counts + data-quality notes  (log this in the audit trail)
"""
import argparse, json, re, subprocess, hashlib, datetime as dt
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent.parent
REF = HERE / "reference"

def norm(s):
    return re.sub(r"\s+", " ", str(s).replace("\xa0", " ")).strip() if pd.notna(s) else None

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]

# ---------------------------------------------------------------- text cleaning
C_PREFIX = re.compile(r"^.*?\?\s*(\|)?\s*:\s*", re.S)                       # survey question + ':'
C_PROBLEM = re.compile(r'^I had (?:a |an )?(?P<sev>very serious |serious |minor |moderate )?problem with (?P<item>.+?):\s*"', re.I)
D_SUFFIX = re.compile(r"\.?\s*That is (?:the )?one thing .*$", re.I | re.S)
B_PREFIX = re.compile(r"^Customer (stated|mentioned|said|expressed|inquired|requested|reported|asked)( that)?\s*", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"(?<![\w.])(?:\+\d{1,3}[\s-]?\(?\d{2,4}\)?|\(?0\d{2,4}\)?)[\s/-]?\d{3,4}[\s-]?\d{3,5}(?![\w.])")
NAME_BEFORE_EMAIL = re.compile(r"\b([A-Za-z][a-z]+ [A-Za-z][a-z]+)\s*\[EMAIL\]")
TITLE_NAME = re.compile(r"\b(mr|mrs|ms|dr)\.? [a-z]+(?: [a-z]+)?\b", re.I)
SIGNOFF = re.compile(r"\b((?i:kind regards|best regards|regards|sincerely|cheers|my name is))[,:]?\s+([A-Z][a-z]+(?: [A-Z][a-z]+)?)")

def mask_pii(t):
    n = 0
    for rx, rep in [(EMAIL, "[EMAIL]"), (PHONE, "[PHONE]"), (NAME_BEFORE_EMAIL, "[NAME] [EMAIL]"), (TITLE_NAME, "[NAME]")]:
        t, k = rx.subn(rep, t); n += k
    t, k = SIGNOFF.subn(lambda m: f"{m.group(1)} [NAME]", t); n += k
    return t, n

def clean(text, source):
    t = str(text) if pd.notna(text) else ""
    meta = {"voice": "customer", "survey_severity": None, "survey_item": None}
    if source == "Source B":
        meta["voice"] = "agent_paraphrase"
        t = B_PREFIX.sub("", t)
    elif source == "Source C":
        m = C_PROBLEM.match(t)
        if m:
            meta["survey_severity"] = (m.group("sev") or "unspecified").strip()
            meta["survey_item"] = m.group("item").strip()
            t = t[m.end():]
            t = t[:t.rfind('"')] if '"' in t else t
        elif "?" in t[:300]:
            t = C_PREFIX.sub("", t, count=1)
        t = t.strip().strip('"')
    elif source == "Source D":
        t = D_SUFFIX.sub("", t)
    t = re.sub(r"\s+", " ", t).strip()
    t, n_pii = mask_pii(t)
    meta["pii_masked"] = n_pii
    return t, meta

SOURCE_INFO = {  # inferred from text patterns - confirm with organisers
    "Source A": ("owner_review_or_online_survey", "customer", 1.0),
    "Source B": ("customer_care_log", "agent_paraphrase", 0.8),
    "Source C": ("quality_survey_IQS_style", "customer", 1.0),
    "Source D": ("appeal_survey_sentence_completion", "customer", 0.9),
}

# ---------------------------------------------------------------- feedback
def load_feedback(raw):
    tm = pd.read_csv(REF / "theme_mapping.csv"); tm["vfc_level2"] = tm.vfc_level2.map(norm)
    im = pd.read_csv(REF / "issue_mapping.csv")
    frames = []
    for f in sorted(raw.glob("*feedback_hackathon.xlsx")):
        d = pd.read_excel(f); d["file"] = f.name; frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    d.columns = ["comment_id", "source", "brand", "model", "country", "derivative", "engine_type",
                 "feedback_type", "text_raw", "vfc_level2_3", "vfc_level2", "vfc_level3", "file"]
    for c in ["brand", "model"]:
        d[c] = d[c].astype(str).str.strip("[]")
    d["vfc_level2"] = d.vfc_level2.map(norm)
    d["vfc_level3"] = d.vfc_level3.map(norm)
    d["feedback_type"] = d.feedback_type.fillna("unclassified")

    tags = d.merge(tm, on="vfc_level2", how="left").merge(im, on="vfc_level3", how="left")
    tags["theme_id"] = tags.theme_id.fillna("UNCLASSIFIED")
    tags["scope"] = tags.scope.fillna("review")
    tags["signal_type"] = tags.signal_type.fillna(
        tags.feedback_type.map({"Wants": "unmet_need", "Difficult to Use": "usability_pain",
                                "Defect": "defect", "Likes": "strength"})).fillna("unknown")
    tags["tag_id"] = tags.comment_id + "#" + tags.groupby("comment_id").cumcount().add(1).astype(str)

    # unique comments
    first = d.drop_duplicates("comment_id").copy()
    cleaned = first.apply(lambda r: clean(r.text_raw, r.source), axis=1)
    first["text"] = [c[0] for c in cleaned]
    for k in ["voice", "survey_severity", "survey_item", "pii_masked"]:
        first[k] = [c[1][k] for c in cleaned]
    first["source_type"] = first.source.map(lambda s: SOURCE_INFO.get(s, ("unknown",))[0])
    first["source_weight"] = first.source.map(lambda s: SOURCE_INFO.get(s, (0, 0, 0.8))[2])
    agg = tags.groupby("comment_id").agg(
        feedback_types=("feedback_type", lambda x: "|".join(sorted(set(x)))),
        themes=("theme_id", lambda x: "|".join(sorted(set(x)))),
        components=("vfc_level2", lambda x: "|".join(sorted(set(map(str, x))))),
        signal_types=("signal_type", lambda x: "|".join(sorted(set(x)))),
        n_tags=("tag_id", "count"))
    comments = first.merge(agg, on="comment_id")[[
        "comment_id", "derivative", "model", "country", "engine_type", "source", "source_type", "voice",
        "source_weight", "text", "survey_severity", "survey_item", "pii_masked", "feedback_types",
        "signal_types", "themes", "components", "n_tags", "file"]]
    comments["text_len"] = comments.text.str.len()
    comments["is_empty"] = comments.text_len < 3

    tags = tags.merge(comments[["comment_id", "text"]], on="comment_id")
    tags = tags[["tag_id", "comment_id", "derivative", "country", "engine_type", "source", "feedback_type",
                 "vfc_level2", "vfc_level3", "theme_id", "theme_name", "scope", "signal_type", "polarity",
                 "requirement_relevance", "text"]]
    return comments, tags

# ---------------------------------------------------------------- studies
US_LEVELS = ["I Hate It", "A Failure", "Unsatisfactory", "Satisfactory", "Excellent", "Delightful", "I Love It"]

def deriv_code(label):
    m = re.search(r"\b([FG]\d{2})\b", str(label))
    return m.group(1) if m else None

def load_studies(raw):
    f = next(raw.glob("*customer_studies.xlsx"))
    sm = pd.read_csv(REF / "study_mapping.csv")
    xs = pd.read_excel(f, sheet_name=None, header=None)
    rows = []
    # CN_EU: row1 = market per column (forward-filled), row2 = vehicle labels, then item / Mean pairs
    s = xs.get("CN_EU_2025")
    if s is not None:
        markets = s.iloc[1].ffill(); year = 2025
        cols = [c for c in s.columns[1:] if pd.notna(s.iloc[2, c])]
        for i in range(2, len(s) - 1):
            if str(s.iloc[i + 1, 0]).strip() == "Mean":
                item = norm(s.iloc[i, 0])
                for c in cols:
                    v = pd.to_numeric(s.iloc[i + 1, c], errors="coerce")
                    if pd.notna(v):
                        rows.append(dict(study="CN_EU_2025", market=markets[c], derivative=deriv_code(s.iloc[2, c]),
                                         vehicle=norm(s.iloc[2, c]), item=item, metric="mean_score_0_10", value=float(v)))
    # US: item row with vehicle labels, then 'Sample total' + 7 level rows (% of column)
    s = xs.get("US_2025")
    if s is not None:
        i = 0
        while i < len(s):
            if str(s.iloc[i, 0]).strip() != "Sample total" and i + 1 < len(s) and str(s.iloc[i + 1, 0]).strip() == "Sample total":
                item = norm(s.iloc[i, 0])
                header = s.iloc[0] if i else s.iloc[i]
                labels = {c: norm(s.iloc[0, c]) for c in s.columns[2:] if pd.notna(s.iloc[0, c])}
                block = s.iloc[i + 2:i + 9]
                for c, lab in labels.items():
                    dist = {str(block.iloc[k, 0]).strip(): pd.to_numeric(block.iloc[k, c], errors="coerce") for k in range(len(block))}
                    for lvl in US_LEVELS:
                        rows.append(dict(study="US_2025", market="US", derivative=deriv_code(lab), vehicle=lab,
                                         item=item, metric=f"share_{lvl}", value=dist.get(lvl)))
                    neg = sum(dist.get(l, 0) or 0 for l in US_LEVELS[:3])
                    top = sum(dist.get(l, 0) or 0 for l in US_LEVELS[5:])
                    rows += [dict(study="US_2025", market="US", derivative=deriv_code(lab), vehicle=lab, item=item,
                                  metric="pct_negative_bottom3", value=round(neg, 4)),
                             dict(study="US_2025", market="US", derivative=deriv_code(lab), vehicle=lab, item=item,
                                  metric="pct_delight_top2", value=round(top, 4))]
                i += 9
            else:
                i += 1
    st = pd.DataFrame(rows).merge(sm.rename(columns={"study_item": "item"}), on="item", how="left")
    st["theme_id"] = st.theme_id.fillna("UNMAPPED")
    # relative position vs. other vehicles of the same study/market (who is weakest on this item?)
    key = st.metric.isin(["mean_score_0_10", "pct_negative_bottom3"])
    st.loc[key, "rank_in_market"] = st[key].groupby(["study", "market", "item", "metric"]).value.rank(
        ascending=True, method="min")
    return st, f

# ---------------------------------------------------------------- sales
def load_sales(raw):
    f = next(raw.glob("*sales_volumes.xlsx"))
    out, issues = [], []
    import openpyxl
    wb = openpyxl.load_workbook(f)  # not data_only -> formulas visible
    formulas = {(ws.title, c.row, c.column_letter): c.value for ws in wb for row in ws.iter_rows() for c in row
                if isinstance(c.value, str) and c.value.startswith("=")}
    for (sh, r_, col_), val in formulas.items():
        hdr = wb[sh][f"{col_}1"].value; mk = wb[sh][f"B{r_}"].value
        issues.append(f"{sh}/{mk}/{hdr}: cell {col_}{r_} contains formula '{val}' (refers to empty/odd cells) -> volume set to missing")
    bad = {(sh, wb[sh][f"B{r_}"].value, wb[sh][f"{col_}1"].value) for (sh, r_, col_) in formulas}
    for sheet, d in pd.read_excel(f, sheet_name=None, dtype=str).items():
        for _, r in d.iterrows():
            for col in [c for c in d.columns if c.startswith("volume_")]:
                raw_v = r[col]; v = pd.to_numeric(raw_v, errors="coerce")
                flag = None
                if (sheet, r["market_code"], col) in bad:
                    v, flag = float("nan"), "formula cell in source - treated as missing"
                elif pd.isna(v):
                    flag = f"non-numeric cell '{raw_v}' -> treated as missing"
                    issues.append(f"{sheet}/{r['market_code']}/{col}: {flag}")
                out.append(dict(derivative_group=sheet, derivatives="|".join(sheet.split("_")), market=r["market"],
                                market_code=r["market_code"], year=int(col.split("_")[1]), volume=v, quality_flag=flag))
    return pd.DataFrame(out), issues, f

# ---------------------------------------------------------------- option lists
OPT_LINE = re.compile(r"^(?P<name>[^\s■□].*?[^\s■□])\s{2,}(?:(?P<code>[0-9][0-9A-Z]{2})\s+)?(?P<price>[\d.]+,[–-]+|–,–|Serie)?\s*(?P<rest>[■□][■□\s]*)$")
SECTION = re.compile(r"^[A-ZÄÖÜ][A-ZÄÖÜ /&,.-]{6,}\.?$")

def load_options(raw, out):
    res, issues = {}, []
    for f in sorted(raw.glob("*OptionList.PDF")) + sorted(raw.glob("*OptionList.pdf")):
        m = re.search(r"([FG]\d{2})_OptionList", f.name)
        dcode = m.group(1) if m else f.stem
        txt = out / f"options_{dcode}.txt"
        try:
            subprocess.run(["pdftotext", "-layout", str(f), str(txt)], check=True)
        except Exception as e:
            issues.append(f"{f.name}: pdftotext failed ({e})"); continue
        section, rows = None, []
        for line in txt.read_text(encoding="utf-8", errors="ignore").splitlines():
            s = line.strip()
            if SECTION.match(s) and not OPT_LINE.match(s):
                section = s.rstrip(".")
            mm = OPT_LINE.match(s)
            if mm and re.search(r"[A-Za-zÄÖÜäöü]", mm.group("name")):
                rest = mm.group("rest")
                rows.append(dict(derivative=dcode, section=section, option_name=mm.group("name"),
                                 option_code=mm.group("code"), price_eur_gross=mm.group("price"),
                                 n_variants_standard=rest.count("■"), n_variants_optional=rest.count("□")))
        if not rows:
            # e.g. an old poppler (Git for Windows) cannot decrypt the PDFs and writes empty text
            issues.append(f"{f.name}: no option lines parsed (unreadable or encrypted PDF?) -> skipped"); continue
        df = pd.DataFrame(rows).drop_duplicates(["option_code", "option_name"])
        df["availability"] = df.apply(lambda r: "standard_only" if r.n_variants_optional == 0 else
                                      ("standard_some" if r.n_variants_standard else "optional"), axis=1)
        df.to_csv(out / f"options_{dcode}.csv", index=False)
        res[dcode] = len(df)
    return res, issues

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    raw, out = Path(a.raw), Path(a.out); out.mkdir(parents=True, exist_ok=True)
    notes = []

    comments, tags = load_feedback(raw)
    comments.to_csv(out / "comments.csv", index=False)
    tags.to_csv(out / "evidence_tags.csv", index=False)
    notes.append(f"{len(tags)} tag rows collapse to {len(comments)} unique comments (one row per BMW tag in raw data) - count frequency on comments, not rows.")
    notes.append(f"{int((comments.themes == 'UNCLASSIFIED').sum())} comments have no BMW classification -> classify with LLM, log as 'ai_assigned'.")
    notes.append(f"{int(comments.pii_masked.gt(0).sum())} comments had PII masked by regex; LLM must still mask residual names.")
    notes.append("Source labels A-D are anonymised; source_type is inferred from text patterns - confirm with organisers.")

    st, sf = load_studies(raw); st.to_csv(out / "study_scores.csv", index=False)
    notes.append("Customer studies: CN_EU_2025 = mean scores (China: G68, G70; EU: F70, G60, G70); US_2025 = rating distributions (G60, G70). No study data for F70 outside EU.")

    sales, s_issues, slf = load_sales(raw); sales.to_csv(out / "sales.csv", index=False)
    notes += [f"Sales data issue: {i}" for i in s_issues]

    opts, o_issues = load_options(raw, out); notes += o_issues
    notes.append("Option lists are German (DE market, mid-2026). Use them as product baseline; map EN feedback terms to DE option names.")

    cov = comments.groupby(["derivative", "country", "source"]).size().reset_index(name="n_comments")
    cov.to_csv(out / "coverage.csv", index=False)

    manifest = {
        "run_at": dt.datetime.now().isoformat(timespec="seconds"),
        "inputs": {p.name: sha(p) for p in sorted(raw.iterdir()) if p.is_file()},
        "outputs": {"comments": len(comments), "evidence_tags": len(tags), "study_rows": len(st),
                    "sales_rows": len(sales), "option_lines": opts},
        "data_quality_notes": notes,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
