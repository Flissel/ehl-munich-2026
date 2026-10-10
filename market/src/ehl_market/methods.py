"""How companies turn customer needs into comparable weights ("is safety worth more than price?").

Short answer encoded here: there is no universal weight. Industry practice measures importance
per market and segment with trade-off methods, and treats legally required safety as a constraint,
not as something customers trade against price.

`examples` are cases from the team's research notes. Entries with `verify: True` were not checked
against the primary source in this repo - check before quoting them on stage.
"""

METHODS: dict[str, dict] = {
    "stated_importance": {
        "name": "Stated importance (rating scales)",
        "question": "How important is X to you? (1-5 / 1-10)",
        "output": "Mean importance or top-2-box % per attribute",
        "use_for": "Quick screening; what most public surveys (Deloitte, EY) publish",
        "weakness": "Everything looks important; scale use differs by culture (e.g. JP/KR rate lower, "
                    "US higher), so country comparisons are biased. No trade-off with price.",
        "data_needed": "Survey percentages - available publicly",
    },
    "derived_importance": {
        "name": "Derived importance / key-driver analysis",
        "question": "Rate overall satisfaction and each attribute; regress overall on attributes",
        "output": "Standardised coefficient or relative-weight share per attribute",
        "use_for": "Which attributes actually move satisfaction/loyalty (J.D. Power APEAL-style studies)",
        "weakness": "Correlational; collinear attributes split weight arbitrarily (use relative weights "
                    "/ Shapley decomposition).",
        "data_needed": "Respondent-level ratings - BMW's own studies (US_2025, CN_EU_2025 in Dataset/)",
    },
    "maxdiff": {
        "name": "MaxDiff / Best-Worst Scaling",
        "question": "Of these 4-5 attributes, which is MOST and which is LEAST important?",
        "output": "Ratio-scaled importance scores summing to 100 per respondent",
        "use_for": "Ranking 10-30 needs (safety, price, range, design, tech...) across countries; "
                   "forces trade-offs and reduces scale-use bias between cultures",
        "weakness": "Relative only - says safety > price, not how many euros safety is worth.",
        "data_needed": "Own survey (n ~ 200-300 per country/segment)",
    },
    "cbc_conjoint": {
        "name": "Choice-based conjoint (CBC)",
        "question": "Which of these 2-3 full vehicle offers would you buy (or none)? Repeated 10-15x "
                    "with systematically varied price, safety package, range, brand...",
        "output": "Part-worth utilities; willingness to pay WTP = -beta_attribute / beta_price; "
                  "preference-share simulator incl. competitors and 'none'",
        "use_for": "The direct answer to 'safety or money': euros per upgrade and predicted take rate",
        "weakness": "Hypothetical choices overstate WTP; simulate shares rather than quoting raw WTP; "
                    "calibrate to real market shares.",
        "data_needed": "Own choice experiment; tool `willingness_to_pay` converts estimated coefficients",
    },
    "kano": {
        "name": "Kano model",
        "question": "How do you feel if the car HAS X? ... if it does NOT have X?",
        "output": "Class per feature: must-be, performance (one-dimensional), attractive, indifferent",
        "use_for": "Deciding whether a feature is hygiene (must ship standard) or differentiating",
        "weakness": "Categories drift over time (yesterday's delighter becomes tomorrow's must-be).",
        "data_needed": "Own survey; Source D 'love / improve' text in Dataset/ is a rough proxy",
    },
    "qfd": {
        "name": "Quality Function Deployment (House of Quality)",
        "question": "Matrix: weighted customer needs x engineering characteristics x competitor benchmark",
        "output": "Technical priority = sum(need weight x relationship strength 9/3/1)",
        "use_for": "Translating the weights from MaxDiff/CBC into engineering targets",
        "weakness": "Garbage in, garbage out: needs measured weights, not team guesses.",
        "data_needed": "Need weights + engineering judgement",
    },
    "observed_behaviour": {
        "name": "Revealed preference / observed behaviour",
        "question": "What do customers actually buy and use? (take rates, option mix, feature usage)",
        "output": "Option take rate, usage frequency, conversion by price point",
        "use_for": "Validating stated preferences; spotting 'say but do not buy' features",
        "weakness": "Only shows choices among what was offered at the price offered.",
        "data_needed": "BMW internal: option take rates, connected-car usage (not in Dataset/)",
    },
}

