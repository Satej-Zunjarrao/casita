# Contribution — Satej Zunjarrao

Casita treats "we don't know" as "it's fine."

The demo's top pick is a Zillow listing badged **Dogs OK**. Its own generated
summary says the dog policy is completely missing from the listing and will
need landlord verification. Both statements are on the same card. Nothing in
the pipeline notices they disagree.

That is not a one-off. Of 143 active listings, 52 have no dog policy recorded
at all and render no badge, so a reader cannot tell "checked, it's fine" from
"nobody looked." A further 91 assert a policy with nothing recorded about what
that claim rests on. Dog policy is the hard constraint of this search — two
dogs at 90 and 100 lb, and the fixture contains a landlord rejecting them over
a 40 lb limit — so an unverified policy is not a neutral fact. It is the whole
question, unanswered.

The same shape appears elsewhere. Dedup's guards only fire when both listings
have a price and a bed count, so missing data quietly disables the check that
prevents wrong merges. Absence of evidence is read as evidence of absence,
across the pipeline.

This contribution makes the distinction visible:

- **`unverified` as a first-class dog policy** — 52 listings gain a badge and a
  small ranking penalty. Craigslist no longer records its own search filter as
  a fact about the apartment.
- **Provenance** — scrapers now record what a policy claim was based on. The
  detail page shows the evidence, or says plainly that there isn't any.
- **`casita eval`** — six offline consistency checks that find these
  contradictions mechanically, in under a second, with no credentials.
- **Windows support** — the project did not start on Windows. It does now.

---
## How I Chose

I read the docs first and wrote down ten things that could be improved: an
eval harness for ranking quality, a pluggable LLM provider, versioning the
ranking policy, explaining a listing's rank on the card, aging old votes,
lifting search criteria into one object, contract tests for the scrapers,
surfacing filtered listings, detecting changes between runs, and cost and
latency accounting.

Four survived a first pass on impact against effort: provider layer, eval
harness, weighted criteria, explain-the-rank. Then I ran the code, and the
plan changed.

Three of the ten were answers to problems the codebase does not have.
Surfacing filtered listings is moot — the page already says `143 of 143
shown`, nothing is hidden. Change detection and cost accounting both need
history or live traffic that a single committed snapshot cannot provide.
Those were ideas from reading documentation, not from using the tool.

The eval harness was worse than moot: it was designed wrong. The plan was to
score rankings against the owner's votes with NDCG and pairwise agreement.
The fixture has 16 votes across 349 listings. At 4.5% coverage those metrics
are noise with a decimal point on them. The harness had to become something
that needs no labels, which is what it is now.

I ordered the remaining work so that the parts that could not be verified
without it came first:

1. **Platform fixes.** The demo did not run on my machine. Nothing downstream
   is verifiable until it does.
2. **The data-model fix.** Unknown needed somewhere to live before anything
   could render or rank it.
3. **Provenance.** Made the contradictions diagnosable rather than only
   visible.
4. **The eval harness.** Proves the above and catches the class of defect
   coming back.

The order matters more than the total. Cut the work anywhere after step two
and there is still a coherent change: unknown is visible, ranking accounts
for it, the demo runs. Cut it after step one and there is a platform fix
worth having on its own. Nothing depends on a later step to make sense.

### Decisions

| # | Candidate | Decision | Reason |
|---|-----------|----------|--------|
| 1 | Eval harness | **Built, redesigned** | 16 votes cannot support ranking metrics. Rebuilt as consistency checks, which need no labels. |
| 2 | Pluggable LLM provider | **Dropped mid-build** | Justified as scaffolding for the harness. The harness turned out to be pure SQL and needed nothing from it. |
| 3 | Versioned ranking policy | Not selected | Real, but it improves reviewability of a policy whose output nothing measures yet. Wrong order. |
| 4 | Explain the rank | **Built, narrowed** | Full version surfaces every ranking dimension. Narrowed to the dealbreaker: show when dog policy is unverified. |
| 5 | Vote aging | Not selected | Needs enough votes for age to be meaningful. There are 16. |
| 6 | Search criteria object | **Dropped mid-plan** | Weights need feedback data to validate against. A knob nobody can prove works is decoration. |
| 7 | Parser contract tests | Not selected | The right idea. Needs recorded HTML fixtures, and Zillow's bot protection makes capturing them a project of its own. |
| 8 | Surface filtered listings | **Dropped — moot** | The page already shows every listing. I proposed this from the docs, before running the demo. |
| 9 | Run-over-run change detection | Not selected | Useful in production, undemonstrable on a single snapshot. |
| 10 | Cost and latency accounting | Not selected | The demo makes no LLM calls, so it would report nothing here. |
| — | Windows platform fixes | **Built** | Not on the list. The project did not start on Windows. |
| — | Provenance | **Built** | Not on the list. The eval harness could show that two components disagreed but not what either claim rested on. |

