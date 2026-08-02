"""Offline consistency checks over the listings DB.

Casita enriches listings from several independent paths: scraper parsing,
LLM fact extraction, LLM photo review, and LLM blurb generation. Nothing
reconciles them, so two components can hold contradictory beliefs about
the same listing and neither notices.

These checks look for that. They are deterministic, read-only, and need
no credentials or network — they run against the committed demo fixture.

They report; they never edit. Deciding what a finding means stays with a
human, the same way `analyze-prefs` proposes without touching code.
"""

import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass

# Severity semantics:
#   error — the system provably disagrees with itself. Should not happen.
#   info  — a count worth watching. May be the honest state of the data.
ERROR = "error"
INFO = "info"


@dataclass(frozen=True)
class Finding:
    check: str
    severity: str
    listing_key: str
    detail: str


def check_policy_contradiction(conn: sqlite3.Connection) -> list[Finding]:
    """Structured dog_policy asserts a policy the generated blurb denies.

    The blurb is written by a model that read the listing. If it says the
    policy is missing while the column says `dogs_ok`, one of them is
    wrong and nothing in the pipeline notices.
    """
    rows = conn.execute(
        """
        SELECT key, source, dog_policy, share_blurb
        FROM listings
        WHERE active = 1
          AND dog_policy IN ('dogs_ok', 'large_ok')
          AND share_blurb IS NOT NULL
          AND (
            share_blurb LIKE '%dog policy is completely missing%'
            OR share_blurb LIKE '%verify the exact dog policy%'
            OR share_blurb LIKE '%dog policy%need%verif%'
            OR share_blurb LIKE '%unverified dog policy%'
          )
        """
    ).fetchall()
    return [
        Finding(
            "policy_contradiction",
            ERROR,
            r["key"],
            f"column says {r['dog_policy']}, blurb says the policy is unconfirmed",
        )
        for r in rows
    ]


def check_unverified_dealbreaker(conn: sqlite3.Connection) -> list[Finding]:
    """Active listings with no dog policy recorded at all.

    Not a bug — it is the honest state of the data. Tracked because two
    90-100 lb dogs are the hard constraint of this search, so the size of
    this bucket is the size of the unanswered question.
    """
    rows = conn.execute(
        """
        SELECT key, source
        FROM listings
        WHERE active = 1
          AND (dog_policy IS NULL OR dog_policy = 'unverified')
        """
    ).fetchall()
    return [
        Finding("unverified_dealbreaker", INFO, r["key"], f"no dog policy from {r['source']}")
        for r in rows
    ]


def check_confident_despite_missing(conn: sqlite3.Connection) -> list[Finding]:
    """Rated `ok` while core facts are absent.

    Missing data should lower confidence. Today a listing with no price
    and no bed count can still carry the same severity as a fully
    specified one.
    """
    rows = conn.execute(
        """
        SELECT key, price, beds, sqft
        FROM listings
        WHERE active = 1
          AND llm_severity = 'ok'
          AND (price IS NULL OR beds IS NULL)
        """
    ).fetchall()
    out = []
    for r in rows:
        missing = [f for f in ("price", "beds", "sqft") if r[f] is None]
        out.append(
            Finding(
                "confident_despite_missing",
                INFO,
                r["key"],
                "severity ok but missing " + ", ".join(missing),
            )
        )
    return out


# Marin towns are grouped under a single search label on purpose; SF
# neighborhoods are not. Only flag a mismatch when the address city is
# outside the cluster the label belongs to.
_MARIN = {"mill valley", "sausalito", "kentfield", "greenbrae", "belvedere", "tiburon", "corte madera"}


def _city_from_address(address: str | None) -> str | None:
    if not address:
        return None
    parts = [p.strip() for p in address.split(",")]
    # "123 Main St, Sausalito, CA 94965" -> "Sausalito"
    if len(parts) >= 2:
        return parts[-2].lower() if re.match(r"^[A-Z]{2}\b", parts[-1].strip()) else parts[-1].lower()
    return None


