"""Tests.

Two things matter here. Every rule fires when it should — and the
ordinary transfer stays silent. A tool that flags everything gets
ignored, and an ignored safety tool is worse than none.
"""

from __future__ import annotations

import pytest

from plainsign.cases import CASES, by_slug
from plainsign.explain import explain
from plainsign.model import (
    UNLIMITED,
    Approval,
    BalanceChange,
    Counterparty,
    OwnershipChange,
    Simulation,
    Token,
    Transaction,
)
from plainsign.rules import evaluate

USDC = Token("0xa0b8…eb48", "USDC", 6)


def codes(tx: Transaction, sim: Simulation) -> set[str]:
    return {f.code for f in evaluate(tx, sim)}


def plain(displayed: str | None = None, **kw) -> Transaction:
    return Transaction(signer="0xYou", to="0xdest", chain="Base", displayed_intent=displayed, **kw)


# --- the quiet case comes first, because it is the one that gets broken -------


def test_ordinary_transfer_is_silent():
    case = by_slug("ordinary-transfer")
    result = explain(case.tx, case.sim)
    assert result.findings == []
    assert result.severity == "note"
    assert result.verdict == "Nothing dangerous found."


def test_ordinary_transfer_still_states_what_leaves():
    case = by_slug("ordinary-transfer")
    assert explain(case.tx, case.sim).now == ["50 USDC leaves your wallet."]


# --- individual rules ---------------------------------------------------------


def test_unlimited_approval():
    sim = Simulation(approvals=[Approval(USDC, "0xspender", UNLIMITED)])
    assert "unlimited_approval" in codes(plain(), sim)


def test_bounded_approval_is_not_critical():
    sim = Simulation(approvals=[Approval(USDC, "0xspender", 50_000_000, expires_in_days=30)])
    assert "unlimited_approval" not in codes(plain(), sim)


def test_approval_without_expiry_is_noted():
    sim = Simulation(approvals=[Approval(USDC, "0xspender", 50_000_000)])
    assert "approval_no_expiry" in codes(plain(), sim)


def test_approval_to_a_person():
    sim = Simulation(
        approvals=[Approval(USDC, "0xperson", 50_000_000, spender_is_contract=False)]
    )
    assert "approval_to_eoa" in codes(plain(), sim)


def test_gasless_signature():
    sim = Simulation(approvals=[Approval(USDC, "0xspender", UNLIMITED)])
    assert "gasless_signature" in codes(plain(offchain_signature=True), sim)


def test_gasless_signature_without_approval_is_quiet():
    assert "gasless_signature" not in codes(plain(offchain_signature=True), Simulation())


def test_ownership_change():
    sim = Simulation(
        ownership_changes=[OwnershipChange("the vault", "The owner", "you", "0xthem")]
    )
    assert "ownership_change" in codes(plain(), sim)


def test_new_contract():
    sim = Simulation(counterparties=[Counterparty("0xnew", deployed_days_ago=3)])
    assert "new_counterparty" in codes(plain(), sim)


def test_old_contract_is_quiet():
    sim = Simulation(
        counterparties=[Counterparty("0xold", deployed_days_ago=900, verified_source=True)]
    )
    assert codes(plain(), sim) == set()


@pytest.mark.parametrize(
    "destination,history,expected",
    [
        ("0x3f9a12cc41b8d7e05a6c93f10b47e2da0ce4d7b1", "0x3f9a12aa77c4bbe1f0d8391b25c7e4fa9be4d7b1", True),
        ("0x742d35cc6634c0532925a3b844bc454e4438f44e", "0x742d35cc6634c0532925a3b844bc454e4438f44e", False),
        ("0x1111111111111111111111111111111111111111", "0x9999999999999999999999999999999999999999", False),
    ],
)
def test_address_poisoning(destination, history, expected):
    tx = Transaction(signer="0xYou", to=destination, chain="Base")
    sim = Simulation(recent_addresses=[history])
    assert ("address_poisoning" in codes(tx, sim)) is expected


def test_sweeping_the_balance():
    sim = Simulation(
        balance_changes=[BalanceChange(USDC, -990_000_000, balance_before=1_000_000_000)]
    )
    assert "sweeps_holdings" in codes(plain(), sim)


def test_partial_spend_is_quiet():
    sim = Simulation(
        balance_changes=[BalanceChange(USDC, -100_000_000, balance_before=1_000_000_000)]
    )
    assert "sweeps_holdings" not in codes(plain(), sim)


def test_wrong_network():
    tx = Transaction(signer="0xYou", to="0xdest", chain="Polygon", expected_chain="Arbitrum")
    assert "wrong_network" in codes(tx, Simulation())


def test_revert():
    sim = Simulation(reverted=True, revert_reason="insufficient allowance")
    assert "reverts" in codes(plain(), sim)


# --- the rule the project exists for -----------------------------------------


def test_intent_mismatch_catches_hidden_approval():
    sim = Simulation(approvals=[Approval(USDC, "0xspender", UNLIMITED)])
    assert "intent_mismatch" in codes(plain("Send 50 USDC"), sim)


def test_intent_mismatch_catches_hidden_ownership_change():
    sim = Simulation(
        ownership_changes=[OwnershipChange("the vault", "The implementation", "audited", "0xnew")]
    )
    assert "intent_mismatch" in codes(plain("Transfer 12 ETH to treasury"), sim)


def test_no_mismatch_when_nothing_is_hidden():
    sim = Simulation(balance_changes=[BalanceChange(USDC, -50_000_000)])
    assert "intent_mismatch" not in codes(plain("Send 50 USDC"), sim)