Two of the four things I shipped were not on my original list. Both came from
running the code rather than reading about it.

## What Running It Taught Me

**The project does not start on Windows.** `casita demo` fails at import:
`html.py` calls `ZoneInfo("America/Los_Angeles")`, and Windows does not ship
a system timezone database, so the lookup raises before anything runs. Past
that, rendering dies on a `UnicodeEncodeError` — `write_text` without an
explicit encoding defaults to cp1252 on Windows, which cannot encode the
arrow characters in the rendered page.

Both are the same class of bug: a dependency on the developer's platform that
is invisible from inside it. The fixes are a `tzdata` dependency gated on
`sys_platform == 'win32'` and an explicit `encoding="utf-8"` at every text
read and write.

**The test suite was green for the wrong reason.** My first instinct on the
encoding failure was to set `PYTHONUTF8=1`, which fixed my shell and left the
bug in place. The tests passed in that shell. Once I fixed the source properly
and opened a clean one, `test_demo.py` failed — it also called `read_text()`
without an encoding. The original 18 passing tests included a latent Windows
failure that only an environment variable was hiding. There is a difference
between a fix and a workaround, and the workaround had been masking the thing
I was trying to verify.

**The fixture has 16 votes.** Across 349 listings. This is the number that
killed the original eval design, and I would not have found it from the docs —
the learning documentation describes the feedback loop in detail without
saying how much feedback exists. Any metric scored against 4.5% coverage is
measuring its own sampling noise.

**One of my Six checks was a hypothesis the data disproved.** I expected
listings with no price or bed count to still carry an `ok` severity — the page
shows "price on request" cards rated *Worth a look*, which I read as
overconfidence. The data says otherwise:

| severity | listings | missing price |
|----------|----------|---------------|
| ok | 11 | 0 |
| concerns | 97 | 20 |
| filtered | 35 | 1 |

Not one `ok` listing lacks a price. Missing data already lowers severity
correctly; "Worth a look" is the display label for `concerns`, not `ok`. I had
been reading the page and inferring the schema. The check stays in the harness
because an invariant that holds today is still worth pinning, but it found
nothing, and it should not be presented as though it did.

## The Finding

Three parts of the pipeline form an opinion about dog policy, independently,
and nothing reconciles them.

**The scrapers.** `craigslist.py` created every listing with
`dog_policy="dogs_ok"`, with a comment describing it as a baseline from the
search filter that enrichment would refine. It could not: `apply_facts` only
writes when the field is empty, and the field was never empty. The docstring
in `dogs.py` states the reasoning directly — a `pets_dog=1` URL filter is
treated as prior knowledge. But that parameter is a fact about the query, not
about the apartment. Zillow and Zumper are honest by comparison: both write a
policy only when they parse one, and leave the field unset otherwise.

**The fact extractor.** Reads the listing and writes a structured
`dog_policy`. It records a conclusion but not what the conclusion was based
on, so the claim cannot be checked afterwards.

**The blurb generator.** Reads the same listing and writes prose. On 5
listings it says the policy is missing while the structured column says
`dogs_ok`. Both fields render on the same card.

Then the ranking makes the gap consequential. `rank.py` scored `large_ok` at
+12, `dogs_ok` at +6, `small_only` at −30, and `no_dogs` as a hard −1000
rejection. An unknown policy scored zero — it fell through every branch. For a
household whose binding constraint is two dogs at 90 and 100 lb, "nobody has
checked" was treated as equivalent to a listing with no dog signal either way,
and competed on price and walk times as if the question did not exist.

The rendering completed the loop. `html.py` emitted a badge only when
`dog_policy` was set, so 52 listings showed nothing at all in that slot, which
is indistinguishable from a policy that was checked and found unremarkable.

