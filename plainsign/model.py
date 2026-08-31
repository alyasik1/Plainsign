"""Data model: what a transaction is, and what simulating it revealed.

Rules and explanations work on these structures only, never on chain
access. That keeps the risk logic testable offline, and lets the
simulation backend be replaced without touching the part that decides
what is dangerous.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

UNLIMITED = 2**256 - 1
# Approvals above this are unlimited in every way that matters.
EFFECTIVELY_UNLIMITED = 2**200

TokenKind = Literal["erc20", "erc721", "erc1155", "native"]


@dataclass
class Token:
    address: str
    symbol: str
    decimals: int = 18
    kind: TokenKind = "erc20"

    def human(self, raw: int) -> str:
        if raw >= EFFECTIVELY_UNLIMITED:
            return f"unlimited {self.symbol}"
        if self.kind in ("erc721", "erc1155"):
            return f"{raw} {self.symbol}"
        value = raw / (10**self.decimals)
        if value == int(value):
            return f"{int(value):,} {self.symbol}"
        return f"{value:,.4f}".rstrip("0").rstrip(".") + f" {self.symbol}"


@dataclass
class BalanceChange:
    """Value moving out of (negative) or into (positive) the signer."""

    token: Token
    delta: int
    balance_before: Optional[int] = None

    @property
    def share_of_holdings(self) -> Optional[float]:
        if not self.balance_before or self.delta >= 0:
            return None
        return min(abs(self.delta) / self.balance_before, 1.0)


@dataclass
class Approval:
    """A spending permission granted to someone else."""

    token: Token
    spender: str
    amount: int
    spender_label: Optional[str] = None
    spender_is_contract: bool = True
    is_all: bool = False  # setApprovalForAll
    expires_in_days: Optional[int] = None

    @property
    def unlimited(self) -> bool:
        return self.is_all or self.amount >= EFFECTIVELY_UNLIMITED

    @property
    def who(self) -> str:
        return self.spender_label or self.spender


@dataclass
class OwnershipChange:
    """Control over a contract, proxy or multisig changed hands."""

    target: str
    what: str
    old: str
    new: str


@dataclass
class Counterparty:
    address: str
    deployed_days_ago: Optional[int] = None
    is_contract: bool = True
    verified_source: bool = False
    label: Optional[str] = None
    seen_before: bool = False
    # False means nothing is deployed at this address yet. Drainers send
    # funds to an address whose contract is deployed only afterwards, so
    # the destination looks like an empty wallet at signing time.
    has_code: Optional[bool] = None
    # Set when the address appears on a public malicious-address list.
    reported_malicious: Optional[str] = None


@dataclass
class Transaction:
    """What the user is about to sign."""

    signer: str
    to: str
    chain: str
    function: Optional[str] = None
    value: int = 0
    # Off-chain signatures (permit, Permit2, EIP-712 orders) cost no gas
    # and never appear as a pending transaction, which is why they slip past.
    offchain_signature: bool = False
    displayed_intent: Optional[str] = None  # what the interface claimed
    expected_chain: Optional[str] = None  # what the user believes they are on


@dataclass
class Simulation:
    """The result of running the transaction against forked state."""

    balance_changes: list[BalanceChange] = field(default_factory=list)
    approvals: list[Approval] = field(default_factory=list)
    ownership_changes: list[OwnershipChange] = field(default_factory=list)
    counterparties: list[Counterparty] = field(default_factory=list)
    recent_addresses: list[str] = field(default_factory=list)
    reverted: bool = False
    revert_reason: Optional[str] = None

    def counterparty(self, address: str) -> Optional[Counterparty]:
        for c in self.counterparties:
            if c.address.lower() == address.lower():
                return c
        return None
