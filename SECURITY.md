# Security

## What Plainsign is not

Plainsign does not hold keys, sign, or broadcast. It cannot move funds.
If you are ever asked for a seed phrase or a private key by anything
claiming to be Plainsign, it is not Plainsign.

## What it cannot promise

Plainsign explains what a transaction does according to the data it is
given. It can be wrong in three ways, and you should know all three:

1. **Missing data.** If contract source is unpublished or an address has
   no history, some checks stay silent. Silence is not a clean bill of
   health.
2. **Unknown patterns.** The rules cover documented attacks. A new
   technique will pass until a rule exists for it. One campaign already
   defeated every age-based check by sending funds to an address whose
   contract was deployed afterwards.
3. **Wrong inputs.** The reasoning is only as good as the simulation
   feeding it.

Treat a clean result as one input to your decision, not permission.

## Reporting a problem

Open an issue for a rule that misses something or fires wrongly, with the
transaction or incident it came from — a false alarm is a real bug here,
because it trains people to click through warnings.

For anything you believe should not be public, say so in the issue
without the details and a private channel will be arranged.
