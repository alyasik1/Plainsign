"""Command line entry point.

    python -m plainsign --case drainer-approval
    python -m plainsign --all
    cat tx.json | python -m plainsign
    python -m plainsign --json < tx.json

The JSON shape mirrors the model: a `transaction` object and a
`simulation` object. Until the simulator lands, this is how another
tool feeds Plainsign a decoded transaction.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__

from .cases import CASES, by_slug
from .explain import explain
from .model import (
    Approval,
    BalanceChange,
    Counterparty,
    OwnershipChange,
    Simulation,
    Token,
    Transaction,
)

RULE = "─" * 68


def _token(raw: dict) -> Token:
    return Token(
        address=raw.get("address", "unknown"),
        symbol=raw.get("symbol", "tokens"),
        decimals=int(raw.get("decimals", 18)),
        kind=raw.get("kind", "erc20"),
    )


def parse(payload: dict) -> tuple[Transaction, Simulation]:
    tx = Transaction(**payload["transaction"])
    raw = payload.get("simulation", {})
    sim = Simulation(
        balance_changes=[
            BalanceChange(_token(c["token"]), int(c["delta"]), c.get("balance_before"))
            for c in raw.get("balance_changes", [])
        ],
        approvals=[
            Approval(
                _token(a["token"]),
                a["spender"],
                int(a["amount"]),
                a.get("spender_label"),
                a.get("spender_is_contract", True),
                a.get("is_all", False),
                a.get("expires_in_days"),
            )
            for a in raw.get("approvals", [])
        ],
        ownership_changes=[OwnershipChange(**o) for o in raw.get("ownership_changes", [])],
        counterparties=[Counterparty(**c) for c in raw.get("counterparties", [])],
        recent_addresses=raw.get("recent_addresses", []),
        reverted=raw.get("reverted", False),
        revert_reason=raw.get("revert_reason"),
    )
    return tx, sim


def show(shown: str, tx: Transaction, sim: Simulation, title: str = "", quiet: bool = False) -> None:
    if quiet:
        result = explain(tx, sim)
        print(f"{result.verdict} {result.summary}")
        return
    if title:
        print(RULE)
        print(title)
    print(RULE)
    print(f'Your wallet shows:  "{shown}"')
    print()
    print(explain(tx, sim).render())
    print()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="plainsign", description="Read a transaction before you sign it.")
    ap.add_argument("--case", help="run one worked example by slug")
    ap.add_argument("--all", action="store_true", help="run every worked example")
    ap.add_argument("--json", action="store_true", help="emit machine-readable output")
    ap.add_argument("--quiet", action="store_true", help="print only the one-line summary")
    ap.add_argument("--version", action="version", version=f"plainsign {__version__}")
    args = ap.parse_args(argv)

    if args.all or args.case:
        cases = CASES if args.all else [by_slug(args.case)]
        if args.json:
            print(json.dumps([explain(c.tx, c.sim).as_dict() for c in cases], indent=2))
            return 0
        for c in cases:
            show(c.shown, c.tx, c.sim, title=c.name, quiet=args.quiet)
        return 0

    if sys.stdin.isatty():
        ap.print_help()
        return 1

    tx, sim = parse(json.load(sys.stdin))
    result = explain(tx, sim)
    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
    else:
        show(tx.displayed_intent or "(nothing)", tx, sim, quiet=args.quiet)
    return 0 if result.severity == "note" else 2


def cli() -> int:
    """Entry point that survives a closed pipe, e.g. `plainsign --all | head`."""
    try:
        return main()
    except BrokenPipeError:
        try:
            sys.stdout.close()
        finally:
            return 0
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(cli())
