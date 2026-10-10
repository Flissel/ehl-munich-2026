import pytest

from ehl_market import analysis, fetch, methods, store
from ehl_market.countries import to_iso2
from ehl_market.sources import BY_ID, SOURCES


@pytest.fixture(autouse=True)
def tmp_home(tmp_path, monkeypatch):
    monkeypatch.setenv("EHL_MARKET_HOME", str(tmp_path))


def _row(country, value, metric="m", year=2024, source_id="worldbank", **kw):
    return {"country": country, "year": year, "period": str(year), "metric": metric, "value": value,
            "unit": "", "source_id": source_id, "url": "u", **kw}


def test_country_codes():
    assert to_iso2("GBR") == "GB"
    assert to_iso2("UK") == "GB"
    assert to_iso2("Korea, Rep.") == "KR"
    assert to_iso2("Germany") is None


def test_registry_ids_unique_and_tiers_valid():
    assert len(BY_ID) == len(SOURCES)
    assert all(s.tier in (1, 2, 3) for s in SOURCES)


def test_jsonstat_flatten():
    body = {"id": ["geo", "time"], "size": [2, 2],
            "dimension": {"geo": {"category": {"index": {"DK": 0, "NO": 1}}},
                          "time": {"category": {"index": {"2024-S1": 0, "2024-S2": 1}}}},
            "value": {"0": 1.0, "3": 4.0}}
    rows = fetch._jsonstat_rows(body)
    assert {"geo": "DK", "time": "2024-S1", "value": 1.0} in rows
    assert {"geo": "NO", "time": "2024-S2", "value": 4.0} in rows


def test_survey_values_need_question_base_and_fieldwork():
    with pytest.raises(ValueError, match="question_wording"):
        store.validate_manual(_row("JP", 47, source_id="deloitte_gacs"))
    ok = store.validate_manual(_row("Japan", 47, source_id="deloitte_gacs", question_wording="q",
                                    population="all_respondents", sample_size=944, fieldwork="2025-09"))
    assert ok["country"] == "JP"


def test_unknown_source_and_country_rejected():
    with pytest.raises(ValueError, match="not in registry"):
        store.validate_manual(_row("JP", 1, source_id="some_blog"))
    with pytest.raises(ValueError, match="not one of the 13"):
        store.validate_manual(_row("DE", 1))


def test_upsert_replaces_same_key():
    store.upsert([_row("JP", 1)])
    res = store.upsert([_row("JP", 2), _row("KR", 3)])
    assert res == {"inserted": 1, "replaced": 1, "total": 2}
    assert store.load().set_index("country").loc["JP", "value"] == 2


def test_correlate_external_metrics_and_mixed_source_guard():
    cs = ["AU", "CA", "DK", "FR", "GB", "JP", "KR", "SE"]
    store.upsert([_row(c, i, "a") for i, c in enumerate(cs)] + [_row(c, i * 2, "b") for i, c in enumerate(cs)])
    r = analysis.correlate("a", "b")
    assert r["n_countries"] == 8 and r["spearman_rho"] == 1.0
    store.upsert([_row("US", 5, "a", source_id="oecd")])
    with pytest.raises(ValueError, match="several sources"):
        analysis.correlate("a", "b")


def test_too_few_countries_not_computed():
    store.upsert([_row(c, i, "a") for i, c in enumerate(["AU", "CA", "DK"])] +
                 [_row(c, i, "b") for i, c in enumerate(["AU", "CA", "DK"])])
    assert "not computed" in analysis.correlate("a", "b")["status"]


def test_wtp():
    assert methods.wtp(0.8, -0.0004)["wtp"] == 2000.0
    with pytest.raises(ValueError):
        methods.wtp(0.8, 0.1)


def _three_metrics():
    cs = ["AU", "CA", "DK", "FR", "GB", "JP", "KR", "SE"]
    store.upsert([_row(c, i, "a") for i, c in enumerate(cs)] + [_row(c, -i, "b") for i, c in enumerate(cs)]
                 + [_row(c, (i * 7) % 5, "c") for i, c in enumerate(cs)])


def test_matrix_pairs_and_sensitivity_sign():
    from ehl_market import explore
    _three_metrics()
    m = explore.matrix(["a", "b", "c"], n_boot=200)
    ab = next(p for p in m["pairs"] if {p["x"], p["y"]} == {"a", "b"})
    assert ab["rho"] == -1.0 and ab["n"] == 8 and "q" in ab
    s = explore.sensitivity("a", delta_sd=2.0, metrics=["a", "b", "c"], n_boot=200)
    assert s[0]["metric"] == "b" and s[0]["expected_change_sd"] == -2.0


def test_export_html_embeds_data(tmp_path):
    from ehl_market import explore
    _three_metrics()
    out = tmp_path / "x.html"
    explore.export_html(str(out), metrics=["a", "b", "c"], n_boot=50)
    html = out.read_text(encoding="utf-8")
    assert "/*__DATA__*/null" not in html and '"pairs"' in html


def test_ranking_external_is_bonus_only():
    from ehl_market import ranking
    w = {"frequency": 0.5, "tone": 0.3, "external": 0.2}
    assert ranking._base(1.0, 1.0, w) == 1.0
    assert ranking._terms("The writer advised the Head-up display fails") == {
        "head-up", "display", "fails", "head-up display", "display fails"}
