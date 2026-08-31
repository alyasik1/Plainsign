"""Builds the public page from the engine itself.

Nothing on the page is written by hand. Every verdict, sentence and
flag below is produced by the same code that runs in the CLI, so the
page cannot drift away from what the tool actually says.

    python build_page.py > docs/index.html
"""

from __future__ import annotations

import html

from plainsign.cases import CASES
from plainsign.explain import explain

CSS = """
:root {
  --fog: #d9dedc;
  --paper: #fbfcfb;
  --ink: #101519;
  --wallet: #171c21;
  --wallet-line: #2b3339;
  --alarm: #a8271c;
  --caution: #7e5f09;
  --calm: #2c5a4a;
  --hair: #97a29e;
  --quiet: #5c6763;
}

* { box-sizing: border-box; }

html { -webkit-text-size-adjust: 100%; }

body {
  margin: 0;
  background: var(--fog);
  color: var(--ink);
  font-family: Newsreader, Georgia, serif;
  font-size: 18px;
  line-height: 1.55;
}

.wrap { max-width: 1080px; margin: 0 auto; padding: 0 24px; }

h1, h2, h3, .label, .verdict, .btn {
  font-family: "Bricolage Grotesque", "Helvetica Neue", Arial, sans-serif;
}

.label {
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--quiet);
  font-weight: 600;
}

/* ---- masthead ---- */

.masthead { padding: 88px 0 64px; }

.masthead h1 {
  font-size: clamp(46px, 8.5vw, 104px);
  font-weight: 800;
  line-height: 0.92;
  letter-spacing: -0.035em;
  margin: 0 0 28px;
}

.masthead h1 em {
  font-family: Newsreader, Georgia, serif;
  font-style: italic;
  font-weight: 400;
  letter-spacing: -0.01em;
}

.thesis {
  font-size: clamp(20px, 2.6vw, 27px);
  line-height: 1.4;
  max-width: 25ch;
  margin: 0 0 36px;
}

.masthead p.sub { max-width: 56ch; color: var(--quiet); margin: 0 0 10px; }

hr.rule { border: 0; border-top: 1px solid var(--hair); margin: 0; }

/* ---- the pair ---- */

.case { padding: 64px 0; border-top: 1px solid var(--hair); }

.case-head { display: flex; flex-wrap: wrap; gap: 8px 20px; align-items: baseline; margin-bottom: 28px; }
.case-head h2 { font-size: 26px; font-weight: 700; letter-spacing: -0.02em; margin: 0; }
.case-head .pattern { color: var(--quiet); font-size: 15px; font-style: italic; }

.source { font-size: 14.5px; color: var(--quiet); margin: -14px 0 24px; max-width: 78ch; }
.source .label { margin-right: 6px; }
.unknown { display: block; margin-top: 4px; font-style: italic; }

.pair { display: grid; grid-template-columns: 1fr 1.25fr; gap: 0; align-items: start; }

.side { padding: 26px; }
.side > .label { display: block; margin-bottom: 16px; }

.shows { background: var(--wallet); color: #e8edf0; border-radius: 14px 0 0 14px; }
.shows .label { color: #7d8b93; }

.dialog-app {
  font-family: "JetBrains Mono", ui-monospace, monospace;
  font-size: 11px;
  color: #7d8b93;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--wallet-line);
  margin-bottom: 20px;
}

.dialog-intent {
  font-family: "Bricolage Grotesque", sans-serif;
  font-size: 23px;
  font-weight: 600;
  line-height: 1.25;
  margin-bottom: 18px;
}

.dialog-meta {
  font-family: "JetBrains Mono", ui-monospace, monospace;
  font-size: 11.5px;
  line-height: 1.9;
  color: #93a1a9;
  word-break: break-all;
  margin-bottom: 24px;
}

.dialog-meta span { color: #5f6d75; }

.btn {
  display: block;
  text-align: center;
  background: #3b6ea8;
  color: #fff;
  border-radius: 8px;
  padding: 13px;
  font-weight: 600;
  font-size: 15px;
}

.does { background: var(--paper); border-radius: 0 14px 14px 0; }

.verdict {
  font-size: 25px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0 0 22px;
  padding-left: 14px;
  border-left: 4px solid var(--calm);
}

.does[data-severity="critical"] .verdict { border-left-color: var(--alarm); color: var(--alarm); }
.does[data-severity="warning"] .verdict { border-left-color: var(--caution); color: var(--caution); }

.block { margin-bottom: 22px; }
.block .label { display: block; margin-bottom: 7px; }
.block ul { margin: 0; padding-left: 18px; }
.block li { margin-bottom: 5px; }

.finding { border-top: 1px solid #e2e6e4; padding-top: 14px; margin-top: 14px; }
.finding h3 {
  font-size: 16px;
  font-weight: 700;
  margin: 0 0 5px;
  display: flex;
  gap: 9px;
  align-items: baseline;
}
.finding p { margin: 0 0 8px; font-size: 16.5px; }
.summary { font-size: 19px; margin: -12px 0 22px; color: var(--quiet); }
.todo-list { border-top: 2px solid var(--ink); margin-top: 22px; padding-top: 14px; }
.todo-list ol { margin: 8px 0 0; padding-left: 20px; font-size: 16.5px; }
.todo-list li { margin-bottom: 6px; }
.finding .todo { color: var(--calm); font-size: 16px; }
.finding .todo b { font-weight: 400; font-style: italic; }

.dot { width: 8px; height: 8px; border-radius: 50%; flex: none; transform: translateY(-1px); }
.sev-critical { background: var(--alarm); }
.sev-warning { background: var(--caution); }
.sev-note { background: var(--hair); }

/* ---- close ---- */

.close { padding: 72px 0 96px; border-top: 1px solid var(--hair); }
.close h2 { font-size: 30px; letter-spacing: -0.02em; margin: 0 0 18px; }
.close p { max-width: 58ch; margin: 0 0 14px; }
.close .label { display: block; margin-bottom: 26px; }
.foot { color: var(--quiet); font-size: 15px; margin-top: 34px; }

@media (max-width: 800px) {
  body { font-size: 17px; }
  .masthead { padding: 56px 0 40px; }
  .pair { grid-template-columns: 1fr; }
  .shows { border-radius: 14px 14px 0 0; }
  .does { border-radius: 0 0 14px 14px; }
  .case { padding: 44px 0; }
}

.reveal { opacity: 0; transform: translateY(14px); transition: opacity .6s ease, transform .6s ease; }
.reveal.seen { opacity: 1; transform: none; }

@media (prefers-reduced-motion: reduce) {
  .reveal { opacity: 1; transform: none; transition: none; }
}
"""

