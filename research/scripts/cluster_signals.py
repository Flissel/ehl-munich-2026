#!/usr/bin/env python3
"""
cluster_signals.py - reproducible pre-clustering of customer comments into candidate signals.

The agent (Claude) then reads each candidate cluster, names it, merges/splits where needed,
and turns it into a Signal record. Pre-clustering keeps the result reproducible and auditable;
the LLM adds meaning.

Usage:
    python scripts/cluster_signals.py --config config/G60_US.yaml --processed data/processed --out runs/G60_US

Method:
    1. filter comments by derivative / countries / engine types from the config
    2. keep in-scope + borderline themes, and the signal types listed in config (default: negative ones)
    3. per theme: vectorise text (TF-IDF word 1-2 grams, or sentence embeddings if installed)
       and run agglomerative clustering with a cosine distance threshold
    4. write clusters with size, source mix, engine mix, top terms and representative comment IDs
"""
import argparse, json, re, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd, yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity

STOP_EXTRA = ["customer", "stated", "vehicle", "car", "bmw", "really", "would", "like", "just", "also", "new",
              "mentioned", "explained", "writer", "series", "i'm", "it's", "don't", "the", "and"]

def vectorise(texts, method):
    if method == "embeddings":
        try:
            from sentence_transformers import SentenceTransformer
            m = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            return m.encode(texts, normalize_embeddings=True), None
        except Exception as e:
            print(f"[warn] embeddings unavailable ({e}); falling back to tf-idf")
    v = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_df=0.5, sublinear_tf=True,
                        stop_words=list(set(STOP_EXTRA) | set(TfidfVectorizer(stop_words="english").get_stop_words())))
    X = v.fit_transform(texts)
    return X.toarray(), v

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True); ap.add_argument("--processed", default="data/processed")
    ap.add_argument("--out", required=True); ap.add_argument("--method", default="tfidf", choices=["tfidf", "embeddings"])
    ap.add_argument("--threshold", type=float, default=None, help="cosine distance threshold (default from config or 0.85)")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(a.config, encoding="utf-8"))
    p, out = Path(a.processed), Path(a.out); out.mkdir(parents=True, exist_ok=True)
    thr = a.threshold or cfg.get("clustering", {}).get("distance_threshold", 0.85)
    min_size = cfg.get("clustering", {}).get("min_cluster_size", 3)

    tags = pd.read_csv(p / "evidence_tags.csv")
    com = pd.read_csv(p / "comments.csv")
    f = cfg["filter"]
    tags = tags[tags.derivative.isin(f["derivatives"])]
    if f.get("countries"):
        tags = tags[tags.country.isin(f["countries"])]
    if f.get("engine_types"):
        tags = tags[tags.engine_type.isin(f["engine_types"])]
    tags = tags[tags.scope.isin(f.get("scopes", ["in", "borderline", "review"]))]
    tags = tags[tags.signal_type.isin(f.get("signal_types", ["unmet_need", "usability_pain", "performance_gap", "defect"]))
                | (tags.theme_id == "UNCLASSIFIED")]

    # one assignment per comment: its most frequent in-scope theme (ties -> first)
    prim = (tags.groupby(["comment_id", "theme_id"]).size().reset_index(name="n")
            .sort_values(["comment_id", "n"], ascending=[True, False]).drop_duplicates("comment_id"))
    d = prim.merge(com, on="comment_id")
    d = d[~d.is_empty]
    comp = tags.groupby("comment_id").agg(components=("vfc_level2", lambda x: "|".join(sorted(set(map(str, x))))),
                                          signal_types=("signal_type", lambda x: "|".join(sorted(set(x)))))
    d = d.drop(columns=["components", "signal_types"]).merge(comp, on="comment_id")

    rows, assign = [], []
    for theme, g in d.groupby("theme_id"):
        g = g.reset_index(drop=True)
        if len(g) < min_size:
            labels = np.zeros(len(g), dtype=int); X = None; vec = None
        else:
            try:
                X, vec = vectorise(g.text.fillna("").tolist(), a.method)
            except ValueError:            # empty vocabulary (tiny theme)
                X, vec = None, None
            labels = np.full(len(g), -1)
            if X is not None:
                ok = np.linalg.norm(X, axis=1) > 0      # comments with no informative words -> noise
                if ok.sum() >= 2:
                    labels[ok] = AgglomerativeClustering(n_clusters=None, metric="cosine", linkage="average",
                                                         distance_threshold=thr).fit_predict(X[ok])
        g["local"] = labels
        for lab, cg in g.groupby("local"):
            cid = f"{cfg['run_id']}-{theme}-{max(lab,0):03d}"
            size = len(cg)
            if size < min_size or lab == -1:
                cid = f"{cfg['run_id']}-{theme}-NOISE"
            terms = []
            if vec is not None and size >= min_size and lab != -1:
                centroid = X[cg.index].mean(axis=0)
                terms = [vec.get_feature_names_out()[i] for i in np.argsort(centroid)[::-1][:8]]
            if X is not None and size >= 2:
                sims = cosine_similarity(X[cg.index], X[cg.index].mean(axis=0, keepdims=True)).ravel()
                reps = cg.iloc[np.argsort(-sims)[:8]].comment_id.tolist()
            else:
                reps = cg.comment_id.tolist()[:8]
            for cmt in cg.comment_id:
                assign.append(dict(comment_id=cmt, cluster_id=cid, theme_id=theme))
            if cid.endswith("NOISE"):
                continue
            rows.append(dict(
                cluster_id=cid, theme_id=theme, n_comments=size,
                weighted_n=round(cg.source_weight.sum(), 2),
                n_sources=cg.source.nunique(),
                source_mix=json.dumps(cg.source.value_counts().to_dict()),
                engine_mix=json.dumps(cg.engine_type.value_counts().to_dict()),
                country_mix=json.dumps(cg.country.value_counts().to_dict()),
                signal_mix=json.dumps(cg.signal_types.str.split("|").explode().value_counts().to_dict()),
                top_components=json.dumps(cg.components.str.split("|").explode().value_counts().head(5).to_dict()),
                top_terms=", ".join(terms),
                representative_ids="|".join(reps),
                representative_texts=" || ".join(com.set_index("comment_id").loc[reps].text.str[:220].tolist()),
            ))
    cl = pd.DataFrame(rows).sort_values("weighted_n", ascending=False)
    cl.to_csv(out / "candidate_clusters.csv", index=False)
    pd.DataFrame(assign).to_csv(out / "cluster_assignments.csv", index=False)
    meta = dict(run_id=cfg["run_id"], method=a.method, distance_threshold=thr, min_cluster_size=min_size,
                n_comments_in=int(d.comment_id.nunique()), n_clusters=len(cl),
                n_noise=int(sum(1 for x in assign if x["cluster_id"].endswith("NOISE"))))
    (out / "clustering_meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))
    print(cl[["cluster_id", "n_comments", "n_sources", "top_terms"]].head(25).to_string(index=False))

if __name__ == "__main__":
    main()
