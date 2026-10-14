# Retrospective adversarial review: October 7–8, 2026

Decision evidence was supplied by the user and has not been independently authenticated. On October 14 the public Kalshi API returned finalized Austin records, retained in `evidence/austin-finalized-markets.json`. Retrieved final records are not original quote snapshots or proof of what was knowable at the decision. No model probability, fee, fill, or source outcome has been fabricated.

| Candidate | Strongest contrary evidence | Verdict |
| --- | --- | --- |
| Austin Oct 8, NO 92–93°F | Exact market `KXHIGHAUS-26OCT08-B92.5` is reported finalized YES, making NO payout zero. A 90°F forecast stressed by +2°F already touches the losing band. A later 91.4°F observation cannot establish the official daily high. | Not substantiated prospectively; would have lost if bought and held to settlement. |
| Austin Oct 7, NO 91–92°F | Exact market `KXHIGHAUS-26OCT07-B91.5` is reported finalized YES, making NO payout zero. The reported 87–88°F forecast with a ±2°F stress tops out at 90°F, missing the settlement band: this particular stress bound did not cover the realized downside. | Not substantiated prospectively; would have lost if bought and held to settlement. |
| Los Angeles Oct 7, YES 91°F+ | Exact contract, station, settlement source, forecast archive, and executable price are unresolved. The 60–65% estimate has no independent calibration. | Not substantiated. |
| Miami Oct 7, YES measurable rain | Candidate was withdrawn. Station/gauge, accumulation window, trace treatment, measurable threshold, and source interpretation remain unresolved. An 88–92% estimate for an undefined event is not useful pricing evidence. | Keep withdrawn. |

The Austin records returned by the API name The Weather Company and Austin (CLIAUS), with expiry/close timestamps of October 8 and 9 at 06:00 UTC respectively. Exact underlying publication, station mapping, original rule version, rounding, and revisions have not been independently verified. A market result is evidence of exchange settlement, not direct verification of its underlying weather measurement. Two losing selections alone cannot establish statistical miscalibration.

## Executable liquidity, costs, and probability

No decision-time order book or contract quantity was supplied for any candidate. Current/final quotes for expired markets cannot reconstruct original execution. The October 7 $150–$175 allocation is a budget, not a count of contracts.

October 7's nominal arithmetic is 65–75% minus a 34–40¢ indicative NO cost, or 25–41¢ gross expected value per contract. This is conditional on unverified inputs, excludes costs, and is not an established edge. October 8's 66% YES indication cannot be mechanically converted to a 34¢ executable NO ask unless it was a same-time executable YES bid with enough size. No fee-adjusted or conservative edge can be established for either record. The proposed NO positions have zero settlement payout according to the retrieved records, so a filled position held to settlement would lose its entry expenditure, plus applicable costs; actual dollar P&L is unknown.

A ±2°F perturbation is a sensitivity test, not a confidence interval or calibrated probability bound. The October 7 outcome demonstrates why passing that limited stress alone is inadequate. Use empirical forecast-error tails by lead time, season, station, and weather regime, plus settlement-source uncertainty. Under the efficient-market counter-hypothesis, the cost of crossing the spread, fees, and adverse fills weighs against any unproven model advantage.

## Calibration objections

- The 34 paired days split into 29 Weather Company and 5 NWS labels. Explain the historical contract source and any rule changes day by day before pooling those outcomes.
- Twenty training plus nine holdout days accounts for 29 days, leaving five unexplained. This may be a legitimate exclusion, but the selection criteria and target must be recorded before interpreting scores.
- Reported log loss 0.258 → 0.099 and Brier score 0.0178 → 0.0033 have not been reproduced from raw predictions and labels. Settlement-source calibration does not validate either trade's event probability.
- Nine holdout days are insufficient to establish robust trading profitability. Examine the baseline, class imbalance, correlated threshold rows, calibration by lead time, uncertainty, model selection, and repeated use of the holdout.
- The August 9–October 7 window must not leak October 7's eventual outcome into the October 7 forecast/model. It can inform an October 8 fit only if the relevant data was published before that model was issued.

## Regression contract

Austin October 7 and 8 are now rejection fixtures. Exact tickers and retrieved settlement outcomes are kept separate from user-supplied decision evidence. Missing quantities remain null, budgets stay budgets, forecast reference times do not become issue times, and probability ranges do not become synthetic point estimates. No retrospective case can produce a BUY signal or an invented edge. Los Angeles remains unresolved; Miami remains withdrawn.

New trades require an independently reviewed contract identity/rule mapping, timestamped forecast and model artifacts, genuinely out-of-sample calibration, fresh quantity-specific order-book evidence, verified applicable fees, and an empirically justified downside scenario. Even complete inputs only support further review, not an automatic recommendation.