JS = """
const io = new IntersectionObserver((entries) => {
  entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('seen'); io.unobserve(e.target); } });
}, { threshold: 0.15 });
document.querySelectorAll('.reveal').forEach(el => io.observe(el));
"""


def esc(text: str) -> str:
    return html.escape(str(text))


def wallet_card(case) -> str:
    tx = case.tx
    kind = "Signature request" if tx.offchain_signature else "Transaction request"
    fee = "No network fee" if tx.offchain_signature else "Network fee applies"
    return f"""
    <div class="side shows">
      <span class="label">What your wallet shows</span>
      <div class="dialog-app">{esc(kind)} · {esc(tx.chain)}</div>
      <div class="dialog-intent">{esc(case.shown)}</div>
      <div class="dialog-meta">
        <span>To</span> {esc(tx.to)}<br>
        <span>Function</span> {esc(tx.function or "—")}<br>
        <span>Fee</span> {esc(fee)}
      </div>
      <div class="btn">Confirm</div>
    </div>"""


def reading_card(case) -> str:
    result = explain(case.tx, case.sim)
    parts = [f'<div class="side does" data-severity="{result.severity}">']
    parts.append('<span class="label">What it actually does</span>')
    parts.append(f'<p class="verdict">{esc(result.verdict)}</p>')
    if result.summary:
        parts.append(f'<p class="summary">{esc(result.summary)}</p>')

    now = result.now or ["Nothing leaves your wallet."]
    parts.append('<div class="block"><span class="label">Immediately</span><ul>')
    parts += [f"<li>{esc(line)}</li>" for line in now]
    parts.append("</ul></div>")

    if result.later:
        parts.append('<div class="block"><span class="label">Afterwards</span><ul>')
        parts += [f"<li>{esc(line)}</li>" for line in result.later]
        parts.append("</ul></div>")

    for f in result.findings:
        parts.append('<div class="finding">')
        parts.append(
            f'<h3><span class="dot sev-{f.severity}"></span>{esc(f.title)}</h3>'
        )
        parts.append(f"<p>{esc(f.detail)}</p>")
        if f.action:
            parts.append(f'<p class="todo"><b>What to do:</b> {esc(f.action)}</p>')
        parts.append("</div>")

    if result.actions:
        parts.append('<div class="todo-list"><span class="label">What to do</span><ol>')
        parts += [f"<li>{esc(a)}</li>" for a in result.actions]
        parts.append("</ol></div>")

    parts.append("</div>")
    return "\n".join(parts)


