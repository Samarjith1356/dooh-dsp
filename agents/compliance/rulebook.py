from __future__ import annotations

from dataclasses import dataclass

Verdict = str  # APPROVED | REJECTED | REQUIRES HUMAN REVIEW


@dataclass(frozen=True)
class Rule:
    id: str
    citation: str
    markets: tuple[str, ...]
    severity: str  # reject | review
    needles: tuple[str, ...]
    venues: tuple[str, ...] = ()
    rewrite: str = ""


# Citations are operational mappings to CAP/ASA and ASAI themes, not legal advice.
RULES: tuple[Rule, ...] = (
    Rule(
        id="cap-3-misleading-hyperbole",
        citation="ASA CAP Code §3 (Misleading advertising) — absolute / unsubstantiated superiority",
        markets=("GB", "IE"),
        severity="reject",
        needles=("guarantee", "guaranteed", "miracle", "cure", "best in the world", "number one", "#1 in the world"),
        rewrite="Replace absolute claims with specific, evidenced statements (e.g. 'our 2025 customer survey').",
    ),
    Rule(
        id="cap-12-health",
        citation="ASA CAP Code §12 (Medicines, medical devices, health claims) / ASAI health advertising",
        markets=("GB", "IE"),
        severity="reject",
        needles=("cures", "treats cancer", "clinically proven to cure", "covid cure", "lose 10kg in a week"),
        rewrite="Remove medicinal claims. Direct audiences to licensed medical advice; do not imply treatment.",
    ),
    Rule(
        id="cap-12-implied-health",
        citation="ASA CAP Code §12 — implied health / wellness that needs substantiation",
        markets=("GB", "IE"),
        severity="review",
        needles=("detox", "immune boosting", "clinically proven", "doctor recommended", "burns fat"),
        rewrite="Qualify with evidence on file or drop the health implication for brand-awareness OOH.",
    ),
    Rule(
        id="cap-18-alcohol",
        citation="ASA CAP Code §18 (Alcohol) / ASAI alcohol — not directed at under-18s; no school-adjacent OOH",
        markets=("GB", "IE"),
        severity="review",
        needles=("beer", "lager", "vodka", "gin", "whiskey", "whisky", "prosecco", "alcopop", "abv"),
        venues=("transit.rail", "transit.rail.underground", "urban.street", "transit.bus"),
        rewrite="Confirm 18+ targeting, no school-proximate screens, no morning-school dayparts, no youthful creative.",
    ),
    Rule(
        id="hfss-cap-children",
        citation="CAP HFSS / HFSS product ad restrictions — less adult-targeted media, school-adjacent OOH",
        markets=("GB", "IE"),
        severity="review",
        needles=("hfss", "junk food", "energy drink", "confectionery", "crisps", "fizzy drink", "chicken nugget"),
        venues=("transit.rail.underground", "urban.street", "transit.bus"),
        rewrite="Exclude school-adjacent inventory and child-skewed dayparts; use adult-skew roadside if eligible.",
    ),
    Rule(
        id="cap-16-gambling",
        citation="ASA CAP Code §16 (Gambling) / IE gambling advertising restrictions",
        markets=("GB", "IE"),
        severity="review",
        needles=("bet now", "odds", "casino", "slot", "jackpot", "gambling", "in-play"),
        rewrite="Adult-only placement, no appeal to under-18s, include required safer-gambling line if the product is licensed.",
    ),
    Rule(
        id="cap-14-finance",
        citation="ASA CAP Code §14 (Financial products) — no guaranteed returns / get-rich claims",
        markets=("GB", "IE"),
        severity="reject",
        needles=("guaranteed returns", "get rich", "risk-free investment", "double your money", "crypto guaranteed"),
        rewrite="If the product is authorised, use factual risk warnings. Do not imply guaranteed performance.",
    ),
    Rule(
        id="cap-7-political",
        citation="ASA CAP / UK political advertising & publisher OOH political policies; IE electoral rules",
        markets=("GB", "IE"),
        severity="reject",
        needles=("vote for", "vote labour", "vote conservative", "vote sinn fein", "election campaign", "political party"),
        rewrite="Political/issue ads need publisher clearance and are not auto-compiled. Route to human legal review.",
    ),
    Rule(
        id="pricing-misleading",
        citation="ASA CAP Code §3.17–3.22 (Prices) — drip / was-now / free claims",
        markets=("GB", "IE"),
        severity="review",
        needles=("was £", "now only", "free gift", "0% apr", "no catch", "from £0"),
        rewrite="Show the real payable price and qualifying criteria on the creative, not only in a landing page.",
    ),
)


SCHOOL_HOURS = frozenset(range(8, 16))
WEEKDAYS = frozenset(range(0, 5))
