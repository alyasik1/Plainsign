"""Plain-language output.

The whole point of the project lives here. Someone who does not know
what calldata is should finish reading and know what happens if they
press confirm.

Wording rules:
  - second person, present tense
  - say what leaves the wallet before saying anything else
  - never use a word the reader would have to look up
  - every warning ends with something to do
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .model import Simulation, Transaction
from .rules import Finding, Severity, evaluate, worst_severity

VERDICTS: dict[Severity, str] = {
    "critical": "Do not sign this.",
    "warning": "Stop and check this.",
    "note": "Nothing dangerous found.",
}

MARKS: dict[Severity, str] = {"critical": "!!", "warning": " !", "note": " ·"}


@dataclass
class Explanation:
    verdict: str
    severity: Severity
    summary: str = ""
    now: list[str] = field(default_factory=list)
    later: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def safe(self) -> bool:
        return self.severity == "note"

    @property
    def actions(self) -> list[str]:
        """Deduplicated, in severity order — what to do, not why."""
        return list(dict.fromkeys(f.action for f in self.findings if f.action))

    def as_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "severity": self.severity,
            "summary": self.summary,
            "now": self.now,
            "later": self.later,
            "actions": self.actions,
            "findings": [asdict(f) for f in self.findings],
        }

    def render(self) -> str:
        out = [self.verdict]
        if self.summary:
            out.append(self.summary)
        out.append("")
        out.append("What happens immediately")
        out += [f"  - {line}" for line in (self.now or ["Nothing leaves your wallet."])]
        if self.later:
            out += ["", "What can happen afterwards"]
            out += [f"  - {line}" for line in self.later]
        if self.findings:
            out += ["", "Why this is flagged"]
            for f in self.findings:
                out.append(f"  {MARKS[f.severity]} {f.title}")
                out.append(f"     {f.detail}")
                if f.action:
                    out.append(f"     → {f.action}")
        if self.actions:
            out += ["", "What to do"]
            out += [f"  {i}. {a}" for i, a in enumerate(self.actions, 1)]
        return "\n".join(out)


def _immediate(sim: Simulation) -> list[str]:
    lines = []
    for change in sim.balance_changes:
        amount = change.token.human(abs(change.delta))
        if change.delta < 0:
            lines.append(f"{amount} leaves your wallet.")
        else:
            lines.append(f"You receive {amount}.")
    return lines


def _afterwards(sim: Simulation) -> list[str]:
    lines = []
    for a in sim.approvals:
        what = f"every {a.token.symbol} you own" if a.is_all else a.token.human(a.amount)
        window = (
            f" for the next {a.expires_in_days} days"
            if a.expires_in_days is not None
            else " at any time from now on"
        )
        lines.append(f"{a.who} can take {what}{window}, without asking you again.")
    for o in sim.ownership_changes:
        lines.append(f"{o.new} takes control of {o.target}.")
    return lines


def short(address: str) -> str:
    """Addresses are shown to people, so they are shortened the way people
    read them — head and tail, which is also where lookalikes differ."""
    if address.startswith("0x") and len(address) > 20:
        return f"{address[:6]}…{address[-4:]}"
    return address


def _summary(tx: Transaction, sim: Simulation, findings: list[Finding]) -> str:
    """One sentence, for a notification or an extension badge.

    Says the worst consequence, not the worst-sounding word.
    """
    if sim.ownership_changes:
        o = sim.ownership_changes[0]
        return f"Control of {o.target} passes to someone else."
    if sim.approvals:
        a = sim.approvals[0]
        what = f"your {a.token.symbol}" if a.unlimited else a.token.human(a.amount)
        who = a.who[0].upper() + a.who[1:] if a.who else "Someone"
        return f"{who} gains the right to take {what} whenever they choose."
    outgoing = [c for c in sim.balance_changes if c.delta < 0]
    if outgoing:
        c = outgoing[0]
        where = (
            short(tx.to)
            if any(r.lower() == tx.to.lower() for r in sim.recent_addresses)
            else "an address you have not used before"
        )
        return f"{c.token.human(abs(c.delta))} goes to {where}."
    if sim.reverted:
        return "This fails and costs you the fee."
    return "No value moves and no permission is granted."


def explain(tx: Transaction, sim: Simulation) -> Explanation:
    findings = evaluate(tx, sim)
    severity = worst_severity(findings)
    return Explanation(
        verdict=VERDICTS[severity],
        severity=severity,
        summary=_summary(tx, sim, findings),
        now=_immediate(sim),
        later=_afterwards(sim),
        findings=findings,
    )
