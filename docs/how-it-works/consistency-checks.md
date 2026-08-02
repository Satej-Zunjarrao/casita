---
icon: lucide/scan-search
---

# Consistency Checks

Casita enriches listings along several independent paths: scraper parsing,
Gemini fact extraction, photo review, and blurb generation. Nothing reconciles
them, so two components can hold contradictory beliefs about the same listing
and neither notices.

`src/casita/evals.py` looks for that. The checks are deterministic and
read-only, and need no credentials, network, or LLM calls — they run against
the committed fixture in under a second.

    uv run casita eval
    uv run casita eval --strict
    uv run casita eval --fixture path/to/other.sqlite

## The Checks

| Check | Looks for |
| ----- | --------- |
| `policy_contradiction` | `dog_policy` asserts a policy the generated blurb says is missing |
| `unevidenced_claim` | A policy is asserted with nothing recorded about what it rests on |
| `unverified_dealbreaker` | Active listings with no dog policy recorded at all |
| `confident_despite_missing` | Severity `ok` while price or bed count is absent |
| `neighborhood_mismatch` | Neighborhood label disagrees with the city in the address |
| `surviving_duplicates` | Two active listings from different sources that look like one property |

## Severity

`error` means the system provably disagrees with itself. `info` is a count
worth watching, and is often the honest state of the data rather than a defect:
52 listings with no dog policy is not a bug, it is 52 landlords nobody has
called.

`--strict` exits non-zero on `error` findings only, so the harness is usable in
CI without failing a build over unanswered questions.

## What It Does Not Do

The checks report and never edit, following the precedent `analyze-prefs` sets:
a revealed problem becomes a change through an intentional human decision.

They also prove consistency, not correctness. A contradiction shows that two
components disagree. It does not say which one is right — and where the
evidence that would settle it was discarded at scrape time, nothing can.

No check carries an acceptable-count threshold. Whether five contradictions is
tolerable depends on context the tool does not have.

## Ways This Could Go Further

The checks are read-time only: they find contradictions after both claims are
already stored. Reconciling at write time — ranking evidence by strength so a
better-sourced conclusion can overwrite a worse one — would prevent the class
rather than report it. Coverage could also extend past dog policy to parking,
laundry, and yard, which have the same shape and no provenance today.