The result on the fixture:

| | count |
|---|---|
| Active listings | 143 |
| No policy recorded, no badge rendered | 52 |
| Policy asserted, nothing recorded about why | 91 |
| Structured field contradicts the generated blurb | 5 |

The top-ranked listing is one of the 5. It is badged **Dogs OK**, its summary
says the policy is completely missing, and before this change there was
nothing on the page or in the database to indicate which to believe.

## What I Built

### `unverified` as a first-class policy

`DogPolicy` gains a fifth value. `None` already meant "nothing has looked
yet"; `unverified` means "we looked and found nothing conclusive." The badge
reads **Verify dog policy** and shares the caution styling with small-dogs-only.

Craigslist no longer seeds `dogs_ok` from the search filter. The listing is
created with the field unset and enrichment fills it from the body, or leaves
it unset if the body says nothing.

*Trade-off on wording.* "Dogs: unknown" is shorter and fits the badge row
better. "Verify dog policy" is longer but names an action, which is what an
unverified dealbreaker actually is for someone hunting apartments. I chose the
longer one because the reader's next step is a phone call, not a shrug.

*Trade-off on the penalty.* Unverified now scores −5. The alternatives were 0
— change the display only, leave ranking untouched — and something around −15,
which would push every unverified listing below every confirmed-friendly one.
−5 breaks ties in favour of certainty without hiding 52 listings that may be
worth a call. The number is a judgment, not a measurement; it is small enough
that being wrong about it is cheap.

### Provenance

A `dog_policy_evidence` column records what a claim rests on. Zumper's parser
captures the matched policy string, Zillow's records the facts-grid value it
classified, and both fall back to naming the path that matched when the exact
snippet is not available. The detail page renders three states: the evidence,
"not stated in the listing" for unverified, and **"asserted, no evidence
recorded"** when a policy exists with nothing behind it.

*Trade-off on storage.* A general `provenance(listing_key, field, value,
evidence)` table would extend to every field rather than one. I used a single
column because the whole argument here is about one field, and a table that
serves fields nobody instrumented is speculative structure. If a second field
needs provenance, the table is the right refactor at that point.

*Limitation.* Provenance is written at scrape time, so the committed fixture
has none — every row predates the feature. That is why the harness reports the
absence as one schema-level finding rather than 91 identical rows: a database
without the column is not a database with 91 audited failures. The feature is
demonstrable on live runs; on the fixture, what is demonstrable is the gap.

### `casita eval`

Six checks over the listings table. Deterministic, read-only, no network, no
credentials, no LLM calls. It runs in under a second against the committed
fixture — deliberately unlike the existing suite, which takes 80 seconds
because it renders the whole site.

    policy_contradiction      5   error
    unevidenced_claim         1   info
    unverified_dealbreaker   52   info
    confident_despite_missing 0   clean
    neighborhood_mismatch     1   info
    surviving_duplicates      4   info

Findings are `error` only when the system provably disagrees with itself.
Everything else is `info` — a count worth watching, often the honest state of
the data rather than a defect. `--strict` exits non-zero on errors only, so it
is usable in CI without failing the build over 52 listings whose landlords
simply have not been called yet.

The harness reports and never edits, following the precedent `analyze-prefs`
sets: revealed problems become changes through an intentional human decision.

*Trade-off on thresholds.* No check has an acceptable-count threshold baked
in. 12 contradictions is not automatically worse than 5; whether either is
tolerable depends on context the tool does not have. Reporting the number and
leaving the judgment to a person keeps the harness honest about what it knows.

### Windows support

Four fixes across `pyproject.toml`, `cache.py`, `__init__.py`, and
`tests/test_demo.py`. The `tzdata` dependency is gated on `sys_platform ==
'win32'` so it does not install where the OS already provides it. Every text
read and write names its encoding explicitly, which is correct on every
platform — relying on the OS default was the bug.

## What I Got Wrong

The duplicate check, in its first version, matched on price, bed count, and
bath count. It reported 17 findings. The numbers looked plausible and the
implementation was correct, so it would have been easy to ship.

I printed the groups instead. Six of the eight were unrelated buildings that
happened to list at the same round number — `1931 Santiago St` and `2017 Judah
St` are not the same property, and the $7,000 bucket contained two San
Francisco listings and one in Sausalito with an undisclosed address. A 75%
false-positive rate on a check nobody had looked at.

