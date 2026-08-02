"""The eval harness needs its own tests — a checker nobody checks is
just an opinion with a line number."""

import sqlite3

import pytest

from casita import evals



@pytest.fixture
def conn():
    from casita import DEMO_FIXTURE

    c = sqlite3.connect(DEMO_FIXTURE)
    c.row_factory = sqlite3.Row
    yield c
    c.close()


def test_all_checks_run_without_error(conn):
    findings = evals.run_all(conn)
    assert isinstance(findings, list)
    # The fixture is known to contain inconsistencies; a completely empty
    # result means the checks stopped matching, not that the data got clean.
    assert findings


def test_findings_are_well_formed(conn):
    for f in evals.run_all(conn):
        assert f.check
        assert f.severity in (evals.ERROR, evals.INFO)
        assert f.listing_key
        assert f.detail


def test_policy_contradiction_finds_known_case(conn):
    """zillow:15100328 is the demo's top pick: dog_policy='dogs_ok' while
    its own generated blurb says the policy is missing."""
    keys = {f.listing_key for f in evals.check_policy_contradiction(conn)}
    assert "zillow:15100328" in keys


def test_contradictions_are_error_severity(conn):
    for f in evals.check_policy_contradiction(conn):
        assert f.severity == evals.ERROR


def test_duplicate_check_requires_matching_street_number(conn):
    """Price alone matched six unrelated buildings; the street number guard
    is what makes this check usable."""
    findings = evals.check_surviving_duplicates(conn)
    # Both members of each pair are reported, so the count is even and small.
    assert len(findings) % 2 == 0
    assert len(findings) < 10


def test_checks_do_not_modify_the_database(conn):
    before = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    evals.run_all(conn)
    after = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    assert before == after