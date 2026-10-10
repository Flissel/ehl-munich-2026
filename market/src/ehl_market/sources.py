"""Curated registry of external sources: how credible each one is and how to retrieve it.

Credibility tiers (what the agent may do with a value):
  1  Official statistics, regulators, independent test bodies. Documented method, full coverage.
     -> may be used as a model variable.
  2  Established commercial research with a published method, sample size and fieldwork period
     (Deloitte, J.D. Power, ...). -> model variable only with question wording, base and year stored.
  3  Press, trade media, forums, blogs, vendor marketing. -> context and hypotheses only, never a
     model variable.

`tool` names the MCP tool that retrieves the source; None means a person (or the agent's web tools)
reads the report and enters values with `add_observation`, citing page/table and question.
"""

from dataclasses import asdict, dataclass, field

NEEDS = ("affordability", "ev_convenience", "safety_tech", "context")


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    publisher: str
    tier: int
    kind: str  # official_statistics | regulator_test | consumer_survey | quality_survey | industry_association | registrations
    needs: tuple[str, ...]
    measures: str
    coverage: str
    access: str  # api | file | report | web
    retrieval: str
    url: str
    cost: str  # free | free_summary_paid_detail | paid
    caveats: str
    tool: str | None = None
    countries: tuple[str, ...] = field(default_factory=tuple)  # empty = all 13 / multi-country

    def as_dict(self) -> dict:
        return asdict(self)