The two real pairs shared something the false ones did not: the street number
matched, and the street name matched after normalisation — `136A 17th Ave`
against `136a 17th Avenue & Lake Street`, `1801 Wedemeyer Street #201` against
`1801 Wedemeyer St`. Adding the street number to the match key dropped 17
findings to 4, which is both real pairs and nothing else.

Price alone is a coincidence detector. The correction cost twenty minutes and
was only possible because I looked at the output rather than the count. A
metric nobody has inspected is not a metric.

I also expected the harness to find severity inflation and it found none — that
hypothesis is in the previous section, along with the data that disproved it.
Two of six checks were wrong on first writing. Both were caught by reading what
they produced.

## Limitations

**The harness proves consistency, not correctness.** It can show that the
structured field and the generated blurb disagree. It cannot say which one is
right. For the 5 contradictions, the evidence that would settle them was
discarded at scrape time and is not in the fixture — that is the gap
provenance closes going forward, and cannot close retroactively.

**Provenance does not populate on the demo.** The committed fixture predates
the column. Running `casita eval` against it reports the absence; running a
live `search` and `enrich` would populate it. What the demo demonstrates is
the shape of the problem, not the feature working.

**The body-regex path records less than it should.** When Zillow or Craigslist
falls back to matching the page body, the evidence records which path matched
rather than the matched snippet, because `dogs.classify` returns a policy
without the span that produced it. Changing its return type would touch every
caller. It is a real gap and a small one.

**The duplicate check now misses cases it used to catch.** Requiring a street
number means listings with an undisclosed address are excluded entirely. I
chose precision over recall because a check with 75% false positives does not
get run twice, but the trade is real.

**Two fixture copies exist** — `fixtures/demo.sqlite` and
`src/casita/fixtures/demo.sqlite`, identical today, with nothing verifying
they stay that way. I did not change this. It is worth knowing about.

## What I Would Do Next

In the order I would do it.

### 1. Reconcile the three dog-policy paths at write time

The harness reports contradictions after the fact. Nothing prevents them.
`apply_facts` currently writes only into empty fields, which is why the
Craigslist default was permanent — a later, better-evidenced conclusion could
not overwrite an earlier, worse one.

*Approach.* Rank evidence by strength rather than by arrival order: a parsed
structured field beats a body regex, which beats a model's reading of prose,
which beats nothing. When a stronger source contradicts a weaker one, it
overwrites and records both. When two sources of equal strength disagree, the
field goes to `unverified` and the disagreement is stored.

*What it needs.* The provenance column already carries what each source
matched. It would need a strength rank per source and a decision about whether
disagreement should ever produce a confident answer. My instinct is no.

### 2. Extend provenance to the other dealbreakers

Dog policy is instrumented; parking, laundry, and yard are not. Each has the
same structure — a scraper or a model asserts a value, and nothing records why.
`has_yard` in particular carries an explicit definition in the extraction
schema (a communal courtyard is not a yard) that nothing verifies was applied.

*Approach.* This is the point at which the single-column decision should be
revisited. Four fields with evidence is a `provenance` table.

### 3. Contract tests for the scraper parsers

The parsers are the least covered and most fragile code in the project. A
Zillow layout change does not raise; it silently returns empty fields, which
flow into ranking as missing data and land in `concerns` looking like listings
that simply did not say much.

*Approach.* Save real detail pages as fixtures, assert each parser extracts the
expected fields, and fail with a readable diff when a site drifts.

*What it needs.* Recorded HTML, which is the hard part — Zillow and Redfin
trigger PerimeterX, and the existing `solve` flow is human-in-the-loop by
design. Capturing a small set of pages once, sanitised, would be a project of
its own. It is why I did not attempt it here.

### 4. Run-over-run change detection

The `runs` table records history that nothing reads. Price drops, relistings,
and disappearances are invisible, and for a time-boxed search a price drop is
the highest-value event in the system.

*Approach.* Diff each run's listings against the previous one and surface the
deltas on the index. The second benefit is cost: once an unchanged listing can
be identified, enrichment can skip it entirely rather than paying for photo
review and fact extraction on a row that has not moved.

*What it needs.* More than one run in a fixture, which the demo does not have.
This is undemonstrable offline and worth doing in production.

