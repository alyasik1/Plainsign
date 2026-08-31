"""Risk rules.

Each rule reads the transaction plus its simulated effects and yields
zero or more findings. Rules never fetch anything — all evidence arrives
in the Simulation — so a new rule is a pure function and nothing else
needs to change.

Every finding carries an `action`: what the reader should do instead.
A warning without an action is just anxiety.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterator, Literal, Optional

from .model import Simulation, Transaction

Severity = Literal["critical", "warning", "note"]

NEW_CONTRACT_DAYS = 30
SWEEP_SHARE = 0.9
LOOKALIKE_EDGE = 6

SEVERITY_ORDER = {"critical": 0, "warning": 1, "note": 2}


@dataclass
class Finding:
    code: str
    severity: Severity
    title: str
    detail: str
    action: Optional[str] = None


Rule = Callable[[Transaction, Simulation], Iterator[Finding]]
RULES: list[Rule] = []


def rule(fn: Rule) -> Rule:
    RULES.append(fn)
    return fn


# --- what you are giving away -------------------------------------------------


def _join(items: list[str]) -> str:
    """Human list: a, b and c. Repeating a warning per item trains the
    reader to skim, so related effects are stated once, together."""
    items = list(dict.fromkeys(items))
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


@rule
def unlimited_approval(tx: Transaction, sim: Simulation) -> Iterator[Finding]:
    unlimited = [a for a in sim.approvals if a.unlimited]
    if not unlimited:
        return
    collections = [a.token.symbol for a in unlimited if a.is_all]
    balances = [a.token.symbol for a in unlimited if not a.is_all]
    phrases = []
    if balances:
        phrases.append(f"all of your {_join(balances)}, now and in the future")
    if collections:
        phrases.append(
            f"every {_join(collections)} item you own, including ones you buy later"
        )
    holdings = "; ".join(phrases) if len(phrases) > 1 else phrases[0]
    who = _join([a.who for a in unlimited])
    plural = "permissions" if len(unlimited) > 1 else "permission"
    yield Finding(
        code="unlimited_approval",
        severity="critical",
        title=f"You are granting unlimited, open-ended {plural}",
        detail=(
            f"{who} will be able to move {holdings}. It does not expire and "
            "does not ask again. It stays active until you revoke it."
        ),
        action=(
            "Approve only the amount you are spending right now. If the site "
            "will not let you, that is a reason to leave, not to sign."
        ),
    )


@rule
def approval_never_expires(tx: Transaction, sim: Simulation) -> Iterator[Finding]:
    open_ended = [
        a for a in sim.approvals if not a.unlimited and a.expires_in_days is None
    ]
    if not open_ended:
        return
    yield Finding(
        code="approval_no_expiry",
        severity="note",
        title="This permission has no end date",
        detail=(
            f"{_join([a.who for a in open_ended])} keeps the right to move "
            f"{_join([a.token.human(a.amount) for a in open_ended])} "
            "indefinitely, even after you stop using the site."
        ),
        action="Revoke it once you are done.",
    )


@rule
def approval_to_person(tx: Transaction, sim: Simulation) -> Iterator[Finding]:
    for a in sim.approvals:
        if a.spender_is_contract:
            continue
        yield Finding(
            code="approval_to_eoa",
            severity="critical",
            title="You are granting permission to a person, not a program",
            detail=(
                f"{a.who} is an ordinary wallet, not a contract. Legitimate "
                "applications ask for permissions on behalf of their code. "
                "There is no honest reason for an individual to hold this."
            ),
            action="Do not sign. Nothing you are trying to do requires this.",
        )
        return


@rule
def gasless_signature(tx: Transaction, sim: Simulation) -> Iterator[Finding]:
    if not tx.offchain_signature or not sim.approvals:
        return
    yield Finding(
        code="gasless_signature",
        severity="critical",
        title="This is a signature, not a transaction — and it still moves money",
        detail=(
            "It costs no gas and will not show up in your transaction history, "
            "which is exactly why it looks harmless. It authorises someone to "
            "take your tokens later, without asking you again."
        ),
        action=(
            "Treat a free signature with the same suspicion as a payment. "
            "Sign-in requests never need permission over your tokens."
        ),
    )


@rule
def ownership_transfer(tx: Transaction, sim: Simulation) -> Iterator[Finding]:
    for o in sim.ownership_changes:
        yield Finding(
            code="ownership_change",
            severity="critical",
            title="This changes who controls the contract",
            detail=(
                f"{o.what} on {o.target} changes from {o.old} to {o.new}. "
                "Afterwards, control over the funds held there belongs to "
                "someone else, and no further signature from you is needed."
            ),
            action="Do not sign until the new controller is independently confirmed.",
        )


# --- who you are dealing with -------------------------------------------------


@rule
def new_counterparty(tx: Transaction, sim: Simulation) -> Iterator[Finding]:
    for c in sim.counterparties:
        age = c.deployed_days_ago
        if not c.is_contract or age is None or age > NEW_CONTRACT_DAYS:
            continue
        when = "today" if age == 0 else f"{age} day{'s' if age != 1 else ''} ago"
        yield Finding(
            code="new_counterparty",
            severity="warning",
            title="This contract was created very recently",
            detail=(
                f"The contract at {c.address} was deployed {when}. Draining "
                "campaigns run on contracts only days old. The established "
                "protocol you were looking for is not new."
            ),
            action="Check the address against the project's own documentation.",
        )
        return


@rule
def unverified_counterparty(tx: Transaction, sim: Simulation) -> Iterator[Finding]:
    for c in sim.counterparties:
        if not c.is_contract or c.verified_source:
            continue
        yield Finding(
            code="unverified_source",
            severity="note",
            title="Nobody can read what this contract does",
            detail=(
                f"The source code for {c.address} has not been published, so "
                "its behaviour cannot be checked by you or anyone else."
            ),
        )
        return


@rule
def destination_has_no_code(tx: Transaction, sim: Simulation) -> Iterator[Finding]:
    """Found by running the engine against a documented drainer campaign.

    The kit sends funds to an address whose contract is deployed only
    afterwards. At signing time nothing is there, so every check that
    asks "how old is this contract" stays silent — the address looks
    like an ordinary empty wallet.
    """
    for c in sim.counterparties:
        if c.has_code is not False or c.seen_before:
            continue
        if not any(ch.delta < 0 for ch in sim.balance_changes) and not sim.approvals:
            continue
        yield Finding(
            code="destination_has_no_code",
            severity="warning",
            title="Nothing exists at this address yet",
            detail=(
                f"There is no contract and no history at {c.address}. A "
                "destination can be calculated in advance and the code put "
                "there after you send, which is a known way of staying "
                "invisible to checks that ask how old a contract is."
            ),
            action="Confirm the address from the project's own site before sending.",
        )
        return


@rule
def reported_address(tx: Transaction, sim: Simulation) -> Iterator[Finding]:
    for c in sim.counterparties:
        if not c.reported_malicious:
            continue
        yield Finding(
            code="reported_address",
            severity="critical",
            title="This address has been publicly reported",
            detail=f"{c.address} is listed as malicious: {c.reported_malicious}.",
            action="Do not sign. Close the page you came from.",
        )
        return


def _lookalike(a: str, b: str) -> bool:
    a, b = a.lower(), b.lower()
    if a == b or len(a) != len(b):
        return False
    return a[:LOOKALIKE_EDGE] == b[:LOOKALIKE_EDGE] and a[-4:] == b[-4:]


@rule
def address_poisoning(tx: Transaction, sim: Simulation) -> Iterator[Finding]:
    for known in sim.recent_addresses:
        if not _lookalike(tx.to, known):
            continue
        yield Finding(
            code="address_poisoning",
            severity="critical",
            title="This address only looks like one you have used before",
            detail=(
                f"You are sending to {tx.to}. You previously sent to {known}. "
                "They share the first and last characters and differ in the "
                "middle. This is address poisoning: a fake entry is planted in "
                "your history so that you copy it later by mistake."
            ),
            action=(
                "Compare the full address against the original source, not "
                "against your own history."
            ),
        )
        return


# --- what leaves, and where ---------------------------------------------------


@rule
def sweeps_holdings(tx: Transaction, sim: Simulation) -> Iterator[Finding]:
    for change in sim.balance_changes:
        share = change.share_of_holdings
        if share is None or share < SWEEP_SHARE:
            continue
        pct = "all" if share >= 0.999 else f"{share:.0%}"
        yield Finding(
            code="sweeps_holdings",
            severity="warning",
            title=f"This moves {pct} of your {change.token.symbol}",
            detail=(
                "Transactions that empty a balance are worth a second look, "
                "because there is nothing left to recover from if it is wrong."
            ),
            action="Send a small test amount first and confirm it arrives.",
        )


@rule
def wrong_network(tx: Transaction, sim: Simulation) -> Iterator[Finding]:
    if not tx.expected_chain or tx.expected_chain == tx.chain:
        return
    yield Finding(
        code="wrong_network",
        severity="critical",
        title=f"You are on {tx.chain}, not {tx.expected_chain}",
        detail=(
            "The same address format is used across networks, so the address "
            "alone tells you nothing about which one applies. Funds sent on a "
            "network the recipient does not watch are usually unrecoverable."
        ),
        action=f"Switch to {tx.expected_chain}, or confirm the recipient accepts {tx.chain}.",
    )


@rule
def transaction_reverts(tx: Transaction, sim: Simulation) -> Iterator[Finding]:
    if not sim.reverted:
        return
    reason = f" Reason given: {sim.revert_reason}." if sim.revert_reason else ""
    yield Finding(
        code="reverts",
        severity="warning",
        title="This transaction fails when simulated",
        detail=f"It would not complete, but you would still pay the gas.{reason}",
        action="Do not send it. Something about the request is already wrong.",
    )


# --- the one that matters most ------------------------------------------------


@rule
def intent_mismatch(tx: Transaction, sim: Simulation) -> Iterator[Finding]:
    """The screen said one thing, the state diff says another.

    This is the failure mode behind the largest signing losses on record:
    the interface, not the chain, was what everyone trusted.
    """
    if not tx.displayed_intent:
        return
    hidden = bool(sim.approvals or sim.ownership_changes)
    sounds_simple = any(
        word in tx.displayed_intent.lower()
        for word in ("transfer", "send", "swap", "claim", "mint", "sign in", "connect", "verify")
    )
    if not (hidden and sounds_simple):
        return
    yield Finding(
        code="intent_mismatch",
        severity="critical",
        title="What you were shown is not what this does",
        detail=(
            f'Your wallet described this as "{tx.displayed_intent}". Simulating '
            "it shows that it also grants permissions or hands over control. "
            "The screen is not the transaction."
        ),
        action="Trust the simulated result over the description.",
    )


UNINFORMATIVE = (
    "signature request",
    "sign message",
    "signature",
    "confirm",
    "approve",
    "sign",
    "",
)


@rule
def uninformative_display(tx: Transaction, sim: Simulation) -> Iterator[Finding]:
    """Found by running the engine against two documented permit drains.

    `intent_mismatch` assumed the interface makes a false claim. In the
    real campaigns it makes no claim at all — the wallet says "Signature
    request" and nothing else, while the signature hands over every
    token. Silence is the more common failure, and it was going
    unflagged.
    """
    shown = (tx.displayed_intent or "").strip().lower()
    if shown not in UNINFORMATIVE:
        return
    if not (sim.approvals or sim.ownership_changes):
        return
    yield Finding(
        code="uninformative_display",
        severity="critical",
        title="Your wallet is not telling you what this does",
        detail=(
            f'The request is labelled "{tx.displayed_intent or "(no description)"}" '
            "and nothing more, yet it hands over control of your tokens. A "
            "request that will not say what it does is not one you can judge "
            "from the screen."
        ),
        action="Read the effects below instead of the label, and sign nothing you cannot restate in your own words.",
    )


def evaluate(tx: Transaction, sim: Simulation) -> list[Finding]:
    findings = [f for r in RULES for f in r(tx, sim)]
    return sorted(findings, key=lambda f: SEVERITY_ORDER[f.severity])


def worst_severity(findings: list[Finding]) -> Severity:
    return findings[0].severity if findings else "note"