EXAMPLES: list[dict] = [
    {"company": "Toyota (and suppliers), Ford, GM", "method": "qfd",
     "what": "House of Quality: customer attributes weighted, mapped to engineering characteristics, "
             "benchmarked against competitors.",
     "source": "Hauser & Clausing, 'The House of Quality', Harvard Business Review, May-June 1988",
     "url": "https://hbr.org/1988/05/the-house-of-quality", "verify": False},
    {"company": "Ford", "method": "kano",
     "what": "Kano questionnaire to separate expected vs attractive SUV attributes (reported ASQ case, 2001).",
     "source": "ASQ case study (team notes)", "url": None, "verify": True},
    {"company": "Porsche", "method": "derived_importance",
     "what": "Uses J.D. Power quality/appeal feedback in concept and development; observed button "
             "usage led to a dedicated track-skip button.",
     "source": "Porsche Newsroom (team notes)", "url": None, "verify": True},
    {"company": "BMW", "method": "observed_behaviour",
     "what": "Interface customer studies combined with anonymised fleet usage data from consenting users; "
             "regular new-car buyer and early-ownership surveys.",
     "source": "BMW Group press / Group Report 2024 (team notes)", "url": None, "verify": True},
    {"company": "Commercial-vehicle OEM (IfaD case)", "method": "cbc_conjoint",
     "what": "CBC with fleet buyers over power, cab, equipment, service, price; simulator calibrated to "
             "market shares and combined with cost to find profitable configurations.",
     "source": "IfaD conjoint case study (team notes)", "url": None, "verify": True},
    {"company": "NielsenIQ BASES (FMCG)", "method": "cbc_conjoint",
     "what": "Choice-based concept and price testing with volume forecasting before launch.",
     "source": "NIQ (team notes)", "url": None, "verify": True},
]

SAFETY_VS_PRICE = {
    "principle": "Do not assign safety a fixed weight (e.g. 70 %) against price. Split the question.",
    "steps": [
        "1. Constraint, not trade-off: functions required by law (e.g. EU General Safety Regulation "
        "phases) or needed for the target NCAP rating are fixed. They are out of scope for customer "
        "trade-offs (matches the requirements agent: OUT_SAFETY theme = park).",
        "2. Above the baseline: measure relative importance per country with MaxDiff "
        "(safety vs price vs range vs tech vs design...).",
        "3. Price it: CBC gives WTP and take rate for a specific safety/ADAS package at specific prices.",
        "4. Check against behaviour: actual option take rate and usage; BMW comment signals "
        "(ADAS theme: false alarms, cannot switch off = experience in scope).",
        "5. Decide with: WTP x predicted take rate x margin, minus cost, plus validated safety benefit "
        "(crash/injury reduction) - per market and segment.",
    ],
    "what_public_data_can_do": "Rank markets by stated safety/price importance (Deloitte etc.) as a "
        "country-level context variable and point to where an own MaxDiff/CBC is worth running. It "
        "cannot produce individual utilities or WTP.",
}


def wtp(beta_attribute: float, beta_price: float, price_unit: float = 1.0) -> dict:
    """Marginal willingness to pay from conjoint coefficients: -beta_attr / beta_price."""
    if beta_price >= 0:
        raise ValueError("beta_price must be negative (higher price = lower utility)")
    value = -beta_attribute / beta_price * price_unit
    return {
        "wtp": round(value, 2),
        "formula": "WTP = -beta_attribute / beta_price",
        "caveat": "Only valid for coefficients estimated from real choice data. Hypothetical WTP is "
                  "usually overstated; prefer share simulations with competitors and a 'none' option.",
    }