### 5. Eval coverage for the ranker itself

Everything the harness checks today is internal consistency. Nothing measures
whether the ranking is any good, because the 16 votes cannot support it.

*Approach.* The path to a real ranking eval runs through more labels, and the
cheapest source of strong labels is disagreement — an explicit override of a
rejection is worth more than a passive upvote. A lightweight way to record
"this was ranked wrong, and here is why" would build the label set as a
side-effect of normal use.

*What it needs.* Enough of a search to generate them. This is the eval design
problem properly stated, and it is a data-collection problem before it is a
metrics problem.

## Verifying This

    uv sync
    uv run playwright install chromium
    uv run casita demo          # renders the fixture at 127.0.0.1:8765
    uv run casita eval          # the consistency checks
    uv run python -m pytest     # 29 tests

The demo path stays credentials-free: no GCS, Firebase, Vertex, browser login,
or paid API calls. `make check` passes — on Windows, run its steps directly,
since `make` is not available there:

    uv run python -m compileall src scripts
    uv run python -m pytest
    uv run python scripts/validate_public.py
    uv run zensical build --clean
    uv build
    uv run casita --help

The documentation site covers the new command and the changed behaviour:

- [Consistency Checks](docs/how-it-works/consistency-checks.md) — what each check looks for and what it deliberately does not do
- [Ranking](docs/how-it-works/ranking.md) — how an unverified policy is scored
- [Data Model](docs/data-model.md) — the provenance column
- [Getting Started](docs/getting-started.md) — Windows notes

### Changed

18 tests to 29. Three new files: `src/casita/evals.py`, `tests/test_evals.py`,
`tests/test_provenance.py`. Modified: `pyproject.toml`, `cache.py`,
`craigslist.py`, `dogs.py`, `html.py`, `listing_page.py`, `models.py`,
`rank.py`, `storage.py`, `zillow.py`, `zumper.py`, `__init__.py`,
`tests/test_demo.py`, and four docs pages.

# Casita

[![Documentation](https://img.shields.io/badge/docs-casita-0b6e4f?style=for-the-badge)](https://matin.github.io/casita/)

Casita is a personal rental-search tool published as a public repo.

It started as a small script for a time-boxed San Francisco rental search with
two large dogs: scrape Zillow, Craigslist, Zumper, and Redfin; enrich the
listings; rank them; and render a static page that was easier to review than
four open browser tabs.

This is not a product or service. It is published as-is, under MIT, as a
personal-use codebase for an interview loop. The interesting part is what a
candidate chooses to improve.

## Demo

The demo is credentials-free and uses a sanitized SQLite fixture with cached
route times and precomputed LLM enrichment.

```bash
uv sync
uv run playwright install chromium
uv run casita demo
```

Then open <http://127.0.0.1:8765/>.

The demo does not scrape, call Vertex, deploy to Firebase, read GCS, or call the
Google Maps Routes API. It does use Playwright's local Chromium browser to
render Open Graph preview images from listing photos and facts. Live `search` /
`enrich` / `publish` paths still exist for private use and are controlled by
environment variables; see `.env.example`.

## What It Does

- Scrapes active rental listings from Zillow, Craigslist, Zumper, and Redfin.
- Normalizes listing facts into SQLite.
- Classifies dog policy and enriches details from listing pages.
- Uses Gemini for fact extraction, photo review, share blurbs, and ranking.
- Computes walking and driving times to curated SF / Marin anchors.
- Renders a static, mobile-friendly site with index and detail pages.
- Records votes and passes so future ranking can learn from reviewer feedback.

The domain assumptions are intentionally personal: large dogs, San Francisco
walkability, Marin driving context, trails, beaches, and good bakeries nearby.
That is the point of a personal tool.

## Docs

The [documentation site](https://matin.github.io/casita/) explains the systems
without turning them into assigned tasks. To run it locally instead:

```bash
uv run zensical serve
```

Start at `docs/index.md`, or run `uv run zensical build` to generate the site.

## Checks

```bash
make check
```

This compiles the Python modules, runs the pytest suite, runs the public leak
validator, builds the docs, builds the Python package artifacts, and checks
that the CLI imports.

## Contributing

Read `CONTRIBUTING.md`. The short version: fork the repo, pick something you
think makes Casita better, and explain why you chose it.
