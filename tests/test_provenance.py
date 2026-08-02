"""A policy claim with no recorded evidence can't be audited.

These tests pin the property that matters: when a scraper decides a dog
policy, it also records what that decision was based on. The claim and its
justification are written together or not at all.
"""

from casita import zumper
from casita.models import Listing


def _listing() -> Listing:
    return Listing(source="zumper", source_id="test", url="https://example.com/x")


def test_large_dogs_records_policy_and_evidence():
    L = _listing()
    zumper._parse_detail_html("<div>Dog Policy: Large dogs allowed</div>", L)
    assert L.dog_policy == "large_ok"
    assert L.dog_policy_evidence
    assert "zumper" in L.dog_policy_evidence.lower()


def test_not_allowed_records_evidence():
    L = _listing()
    zumper._parse_detail_html("<div>Dog Policy: Not allowed</div>", L)
    assert L.dog_policy == "no_dogs"
    assert L.dog_policy_evidence


def test_small_dogs_records_evidence():
    L = _listing()
    zumper._parse_detail_html("<div>Dog Policy: Small dogs</div>", L)
    assert L.dog_policy == "small_only"
    assert L.dog_policy_evidence


def test_silent_listing_asserts_nothing():
    """No dog language at all must leave the policy unset. A missing field
    is the honest answer; anything else is a guess presented as a fact."""
    L = _listing()
    zumper._parse_detail_html("<div>Hardwood floors. Near the park.</div>", L)
    assert L.dog_policy is None
    assert L.dog_policy_evidence is None


def test_evidence_quotes_the_matched_text():
    """The evidence has to name what was matched, not just that something
    was. 'Something matched' is not auditable."""
    L = _listing()
    zumper._parse_detail_html("<div>Dog Policy: Large dogs allowed</div>", L)
    assert "large dogs" in L.dog_policy_evidence.lower()