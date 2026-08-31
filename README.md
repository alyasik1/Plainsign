# Plainsign

**Read before you sign.**

Your wallet shows you a sentence. The transaction is something else.

Plainsign simulates a transaction before you approve it and explains, in
plain language, what it will actually do: what leaves your wallet now,
what someone can take later, and who ends up in control.

It never holds keys, never signs, never broadcasts, and stores nothing.
By design, it cannot move your funds.

---

## Why

People do not lose money because they are careless. They lose it because
the interface showed one thing and the signature meant another — or
because a permission granted months ago never expired, or because an
address in their own history was planted there to be copied.

Recovery is close to nonexistent. The only moment that matters is the
second before you press confirm. Plainsign exists to make that second
useful.

## Status

**Early. The reasoning engine works; the chain plumbing does not exist yet.**

| Part | State |
| --- | --- |
| Risk rules | 13 rules, 55 tests |
| Plain-language output | working |
| Command line tool | working |
| Worked examples | reconstructed from published post-mortems, sources named |
| Calldata decoding | not started |
| Fork simulation | not started |
| Browser extension | not started |

Rules and explanations depend only on the data model, never on chain
access. That is deliberate: the part that decides what is dangerous can
be tested and reviewed offline, and the simulation backend can be
replaced without touching it.

## Try it

```bash
pip install -e ".[dev]"

python -m plainsign --all                      # every documented case
python -m plainsign --all --quiet              # one line each
python -m plainsign --case bybit-2025
python -m plainsign < examples/transfer.json   # your own transaction
python -m plainsign --json < examples/transfer.json

pytest -q                                      # 55 tests
python build_page.py > docs/index.html         # rebuild the page
```

`examples/` holds two runnable inputs — one dangerous, one clean — so the
JSON shape is documented by something that actually executes. A test
asserts they still disagree.

Exit code is `0` when nothing is flagged and `2` otherwise, so it can be
used in a pipeline.

## What it catches

| Rule | Pattern |
| --- | --- |
| `intent_mismatch` | the screen described a transfer; the transaction also grants permissions or changes control |
| `unlimited_approval` | open-ended spending rights that never expire |
| `gasless_signature` | an off-chain permit that costs no gas and leaves no trace in your history |
| `approval_to_eoa` | a permission granted to a person rather than a program |
| `ownership_change` | control of a contract, proxy or multisig moving to someone else |
| `address_poisoning` | a destination that only resembles one you have used before |
| `new_counterparty` | a contract deployed days ago |
| `wrong_network` | the same address format, the wrong chain |
| `sweeps_holdings` | a transaction that empties a balance |
| `reverts` | it fails when simulated, and you still pay |
| `uninformative_display` | the wallet shows no claim at all, yet the request hands over control |
| `destination_has_no_code` | nothing is deployed at the destination yet |
| `reported_address` | the address appears on a public malicious-address list |
| `unverified_source`, `approval_no_expiry` | notes, not alarms |

`intent_mismatch` is the one the project exists for. Everything else
checks the transaction; that rule checks the *gap between the transaction
and the description* — which is the failure mode behind the largest
signing losses on record.

## Design rules for the output

A tool that shouts at everything gets ignored, and an ignored safety tool
is worse than none. So:

- the ordinary transfer in the examples produces no findings, and a test
  enforces that
- every critical or warning finding must carry an action — a test
  enforces that too
- no jargon reaches the reader; a test bans the words

## Adding a rule

A rule is a pure function from `(Transaction, Simulation)` to findings.
Nothing else needs to change.

```python
@rule
def approval_to_person(tx, sim):
    for a in sim.approvals:
        if a.spender_is_contract:
            continue
        yield Finding(
            code="approval_to_eoa",
            severity="critical",
            title="You are granting permission to a person, not a program",
            detail="...",
            action="Do not sign. Nothing you are trying to do requires this.",
        )
```

## What the real cases changed

The rules were written first and tested against invented examples. Then
they were run against reconstructed incidents, and two of them failed:

- **`intent_mismatch` missed both permit drains.** It assumed the
  interface makes a false claim. In the documented campaigns the wallet
  claimed nothing at all — it displayed "Signature request" and no more,
  while the signature handed over every token. Silence is the more common
  failure and it was going unflagged. `uninformative_display` exists
  because of this.
- **Every contract-age check missed a whole campaign.** One drainer sends
  funds to an address calculated in advance and deploys the contract
  afterwards, so at signing time there is nothing there to be suspicious
  of. `destination_has_no_code` exists because of this.

Both are covered by regression tests named after where they came from.
This is the argument for running against real data before building
anything further: the rule the project was built around was the one that
failed.

## Next

1. Calldata decoding: resolve ABIs where the source is verified, fall
   back to a function-signature lookup where it is not.
2. Fork simulation to produce the state diff the rules already expect.
3. A single public page where anyone can paste a transaction.
4. A browser extension that reads a pending signature in place.

## Repository

```
plainsign/
  model.py      what a transaction is, and what simulating it revealed
  rules.py      13 rules, each a pure function; add one without touching anything else
  explain.py    the plain-language layer — the part the project exists for
  cases.py      documented incidents, each with its source and its unknowns
  __main__.py   command line
tests/          55 tests, including regressions named after the incidents that found them
examples/       runnable JSON inputs
docs/           generated page and text output
build_page.py   builds docs/index.html from the engine, so the demo cannot drift
```

## Limits

Plainsign can be wrong in three ways and says so on the page:

- **Missing data.** Unpublished source or an address with no history means
  some checks stay silent. Silence is not a clean bill of health.
- **Unknown patterns.** The rules cover documented attacks. A new
  technique passes until a rule exists — as one campaign already proved.
- **Wrong inputs.** The reasoning is only as good as the simulation
  feeding it, and the simulator is not written yet.

## Support this work

Plainsign is free, has no token, sells nothing, and gives donors nothing
in return. That last part is deliberate: a donation that buys a benefit
is not a donation.

**[Donate on Giveth →](https://giveth.io/project/plainsign-read-before-you-sign)**

100% of every donation reaches the project — Giveth takes no fee and sits
in the middle of nothing.

Donations pay for three things and nothing else: **infrastructure**
(simulation needs archive node access or a paid provider, plus hosting and
reference data), **maintenance** (attack patterns change and reference
data goes stale, and an unmaintained security tool is worse than none,
because people keep trusting it), and **development time** — a single
maintainer working in public, where every funded hour produces commits
anyone can read.

Incoming donations are visible on chain, and a spending summary is
published here alongside the commit history, so the money and the work
can be checked against each other.

If you cannot donate, the two most useful things you can give instead are
a transaction Plainsign should have flagged and didn't, or a false alarm
it raised — both open as issues, and false alarms are treated as real
bugs.

## Licence

MIT.
