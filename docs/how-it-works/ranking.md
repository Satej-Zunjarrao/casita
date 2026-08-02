---
icon: lucide/list-ordered
---

# Ranking

Ranking has two layers.

`src/casita/rank.py` is the deterministic sorter. It handles explicit pipeline
state, votes, filtered listings, and heuristic score. Human engagement beats a
fresh LLM rank because an active conversation is real work.

`src/casita/llm.py` is the preference ranker. `rank_listings` builds a compact
brief for each listing, adds route summaries, attaches current feedback, and
asks Gemini to return every listing with:

- a rank
- a one-sentence reason
- a severity: `ok`, `concerns`, or `filtered`

The ranking policy keeps the personal assumptions: large dogs, SF walkability,
Marin drive context, trail or beach access, and practical livability. An unverified dog policy is scored as a risk rather than a neutral. Two dogs
at 90 and 100 lb are the binding constraint of this search, so a listing whose
policy nobody has confirmed carries a small penalty, enough to break ties in
favour of certainty, not enough to bury a listing worth a phone call.

## Ways This Could Go Further

Ranking is deliberately still prompt-centric and Vertex-only. A future version
could make policy changes easier to evaluate, compare deterministic and LLM
rank movement, or support another model backend.
