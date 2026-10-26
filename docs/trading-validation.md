# Austin contract, execution, and probability validation

This pipeline produces research evidence. It does not execute orders. A positive model scenario cannot override missing verification.

## Authoritative evidence and findings

`evidence/official/` preserves the official GLOBALTEMPERATURE terms, the Kalshi fee PDF, the Weather Company portal, a portal response for October 25, 2026, and the developer fee-rounding/fixed-point documentation. `receipts.json` records retrieval times, official URLs, content hashes, and acquisition status. Acquisition does not itself establish semantic review. `evidence/trading-policy.json` binds reviewed facts to these document hashes and to exact contract rule versions or a strictly checked Austin rule grammar. Unexpected station, date, source, strike/operator, secondary-rule, payout, or document changes block approval.

Verified facts:

- The Weather Company portal maps Austin to ICAO **KAUS**, CLI ID **AUS**, and `America/Chicago`. The current exchange rules name Austin **CLIAUS**. The portal reports 92°F for both October 7 and October 8, matching the retrieved YES settlements for the two retrospective bins.
- GLOBALTEMPERATURE uses the **full precision reported by the source**. “Between” is inclusive; above/below are strict. Do not round an observation or source value to force a contract outcome.
- The general source hierarchy is TWC, NWS, then the relevant national service. The first official non-preliminary report matters, with contract-specific material-error review, timing, and fallback provisions. Post-expiration revisions do not automatically change payout. No data can lead to exchange-determined last-fair-price settlement, not an assumed binary outcome.
- The fee PDF effective July 7, 2026 gives the general direct-exchange taker coefficient **0.07**; current `KXHIGHAUS` metadata reports `quadratic` and multiplier **1**. Series and event fee-change endpoints are checked for overrides and imminent changes.
- The developer fee-rounding documentation specifies direct-member balance precision **$0.0001** and non-direct precision **$0.01**. Trade fees ceil to **$0.000001 per fill**. Balance rounding and capped rebates accumulate across an order. Fractional fills have a minimum quantity of **0.01 contracts**. The PDF whole-cent example table is not a universal rounding rule for all accounts.

Unresolved and blocking:

- The Austin domestic daily maximum's exact weather measurement window and DST/standard-time handling. The calendar date, trading close, and the portal's international midnight-to-midnight explanation do not establish that domestic window. The assumed civil-day forecast window is visible and unverified.
- The user account category and any brokerage charges. The engine implements the documented rounding mechanics and provides separate conservative exchange-fee bounds for direct/non-direct accounts. It does not infer account category or claim that an aggregated order book identifies the exact future fill sequence. Until account scope is confirmed, definitive cost approval remains blocked. Broker/funding/early-exit charges are excluded and not verified.

Use `python3 scripts/acquire_documents.py` to refresh receipts. An unexpected changed document hash invalidates its prior approval. Changes to policy facts require review of the actual authoritative evidence, not a client-side checkbox.

## Quantity-specific executable-price research

`GET /api/trading-validation/<ticker>?side=YES|NO&quantity=<integer>` fetches a fresh specific market, series metadata, and up to 100 depth levels. It derives asks from opposite-side bids, aggregates identical price levels, walks depth using Decimal arithmetic, records receipt time, checks the current market price grid, and rejects malformed/crossed/off-grid books. Insufficient visible depth never produces a complete entry estimate. Quotes are snapshots, not fill guarantees; receipt time cannot prove exchange-side freshness.

The endpoint audits rule identity, active status, $1 notional, source evidence, effective fee policy, prediction provenance, and data age. Fee calculations use a documented conservative upper bound: unrounded model fees plus at most one microdollar of trade-fee rounding and one balance-precision unit for every possible minimum-size fill; all rebates are ignored. With minimum fill quantity 0.01, there can be at most 100 fills per requested whole contract. This overestimates possible fees without pretending to know matching-order fragmentation. `feeCents` is explicitly a conservative upper bound, and `realizedFeeCents` remains null. Account-verified fee and cost paths add a precommitted extra execution-cost buffer. NO uses `1 - upperYes`, not `1 - lowerYes`. A trade must exceed the configured minimum edge under stressed probability and costs. A qualifying result is eligible for further review only; it is not an order or an automatic BUY signal.

The efficient-market hypothesis is tested through the paired out-of-sample market benchmark. It is not used to cap every probability at the midpoint by definition: that construction would make every ask-side edge negative regardless of evidence. The separate manual adversarial panel retains its midpoint counter-scenario as a research objection.

## Immutable prospective forecast ledger