# --- output contract ----------------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.slug)
def test_every_case_renders(case):
    text = explain(case.tx, case.sim).render()
    assert text.strip()
    assert "None" not in text


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.slug)
def test_every_warning_tells_you_what_to_do(case):
    for finding in explain(case.tx, case.sim).findings:
        if finding.severity in ("critical", "warning"):
            assert finding.action, f"{finding.code} has no action"


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.slug)
def test_no_jargon_in_output(case):
    """The reader is not expected to know these words."""
    # Addresses themselves are fine — people see those anyway. What must
    # not appear is vocabulary the reader would have to look up.
    banned = ["calldata", "ABI", "EOA", "nonce", "EIP-", "delegatecall", "revert("]
    text = explain(case.tx, case.sim).render()
    for word in banned:
        assert word not in text, f"{word} leaked into the explanation"


def test_dangerous_cases_all_say_do_not_sign():
    for case in CASES:
        if case.slug == "ordinary-transfer":
            continue
        assert explain(case.tx, case.sim).severity in ("critical", "warning")


# --- regressions found by running the engine against documented incidents ----


def test_bare_signature_request_is_flagged():
    """Two real permit drains showed only 'Signature request'.

    intent_mismatch stayed silent because nothing false was claimed.
    """
    sim = Simulation(approvals=[Approval(USDC, "0xspender", UNLIMITED)])
    found = codes(plain("Signature request"), sim)
    assert "uninformative_display" in found


def test_undeployed_destination_is_flagged():
    """A drainer sends to a precomputed address and deploys after.

    Every check keyed on contract age stays silent, because there is no
    contract yet.
    """
    tx = Transaction(signer="0xYou", to="0xnothing", chain="Ethereum")
    sim = Simulation(
        balance_changes=[BalanceChange(USDC, -100_000_000)],
        counterparties=[Counterparty("0xnothing", is_contract=False, has_code=False)],
    )
    assert "destination_has_no_code" in codes(tx, sim)


def test_known_destination_with_no_code_is_quiet():
    """An ordinary wallet you have paid before must not trip the rule."""
    tx = Transaction(signer="0xYou", to="0xfriend", chain="Base")
    sim = Simulation(
        balance_changes=[BalanceChange(USDC, -100_000_000)],
        counterparties=[Counterparty("0xfriend", is_contract=False, has_code=False, seen_before=True)],
    )
    assert "destination_has_no_code" not in codes(tx, sim)


def test_reported_address():
    sim = Simulation(
        counterparties=[Counterparty("0xbad", reported_malicious="listed by a public tracker")]
    )
    assert "reported_address" in codes(plain(), sim)


def test_documented_cases_all_produce_a_critical_finding():
    """Each reconstructed incident must be caught, not merely noted."""
    for case in CASES:
        if case.slug == "ordinary-transfer":
            continue
        severity = explain(case.tx, case.sim).severity
        assert severity in ("critical", "warning"), f"{case.slug} was not caught"


def test_every_documented_case_names_its_source():
    for case in CASES:
        assert case.source, f"{case.slug} has no source"


# --- output discipline --------------------------------------------------------


def test_repeated_approvals_produce_one_finding():
    """Three unlimited approvals must not print the same warning three times.

    Repetition teaches the reader to skim, which is the opposite of the point.
    """
    weth = Token("0xc02a…6cc2", "WETH", 18)
    sim = Simulation(
        approvals=[
            Approval(USDC, "0xspender", UNLIMITED),
            Approval(weth, "0xspender", UNLIMITED),
        ]
    )
    unlimited = [f for f in evaluate(plain(), sim) if f.code == "unlimited_approval"]
    assert len(unlimited) == 1
    assert "USDC and WETH" in unlimited[0].detail


def test_actions_are_deduplicated_and_ordered():
    sim = Simulation(
        approvals=[Approval(USDC, "0xspender", UNLIMITED)],
        counterparties=[Counterparty("0xspender", deployed_days_ago=1)],
    )
    actions = explain(plain("Claim your airdrop"), sim).actions
    assert len(actions) == len(set(actions))
    assert actions


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.slug)
def test_every_case_has_a_one_line_summary(case):
    summary = explain(case.tx, case.sim).summary
    assert summary.endswith(".")
    assert summary[0].isupper() or summary[0].isdigit()
    assert len(summary) < 120
    assert "…" in summary or "0x" not in summary, "long address left unshortened"


def test_safe_flag_matches_severity():
    case = by_slug("ordinary-transfer")
    assert explain(case.tx, case.sim).safe is True
    bad = by_slug("bybit-2025")
    assert explain(bad.tx, bad.sim).safe is False


def test_json_output_is_serialisable():
    import json

    for case in CASES:
        json.dumps(explain(case.tx, case.sim).as_dict())


# --- the shipped examples must actually run ----------------------------------


@pytest.mark.parametrize("name", ["transfer.json", "ordinary.json"])
def test_shipped_examples_parse_and_run(name):
    import json
    import pathlib

    from plainsign.__main__ import parse

    path = pathlib.Path(__file__).parent.parent / "examples" / name
    tx, sim = parse(json.loads(path.read_text()))
    assert explain(tx, sim).render()


def test_example_files_disagree():
    """One example must be dangerous and one must be clean, or the
    examples do not demonstrate anything."""
    import json
    import pathlib

    from plainsign.__main__ import parse

    base = pathlib.Path(__file__).parent.parent / "examples"
    results = {
        name: explain(*parse(json.loads((base / name).read_text()))).safe
        for name in ("transfer.json", "ordinary.json")
    }
    assert results == {"transfer.json": False, "ordinary.json": True}
