# Contributing

The most useful contribution is a rule that catches something real, with
a link to the incident it came from.

## Adding a rule

A rule is a pure function from `(Transaction, Simulation)` to findings.
It must not fetch anything — every piece of evidence arrives in the
`Simulation`. That is what keeps the reasoning testable offline and
reviewable by someone who does not run a node.

```python
@rule
def destination_has_no_code(tx, sim):
    for c in sim.counterparties:
        if c.has_code is not False or c.seen_before:
            continue
        yield Finding(
            code="destination_has_no_code",
            severity="warning",
            title="Nothing exists at this address yet",
            detail="...",
            action="Confirm the address from the project's own site before sending.",
        )
        return
```

## Rules for rule-writing

1. **Every critical or warning finding carries an `action`.** A warning
   without something to do is just anxiety. A test enforces this.
2. **No jargon reaches the reader.** No `calldata`, `ABI`, `EOA`,
   `nonce`, `delegatecall`. A test enforces this too. If you cannot say
   it in ordinary words, the rule is not finished.
3. **Say it once.** If a rule can match several items, aggregate them
   into one finding rather than repeating the same warning. Repetition
   teaches people to skim.
4. **Silence is a feature.** The ordinary transfer in the test suite must
   produce no findings. Before adding a rule, check it against that case.
   A tool that flags everything gets ignored, and an ignored safety tool
   is worse than none.
5. **Severity means something.** `critical` = do not sign. `warning` =
   stop and check. `note` = worth knowing. Nothing routine is critical.

## Adding a case

Cases in `plainsign/cases.py` come from published post-mortems. Each one
needs a `source`. Where a detail was never published — the exact wording
a wallet displayed, a contract's age — put it in `unknowns` and leave the
field unset. Do not invent it. An invented detail in a security tool is
worse than a missing one.

## Before opening a pull request

```bash
pytest -q
python build_page.py > docs/index.html
```

The page is generated from the engine, so a change to the wording of a
rule changes the page. Commit both.