The supervisor runs `scripts/research.py` after each successful source-collection pass. It uses only already-received NWS and market snapshots. The forecast must cover every hour of the complete explicitly assumed future event window (including 23/25-hour DST days), be fresh at capture, and leave at least six hours before the target day starts. No new forecast is generated for a past event.

Each record contains actual issue time, source issue/receipt times and snapshot IDs, target window, rule fingerprint, model/spec/implementation hash, event date, probability, and scenario envelope. Records are insert-only and unique by experiment and ticker/date, and each event family is inserted atomically. Evaluation checks raw forecast hashes, source timestamps, complete event-family coverage, and recomputed frozen-model probabilities and stress bounds. Quotes are requested **after** prediction insertion; missing, delayed, or unverified quotes cannot establish executable backtest profits.

The initial model is an **unfitted engineering prior**: discrete Gaussian probabilities over assumed source-reported integer Fahrenheit values, centered on the target-day NWS peak with sigma 4°F. This does not round a source value or verify that all future source reports have integer support. Stress calculations vary forecast bias by ±2°F, sigma by precommitted multipliers, source-value support between 0.1°F and 1°F, and add a five-percentage-point calibration margin. These are scenarios, not empirically established confidence bounds. A fractional official outcome outside the assumed support blocks evaluation; it is never rounded away.

`twc.daily` snapshots retain the Austin portion of official portal responses, source URL, receipt time, and a canonical full-response hash. Preliminary/wrong-station/nonfinite/wrong-date records cannot become labels. Conflicting official revisions and disagreement between the numeric source and exchange result block evaluation. Blank source publication times are not invented: data is known no earlier than its captured receipt time.

## Training and untouched holdout

Research spec, model parameters, implementation hash, experiment freeze time, and the rule/fee/risk policy fingerprint, and the first eligible future target date are persisted before outcomes. The holdout waits for an eligible first forecast; a deployment late in the day does not invent an unavailable first test day. Changes create a new experiment; they cannot overwrite earlier predictions. Already-inspected October 7/8 cases and retrospective reconstructions are not untouched prospective tests.

`python3 scripts/research.py train --data-dir <directory>` requires at least **60 independent verified event days**, archived forecast provenance, numeric official outcomes, and source/outcome knowledge strictly before model freeze. It fits bias and sigma from actual source-value forecast errors, with a fixed sigma floor of 1°F. It refuses to replace an existing frozen fitted-model artifact. No midpoint of a winning interval is invented as an actual temperature.

A new fitted model starts a **separate 30-calendar-event-day future holdout**, beginning with its first eligible future prediction. Scores remain hidden until the entire fixed window has complete eligible outcomes. Missing data is not silently dropped to get a passing test. Related contracts are clustered by event day. The precommitted strategy takes at most one position per day, chooses by maximum stressed edge with fixed tie-breaking, includes no-trade days, and requires complete post-prediction quotes and verified fees.

Evaluation reports Brier score against paired market midpoint probabilities, bucket calibration uncertainty, and stressed fee-adjusted paper profit. Event-day bootstrap confidence checks require positive lower bounds on both benchmark improvement and paper profitability, and calibration uncertainty below the fixed tolerance. Changing selection rules or tuning after seeing the holdout requires a new future test. Sample minima and bootstrap checks do not guarantee future performance. Validation expires and source/rule revisions can revoke it.

**Current state:** only a few days of forecast history exist; the prior is not fitted, no 60-day verified training set exists, and no complete untouched prospective holdout has run. `calibrationVerified` remains false. No genuine trading edge or positive recommendation is established.

## Operator commands

```sh
python3 scripts/research.py run --data-dir /var/data
python3 scripts/research.py status --data-dir /var/data
python3 scripts/research.py train --data-dir /var/data
python3 -m unittest discover -s scripts -p 'test_*.py'
```

The legacy CSV scoring CLI remains an exploratory tool; it cannot promote a model or change server verification state. Hourly collector/model source freshness is separate from publication time; a newer live NWS issue invalidates a model based on an older forecast even inside the two-hour age limit. Research tables are in the same SQLite database and are included in its online backups. No account credentials, submitted orders, or private positions are stored.

## Questions requiring authoritative clarification

1. For KXHIGHAUS/CLIAUS domestic daily maxima, what exact start/end instants define the named date, including DST? Does this match the source's official climate-report window or a civil calendar day?
2. Does the user trade as a direct Kalshi member or through a broker/FCM, and what additional brokerage charges apply? The public developer documentation now resolves the general balance-precision/rounding mechanics; no account credentials are needed to identify this category.

Do not fill these gaps with a forecast-provider convention or a remembered fee formula.
