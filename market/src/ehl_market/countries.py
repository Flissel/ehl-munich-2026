"""The 13 markets that have BMW customer comments in Dataset/ (coverage.csv), with the codes each
external source uses for them and the BMW sales region (sales.csv only has 4 regions)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Country:
    iso2: str
    iso3: str
    name: str
    eurostat: str | None  # None = not covered by Eurostat
    sales_region: str  # market_code in sales.csv: EU / US / RoW (CN is not one of the 13)


COUNTRIES: dict[str, Country] = {
    c.iso2: c
    for c in [
        Country("AU", "AUS", "Australia", None, "RoW"),
        Country("CA", "CAN", "Canada", None, "RoW"),
        Country("DK", "DNK", "Denmark", "DK", "EU"),
        Country("ES", "ESP", "Spain", "ES", "EU"),
        Country("FI", "FIN", "Finland", "FI", "EU"),
        Country("FR", "FRA", "France", "FR", "EU"),
        Country("GB", "GBR", "United Kingdom", None, "EU"),  # Eurostat stopped most UK series in 2020
        Country("JP", "JPN", "Japan", None, "RoW"),
        Country("KR", "KOR", "Korea", None, "RoW"),
        Country("NO", "NOR", "Norway", "NO", "EU"),
        Country("SE", "SWE", "Sweden", "SE", "EU"),
        Country("US", "USA", "United States", None, "US"),
        Country("ZA", "ZAF", "South Africa", None, "RoW"),
    ]
}

_BY_ISO3 = {c.iso3: c.iso2 for c in COUNTRIES.values()}
_BY_NAME = {c.name.lower(): c.iso2 for c in COUNTRIES.values()}
_BY_NAME.update(
    {
        "uk": "GB",
        "united kingdom of great britain and northern ireland": "GB",
        "korea, rep.": "KR",
        "south korea": "KR",
        "republic of korea": "KR",
        "usa": "US",
        "united states of america": "US",
    }
)


def to_iso2(code: str) -> str | None:
    """Normalise ISO2, ISO3 or an English country name to ISO2; None if not one of the 13."""
    if not code:
        return None
    raw = str(code).strip()
    up = raw.upper()
    if up in COUNTRIES:
        return up
    if up == "UK":
        return "GB"
    if up in _BY_ISO3:
        return _BY_ISO3[up]
    return _BY_NAME.get(raw.lower())