SOURCES: list[Source] = [
    # ---- Tier 1: official statistics and international agencies -------------------------------
    Source(
        "worldbank", "World Development Indicators", "World Bank", 1, "official_statistics",
        ("affordability", "context"),
        "GDP/GNI per capita PPP, inflation, lending rate, urbanisation, renewable electricity share",
        "All 13 markets, annual", "api",
        "REST, no key: api.worldbank.org/v2/country/{ISO3;...}/indicator/{code}?format=json",
        "https://datahelpdesk.worldbank.org/knowledgebase/articles/889392", "free",
        "Annual and ~1 year lag; lending-rate series is patchy for some high-income countries.",
        tool="fetch_worldbank",
    ),
    Source(
        "eurostat", "Eurostat database", "European Commission", 1, "official_statistics",
        ("affordability", "ev_convenience", "context"),
        "Household electricity prices (nrg_pc_204), income, HICP, registrations by fuel (road_eqr_carpda)",
        "DK ES FI FR SE + NO; not GB after 2020; not AU CA JP KR US ZA", "api",
        "JSON-stat 2.0: ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}?filters",
        "https://wikis.ec.europa.eu/display/EUROSTATHELP/API+Statistics+-+data+query", "free",
        "Electricity prices are half-yearly (2025-S1); average the semesters or pick one consistently.",
        tool="fetch_eurostat", countries=("DK", "ES", "FI", "FR", "SE", "NO"),
    ),
    Source(
        "oecd", "OECD Data Explorer", "OECD", 1, "official_statistics",
        ("affordability", "context"),
        "Household disposable income, PPPs, CPI, long/short-term interest rates",
        "All 13 except ZA for some series (ZA is a key partner, partial coverage)", "api",
        "SDMX REST: sdmx.oecd.org/public/rest/data/{agency},{dataflow},{version}/{key}; build the "
        "query in the Data Explorer and copy the 'Developer API' URL",
        "https://www.oecd.org/en/data/insights/data-explainers/2024/09/api.html", "free",
        "Dataflow IDs changed with the 2024 Data Explorer migration; old OECD.Stat URLs break.",
    ),
    Source(
        "iea_gevo", "Global EV Outlook / Global EV Data Explorer", "International Energy Agency", 1,
        "official_statistics", ("ev_convenience",),
        "EV sales share, EV stock, public slow/fast chargers, by country and year (CSV columns: "
        "region, category, parameter, mode, powertrain, year, unit, value)",
        "All 13 (ZA small/partly aggregated), annual, with projections flagged as category 'Projection-*'",
        "file", "Download the CSV from the Data Explorer, then import_iea_ev(path). Keep only category "
        "'Historical' for modelling.",
        "https://www.iea.org/data-and-statistics/data-tools/global-ev-data-explorer", "free",
        "CC BY 4.0. Never mix 'Projection' rows into observed data.",
        tool="import_iea_ev",
    ),
    Source(
        "eafo", "European Alternative Fuels Observatory", "European Commission (DG MOVE)", 1,
        "official_statistics", ("ev_convenience",),
        "Public charging points, chargers per EV, AF registrations",
        "EU + NO, GB (+ others in Europe)", "web", "Country pages with downloadable tables; import with "
        "import_table", "https://alternative-fuels-observatory.ec.europa.eu/", "free",
        "Definitions of 'charging point' changed over time; compare within one vintage.",
        tool="import_table",
    ),
    Source(
        "afdc", "Alternative Fuels Station Locator API", "US DOE / NREL", 1, "official_statistics",
        ("ev_convenience",), "Public charging stations and ports (US, CA)", "US, CA", "api",
        "developer.nrel.gov/api/alt-fuel-stations/v1 - free API key required",
        "https://developer.nrel.gov/docs/transportation/alt-fuel-stations-v1/", "free",
        "Snapshot, not history; store the retrieval date as the period.",
        countries=("US", "CA"),
    ),
    # ---- Tier 1: regulators and independent safety test bodies ----------------------------------
    Source(
        "nhtsa", "NHTSA complaints, recalls, NCAP ratings", "US National Highway Traffic Safety Admin.", 1,
        "regulator_test", ("safety_tech",),
        "Owner safety complaints by component, recall campaigns, 5-star NCAP ratings by make/model/year",
        "US only, by vehicle", "api",
        "api.nhtsa.gov/complaints/complaintsByVehicle, /recalls/recallsByVehicle, /SafetyRatings - no key",
        "https://www.nhtsa.gov/nhtsa-datasets-and-apis", "free",
        "Complaints are self-reported counts, not defect rates: divide by sales/fleet before comparing models.",
        tool="nhtsa_vehicle", countries=("US",),
    ),
    Source(
        "euroncap", "Euro NCAP ratings", "Euro NCAP", 1, "regulator_test", ("safety_tech",),
        "Star rating + scores for adult/child occupant, vulnerable road users, Safety Assist",
        "Europe (DK ES FI FR GB NO SE)", "web",
        "No public API: read the model's datasheet PDF, enter scores with add_observation",
        "https://www.euroncap.com/en/ratings-rewards/latest-safety-ratings/", "free",
        "Protocols tighten every ~2-3 years; compare stars only within one protocol year.",
    ),
    Source(
        "ancap", "ANCAP safety ratings", "ANCAP", 1, "regulator_test", ("safety_tech",),
        "Star ratings aligned with Euro NCAP protocols", "AU (and NZ)", "web",
        "Model pages; manual entry", "https://www.ancap.com.au/", "free",
        "Many ratings are adopted from Euro NCAP tests.", countries=("AU",),
    ),
    Source(
        "iihs", "IIHS ratings", "Insurance Institute for Highway Safety", 1, "regulator_test",
        ("safety_tech",), "Crashworthiness, crash avoidance, headlights, Top Safety Pick",
        "US", "web", "Model pages; manual entry (check terms before scraping)",
        "https://www.iihs.org/ratings", "free",
        "Insurer-funded but independent and methodologically documented.", countries=("US",),
    ),
    Source(
        "kncap_jncap", "KNCAP / JNCAP", "KOTSA (Korea) / NASVA (Japan)", 1, "regulator_test",
        ("safety_tech",), "National NCAP results", "KR, JP", "web", "Published result tables; manual",
        "https://www.car.go.kr/ (KNCAP), https://www.nasva.go.jp/mamoru/ (JNCAP)", "free",
        "Few premium imports are tested; BMW models are often missing.", countries=("KR", "JP"),
    ),
    # ---- Tier 1: national registrations (what people actually bought) ---------------------------
    Source("reg_au", "VFACTS", "FCAI", 1, "registrations", ("ev_convenience", "context"),
           "New-vehicle sales by brand/model/fuel", "AU", "report",
           "Monthly press tables free; full VFACTS by subscription. Tesla/Polestar are reported "
           "separately (EVDirect) - add them or EV share is undercounted",
           "https://www.fcai.com.au/sales", "free_summary_paid_detail", "See retrieval note.",
           countries=("AU",)),
    Source("reg_ca", "New motor vehicle registrations (table 20-10-0024-01)", "Statistics Canada", 1,
           "registrations", ("ev_convenience",), "Registrations by fuel type, quarterly", "CA", "file",
           "CSV/SDMX download of the table", "https://www150.statcan.gc.ca/", "free", "",
           tool="import_table", countries=("CA",)),
    Source("reg_dk", "StatBank BIL53 and related", "Statistics Denmark", 1, "registrations",
           ("ev_convenience",), "New registrations by fuel", "DK", "api",
           "StatBank API (api.statbank.dk) or table export", "https://www.statbank.dk/", "free", "",
           tool="import_table", countries=("DK",)),
    Source("reg_es", "Vehicle registration microdata", "DGT", 1, "registrations", ("ev_convenience",),
           "Every registration, monthly ZIP + data dictionary", "ES", "file", "Monthly ZIP files",
           "https://www.dgt.es/menusecundario/dgt-en-cifras/", "free", "Large files; aggregate first.",
           countries=("ES",)),
    Source("reg_fi", "Vehicle registration statistics", "Traficom", 1, "registrations",
           ("ev_convenience",), "First registrations by power source", "FI", "api", "PxWeb tables / API",
           "https://www.traficom.fi/en/statistics-and-publications", "free", "", countries=("FI",)),
    Source("reg_fr", "Vehicle registration open data", "SDES (Ministry of Ecological Transition)", 1,
           "registrations", ("ev_convenience",), "Registrations by energy", "FR", "file", "CSV open data",
           "https://www.statistiques.developpement-durable.gouv.fr/", "free", "", countries=("FR",)),
    Source("reg_gb", "Vehicle licensing statistics (VEH tables)", "UK Department for Transport", 1,
           "registrations", ("ev_convenience",), "New registrations by fuel; SMMT monthly as faster "
           "industry figure", "GB", "file", "ODS/CSV downloads",
           "https://www.gov.uk/government/collections/vehicles-statistics", "free",
           "SMMT (smmt.co.uk) is tier 1 for speed but is an industry body.", countries=("GB",)),
    Source("reg_jp", "Registration statistics", "JADA / JAIA (imports)", 1, "registrations",
           ("ev_convenience",), "Registrations by brand/fuel; JAIA covers imported brands like BMW", "JP",
           "report", "Monthly reports; detailed Excel is paid", "https://www.jada.or.jp/",
           "free_summary_paid_detail", "", countries=("JP",)),
    Source("reg_kr", "Imported car registrations", "KAIDA / MOLIT", 1, "registrations",
           ("ev_convenience",), "Imported-brand registrations by model and fuel (KAIDA), all vehicles (MOLIT)",
           "KR", "report", "Monthly XLSX/press releases", "https://www.kaida.co.kr/", "free", "",
           countries=("KR",)),
    Source("reg_no", "Vehicle statistics", "OFV", 1, "registrations", ("ev_convenience",),
           "New registrations by fuel/brand", "NO", "web", "Public dashboard; history by subscription",
           "https://ofv.no/", "free_summary_paid_detail", "Norway is the BEV outlier (~95 %+); check "
           "leverage in correlations.", countries=("NO",)),
    Source("reg_se", "Registration statistics", "Mobility Sweden", 1, "registrations",
           ("ev_convenience",), "New registrations by fuel/brand", "SE", "file", "Monthly XLSX",
           "https://mobilitysweden.se/statistik", "free", "", countries=("SE",)),
    Source("reg_us", "Light-duty EV sales", "Argonne National Laboratory (US DOE)", 1, "registrations",
           ("ev_convenience",), "Monthly US plug-in sales by model", "US", "file", "XLSX download",
           "https://www.anl.gov/esia/light-duty-electric-drive-vehicles-monthly-sales-updates", "free",
           "No free official total-market sales series in the US; ATP comes from Cox/KBB (tier 2).",
           countries=("US",)),
    Source("reg_za", "Monthly new-vehicle sales", "naamsa", 1, "registrations", ("context",),
           "Sales by brand/segment", "ZA", "report", "Monthly PDF/XLSX", "https://naamsa.net/", "free",
           "BMW reports aggregate only for some months.", countries=("ZA",)),
    Source("acea", "Vehicle registrations by power source", "ACEA", 1, "industry_association",
           ("ev_convenience",), "EU+EFTA+UK monthly registrations by powertrain", "DK ES FI FR GB NO SE",
           "report", "Monthly press-release PDF tables", "https://www.acea.auto/figures/", "free",
           "Industry association, but numbers are compiled from national registries."),
    # ---- Tier 2: consumer and quality surveys --------------------------------------------------
    Source(
        "deloitte_gacs", "Global Automotive Consumer Study", "Deloitte", 2, "consumer_survey",
        ("affordability", "ev_convenience", "safety_tech"),
        "Purchase priorities, price sensitivity, EV concerns (range, charging time, cost), brand trust, "
        "willingness to pay for connectivity/ADAS",
        "~25 countries incl. most of the 13 (check each year's country list), annual, ~1,000 per country",
        "report", "Interactive dashboard + PDF. Enter each value with question ID/wording, base "
        "(all respondents vs EV intenders), sample size and fieldwork month",
        "https://www.deloitte.com/global/en/Industries/automotive/research/global-automotive-consumer-study.html",
        "free", "Online panel; stated preferences ('concerned about range' != 'will not buy an EV'). "
        "Published year != fieldwork year (fieldwork is usually autumn of the year before).",
        tool="add_observation",
    ),
    Source(
        "jdpower", "IQS, APEAL, VDS, EVX, Tech Experience Index", "J.D. Power", 2, "quality_survey",
        ("safety_tech", "ev_convenience"),
        "Problems per 100 vehicles (PP100), appeal scores, feature usage and satisfaction",
        "US (most studies), also UK, JP, AU, CN variants", "report",
        "Press releases (free headline + brand rankings); detailed data commercial",
        "https://www.jdpower.com/business/automotive", "free_summary_paid_detail",
        "BMW Source C/D in Dataset/ are IQS/APEAL-style; compare like with like (same study, same year).",
        tool="add_observation",
    ),
    Source("ey_mci", "Mobility Consumer Index", "EY", 2, "consumer_survey",
           ("ev_convenience", "affordability"), "EV purchase intent, barriers", "~25 countries", "report",
           "PDF; manual entry with base and question", "https://www.ey.com/en_gl/industries/automotive",
           "free", "Smaller published detail than Deloitte.", tool="add_observation"),
    Source("mckinsey_mcp", "Mobility Consumer Pulse", "McKinsey Center for Future Mobility", 2,
           "consumer_survey", ("ev_convenience", "safety_tech"), "EV intent, ADAS/autonomy interest",
           "~15 countries", "report", "Articles/PDF; manual entry", "https://www.mckinsey.com/features/mckinsey-center-for-future-mobility",
           "free", "Often only charts without exact values -> do not read values off charts.",
           tool="add_observation"),
    Source("cox_kbb", "Average transaction price / EV ATP", "Cox Automotive / Kelley Blue Book", 2,
           "industry_association", ("affordability",), "Monthly new-vehicle ATP by segment and brand", "US",
           "report", "Monthly press release", "https://www.coxautoinc.com/market-insights/", "free",
           "US only; brand-level ATP includes incentives differently over time.", countries=("US",),
           tool="add_observation"),
]

TIER_RULES = {
    1: "Official statistics, regulators, independent test bodies: may be used as a model variable.",
    2: "Commercial research with published method/sample/fieldwork: model variable only with question "
       "wording, base, sample size and fieldwork period stored.",
    3: "Press, forums, blogs, marketing: context and hypotheses only, never a model variable.",
}

BY_ID = {s.id: s for s in SOURCES}


def find(need: str | None = None, country: str | None = None, max_tier: int = 3) -> list[Source]:
    out = []
    for s in SOURCES:
        if s.tier > max_tier:
            continue
        if need and need not in s.needs:
            continue
        if country and s.countries and country not in s.countries:
            continue
        out.append(s)
    return sorted(out, key=lambda s: (s.tier, s.access != "api", s.id))