def source_line(case) -> str:
    if not case.source:
        return ""
    unknown = ""
    if case.unknowns:
        items = " ".join(esc(u) for u in case.unknowns)
        unknown = f' <span class="unknown">Not published, so not modelled: {items}</span>'
    return f'<p class="source"><span class="label">Source</span> {esc(case.source)}.{unknown}</p>'


def build() -> str:
    cases = "\n".join(
        f"""<section class="case">
      <div class="case-head">
        <h2>{esc(c.name)}</h2>
        <span class="pattern">{esc(c.pattern)}</span>
      </div>
      {source_line(c)}
      <div class="pair reveal">{wallet_card(c)}{reading_card(c)}</div>
    </section>"""
        for c in CASES
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Plainsign — read before you sign</title>
<meta name="description" content="Plainsign reads a transaction before you approve it and tells you, in plain language, what it will actually do.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400..800&family=Newsreader:ital,opsz,wght@0,6..72,300..700;1,6..72,300..500&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<header class="masthead wrap">
  <span class="label">Plainsign</span>
  <h1>Read <em>before</em><br>you sign.</h1>
  <p class="thesis">Your wallet shows you a sentence. The transaction is something else.</p>
  <p class="sub">Plainsign simulates a transaction before you approve it and says what it does in words you already know: what leaves your wallet now, what someone can take later, and who ends up in control.</p>
  <p class="sub">It never holds keys, never signs, never sends. It cannot move your money.</p>
</header>

<div class="wrap">
{cases}

<section class="close">
  <span class="label">Reconstructed from public post-mortems</span>
  <h2>Every reading above came out of the tool.</h2>
  <p>Each case is rebuilt from published incident analysis, with the source named. Where a detail was never made public, it is left out rather than invented. The page is generated by the same code that runs in the command line, so nothing here is a mock-up written to look convincing.</p>
  <p>Running the engine against these cases changed it. Two rules exist only because real incidents defeated the ones written first: wallets in the permit drains displayed no claim at all rather than a false one, and one campaign sends funds to an address whose contract is deployed afterwards, so every check asking how old a contract is stayed silent.</p>
  <p>Still missing: decoding a transaction from raw data, and simulating it. Until those land, Plainsign reasons correctly about effects that something else has to supply.</p>
  <p class="foot">Free and open source under the MIT licence. No token, no account, no tracking. Plainsign never holds keys, never signs and never broadcasts.</p>
  <p class="foot">A clean result is one input to your decision, not permission. Where data is missing, checks stay silent — and silence is not a clean bill of health.</p>
</section>
</div>
<script>{JS}</script>
</body>
</html>
"""


if __name__ == "__main__":
    print(build())