def check_neighborhood_mismatch(conn: sqlite3.Connection) -> list[Finding]:
    """Neighborhood label disagrees with the city in the address.

    Expect false positives: Marin towns share one label deliberately.
    Reported as info so a human decides which are real.
    """
    rows = conn.execute(
        "SELECT key, neighborhood, address FROM listings WHERE active = 1 AND address IS NOT NULL"
    ).fetchall()
    out = []
    for r in rows:
        hood = (r["neighborhood"] or "").strip().lower().replace("-", " ")
        city = (_city_from_address(r["address"]) or "").replace("-", " ")
        if not hood or not city:
            continue
        hood_is_marin = hood in _MARIN
        city_is_marin = city in _MARIN
        if hood_is_marin != city_is_marin:
            out.append(
                Finding(
                    "neighborhood_mismatch",
                    INFO,
                    r["key"],
                    f"labelled '{hood}' but address city is '{city}'",
                )
            )
    return out


def _street_number(address: str | None) -> str | None:
    """Leading house number, e.g. '136A 17th Ave' -> '136'."""
    if not address:
        return None
    m = re.match(r"\s*(\d+)", address.strip())
    return m.group(1) if m else None


def check_surviving_duplicates(conn: sqlite3.Connection) -> list[Finding]:
    """Two active listings from different sources that look like one property.

    Price alone is a coincidence detector — several unrelated SF buildings
    list at the same round number. Requiring the street number to match as
    well is much closer to identity, at the cost of missing duplicates whose
    address is undisclosed on one side.
    """
    rows = conn.execute(
        """
        SELECT key, source, price, beds, baths, address
        FROM listings
        WHERE active = 1 AND price IS NOT NULL AND beds IS NOT NULL
        """
    ).fetchall()
    buckets: dict[tuple, list[sqlite3.Row]] = defaultdict(list)
    for r in rows:
        num = _street_number(r["address"])
        if not num:
            continue
        buckets[(r["price"], r["beds"], r["baths"], num)].append(r)
    out = []
    for group in buckets.values():
        if len({r["source"] for r in group}) < 2:
            continue
        keys = ", ".join(r["key"] for r in group)
        for r in group:
            out.append(
                Finding(
                    "surviving_duplicates",
                    INFO,
                    r["key"],
                    f"same price/beds/baths and street number across sources: {keys}",
                )
            )
    return out

def check_unevidenced_claim(conn: sqlite3.Connection) -> list[Finding]:
    """A dog policy is asserted but nothing records what it was based on.

    Provenance is written at scrape time, so rows enriched before that
    existed carry no evidence — including every row in the committed
    fixture. This check is not saying those claims are wrong. It is saying
    they cannot be audited: when the column and the generated blurb
    disagree, there is nothing to adjudicate between them.
    """
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(listings)")}
    if "dog_policy_evidence" not in cols:
        # The DB predates provenance entirely. Report that as one finding
        # rather than pretending every row was individually checked.
        n = conn.execute(
            "SELECT COUNT(*) FROM listings WHERE active = 1 AND dog_policy IS NOT NULL"
        ).fetchone()[0]
        return [
            Finding(
                "unevidenced_claim",
                INFO,
                "(schema)",
                f"no dog_policy_evidence column: all {n} policy claims in this "
                f"database predate provenance and cannot be audited",
            )
        ]

    rows = conn.execute(
        """
        SELECT key, source, dog_policy
        FROM listings
        WHERE active = 1
          AND dog_policy IS NOT NULL
          AND dog_policy != 'unverified'
          AND (dog_policy_evidence IS NULL OR dog_policy_evidence = '')
        """
    ).fetchall()
    return [
        Finding(
            "unevidenced_claim",
            INFO,
            r["key"],
            f"claims {r['dog_policy']} with no recorded evidence",
        )
        for r in rows
    ]

CHECKS = [
    check_policy_contradiction,
    check_unevidenced_claim,
    check_unverified_dealbreaker,
    check_confident_despite_missing,
    check_neighborhood_mismatch,
    check_surviving_duplicates,
]

def run_all(conn: sqlite3.Connection) -> list[Finding]:
    findings: list[Finding] = []
    for check in CHECKS:
        findings.extend(check(conn))
    return findings