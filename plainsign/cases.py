"""Worked examples, taken from documented incidents.

Every case below is reconstructed from public post-mortems and security
reporting, with the source named. Where a detail was not published, the
field is left unset rather than invented — see `unknowns`.

The point of each case is the gap: what the interface displayed, against
what the transaction did.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import (
    UNLIMITED,
    Approval,
    BalanceChange,
    Counterparty,
    OwnershipChange,
    Simulation,
    Token,
    Transaction,
)

ETH = Token("native", "ETH", 18, kind="native")
SPWETH = Token("0xc035…9d1f", "spWETH", 18)
PEPE = Token("0x6982…933933", "PEPE", 18)
USDC = Token("0xa0b8…eb48", "USDC", 6)


@dataclass
class Case:
    slug: str
    name: str
    pattern: str
    shown: str
    tx: Transaction
    sim: Simulation
    source: str = ""
    unknowns: list[str] = field(default_factory=list)


CASES: list[Case] = [
    Case(
        slug="bybit-2025",
        name="Bybit, 21 February 2025",
        pattern="Compromised interface displayed a routine transfer; the payload replaced the wallet's logic",
        shown="Send 30,000 ETH to the warm wallet",
        source="NCC Group technical analysis; DFNS breakdown; Bybit incident timeline",
        tx=Transaction(
            signer="Cold wallet signer (3 of 5)",
            to="0x1Db92e2EeBC8E0c075a02BeA49a2935BcD2dFCF4",
            chain="Ethereum",
            function="execTransaction(...)",
            displayed_intent="Send 30,000 ETH to the warm wallet",
        ),
        sim=Simulation(
            ownership_changes=[
                OwnershipChange(
                    target="the cold wallet",
                    what="The implementation the wallet runs",
                    old="the audited Safe logic",
                    new="0x4766…86e2, an attacker-controlled contract",
                )
            ],
            counterparties=[
                Counterparty(
                    "0x9622…7242",
                    deployed_days_ago=2,
                    verified_source=False,
                    has_code=True,
                )
            ],
        ),
        unknowns=[
            "Cold wallet balance at signing time is public (401,347 ETH) but is not "
            "part of this transaction's diff, so it is not modelled as a balance change.",
        ],
    ),
    Case(
        slug="permit-phishing-1.28m",
        name="0xb0b8…40c7, 14 October 2024",
        pattern="Off-chain permit signature; no gas, no entry in transaction history",
        shown="Signature request",
        source="PeckShield alert; Arkham attribution to Inferno Drainer",
        tx=Transaction(
            signer="0xb0b8…40c7",
            to="the address labelled Fake_Phishing442846",
            chain="Ethereum",
            function="permit(...)",
            offchain_signature=True,
            displayed_intent="Signature request",
        ),
        sim=Simulation(
            approvals=[
                Approval(
                    PEPE,
                    "the address labelled Fake_Phishing442846",
                    UNLIMITED,
                    spender_label="an address later reported as a phishing address",
                )
            ],
            counterparties=[
                Counterparty(
                    "the address labelled Fake_Phishing442846",
                    verified_source=False,
                    has_code=True,
                    reported_malicious="labelled Fake_Phishing442846 and linked to a $32M drain two weeks earlier",
                )
            ],
        ),
        unknowns=[
            "The exact wording the wallet displayed was not published; "
            "'Signature request' is the generic label wallets use.",
            "Contract age of the spender was not reported.",
        ],
    ),
    Case(
        slug="spweth-32m",
        name="12,083 spWETH, 28 September 2024",
        pattern="Permit phishing against a single large holder",
        shown="Signature request",
        source="PeckShield; reporting on the Inferno Drainer campaign",
        tx=Transaction(
            signer="Holder of 12,083 spWETH",
            to="the spender contract used in the campaign",
            chain="Ethereum",
            function="permit(...)",
            offchain_signature=True,
            displayed_intent="Signature request",
        ),
        sim=Simulation(
            approvals=[
                Approval(SPWETH, "the spender contract used in the campaign", UNLIMITED, spender_label="an unnamed address")
            ],
            counterparties=[Counterparty("the spender contract used in the campaign", verified_source=False, has_code=True)],
        ),
        unknowns=["Wallet display wording and spender contract age were not published."],
    ),
    Case(
        slug="precomputed-destination",
        name="Transfer to an address that does not exist yet",
        pattern="Drainer sends funds to a precomputed address, deploying the contract afterwards",
        shown="Send 4,200 USDC",
        source="Check Point Research, Inferno Drainer analysis",
        tx=Transaction(
            signer="0xYou",
            to="the destination address",
            chain="Ethereum",
            function="transfer(address,uint256)",
            displayed_intent="Send 4,200 USDC",
        ),
        sim=Simulation(
            balance_changes=[BalanceChange(USDC, -4_200_000_000, balance_before=4_400_000_000)],
            counterparties=[
                Counterparty("the destination address", is_contract=False, has_code=False)
            ],
        ),
        unknowns=["Amount is illustrative; the technique is what is documented."],
    ),
    Case(
        slug="ordinary-transfer",
        name="An ordinary payment",
        pattern="Nothing wrong — included deliberately, to prove the tool stays quiet",
        shown="Send 50 USDC",
        source="Constructed",
        tx=Transaction(
            signer="0xYou",
            to="0x742d35cc6634c0532925a3b844bc454e4438f44e",
            chain="Base",
            expected_chain="Base",
            function="transfer(address,uint256)",
            displayed_intent="Send 50 USDC",
        ),
        sim=Simulation(
            balance_changes=[BalanceChange(USDC, -50_000_000, balance_before=1_200_000_000)],
            recent_addresses=["0x742d35cc6634c0532925a3b844bc454e4438f44e"],
            counterparties=[
                Counterparty(
                    "0x742d35cc6634c0532925a3b844bc454e4438f44e",
                    is_contract=False,
                    seen_before=True,
                    has_code=False,
                )
            ],
        ),
    ),
]


def by_slug(slug: str) -> Case:
    for c in CASES:
        if c.slug == slug:
            return c
    raise KeyError(slug)
