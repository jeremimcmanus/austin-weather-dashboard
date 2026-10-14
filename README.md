# Austin Weather Desk

A read-only Austin daily-high research dashboard for Kalshi, using NWS Austin–Bergstrom (KAUS) observations and hourly forecasts alongside public `KXHIGHAUS` market quotes. No accounts, credentials, trading, or paid dependencies.

## Run

Requires Node.js 22+ and curl (TLS verification enabled).

```sh
npm start
# development with automatic server restart:
npm run dev
# validation:
npm test
```

The server binds port 3000 (override with `PORT`). Open it through your development environment's supported application access. Select **Illustrative demo** to explore the interface without upstream access. The default is live mode; source failures are visible and never silently replaced with sample data. Refresh manually for new quotes.

Required outbound HTTPS hosts: `api.weather.gov` and `api.elections.kalshi.com`. The backend uses curl so cloud HTTPS proxy configuration is honored. No dependency installation is needed.

## Design decisions and limits

- Contract rules come first. KAUS is the weather view's chosen station; verify each live market's actual station, date, thresholds, rounding, reporting window, and settlement publication before relying on it.
- An hourly forecast peak over the next 24 hours is not a forecast of the official daily maximum for a selected event. The chart is weather context and is intentionally not aligned to a contract as a settlement prediction.
- A latest observation is not the maximum observed so far. The collector retrieves NWS climate reports as comparison evidence; this app does not certify settlement outcomes.
- Display bid and ask separately. Spread is shown only for coherent quotes. Quotes exclude depth, fees, and slippage; prices are snapshots, not execution guarantees.
- No invented win probabilities, expected value, or buy/sell recommendations. Those require calibrated station-level forecast errors, date alignment, and proper settlement history.
- Demo data is fixed, illustrative, and prominently labeled. Network failures remain explicit; live NWS and Kalshi API access was validated during development.
- No automatic trading or account connection. Public market normalization is covered by fixture-based tests and live endpoints were exercised during development.

The best next research increment is verified Weather Company outcome ingestion and contract-to-station/date mapping, followed by backtesting a probabilistic model against historical settlement results. A point forecast alone does not justify a claimed trading edge.

## Independent collection and history

`scripts/collect.py` appends raw, timestamped NWS forecasts, latest observations, NWS climate reports (context only), Kalshi market rules, series metadata, and order books to `data/snapshots.sqlite`. Every response has its own receipt time; errors are recorded and cause a nonzero exit. Snapshots are not atomic across sources. Only public data is requested.

```sh
python3 scripts/collect.py
python3 -m unittest discover -s scripts -p 'test_*.py'
```

`.github/workflows/collect.yml` runs this independently of dashboard visitors hourly **once committed/pushed to the default branch and GitHub Actions is enabled**. Each run uploads a separate SQLite snapshot artifact with up to 90 days retention. Scheduling may be delayed, free allowances apply, and GitHub can disable inactive scheduled workflows. This is a practical starter archive, not permanent cloud storage or an availability guarantee. Download artifacts before expiration or move the same collector to a managed scheduler with durable object storage for long-term research. No workflow has been deployed by this local build. Local `data/` is ignored by Git.

**Live-source finding:** current `KXHIGHAUS` market rules and series metadata name **The Weather Company**, with `https://weather.com/kalshi` as the source. They reference Austin (CLIAUS). The dashboard displays the exchange-declared source and full per-contract API rules. The Weather Company outcome feed, contract PDF, station mapping, revision policy, and reporting-window interpretation have not been independently certified. NWS CLI reports are retained only as comparison evidence. Never use them as an automatic substitute for the declared source.

The liquidity inspector derives YES asks from NO bids, walks visible depth for the requested quantity, and refuses a full fill estimate when depth is insufficient. It accepts a **user-verified total fee**, rather than inventing the current exchange fee formula. Series fee type and multiplier are displayed separately. The live series currently reports `quadratic` and multiplier `1`; this alone is insufficient to verify the complete schedule.

## Holdout evaluation

`scripts/backtest.py` evaluates an externally prepared CSV of genuinely archived predictions and verified binary outcomes. Freeze the model and cutoff in advance. Fields: `event_id,prediction_at,event_close,settled_at,probability,outcome`. All timestamps require timezones. One independent prediction per event is required. It refuses post-close predictions, duplicate events, invalid probabilities, missing train/holdout data, and events straddling the split. The baseline is learned only from events settled before the cutoff.

```sh
python3 scripts/backtest.py verified-predictions.csv --cutoff 2026-10-15T00:00:00Z
```

No historical predictions or verified settlement labels have been fabricated. Therefore no real out-of-sample backtest has yet run and no trading edge is claimed. Historical provenance, selection bias, uncertainty, and fee-adjusted execution require further research. The tool reports Brier scores, not trading profits.

## Why this implementation differs from the initial Streamlit proposal

A small Node server and dependency-free browser UI keep source access server-side, make partial outages explicit, and support responsive quote/depth interaction without tying collection to page reruns. Streamlit would also work for a research prototype, but neither framework creates permanent hosting, durable history, or verified settlement data by itself. This repository is runnable locally; a public deployment and persistent scheduled collection are separate activation steps.

## Adversarial trade review

The **Evidence against the trade** panel assumes the market is efficient and the model may be wrong. Inspect a contract, choose BUY YES or BUY NO, enter a probability for that side and a timezone-qualified model issue timestamp, then supply quantity and total fees in the execution panel. The review uses visible complementary bid depth for the selected side, not the last price or quote midpoint as an execution price.

It reports the strongest identifiable objections: insufficient depth, a closed/unconfirmed market, missing or stale forecast/model/book timestamps, model predating the displayed forecast, missing fees, unverified settlement mapping and fee schedule, and absent independently reviewed calibration. The current app has no independent settlement/calibration/fee verification integration; those remain explicit blockers even if a model scenario looks attractive. Entering numbers does not verify evidence.

Three scenarios are separated:

1. Supplied model probability minus depth-weighted entry cost and entered total fees.
2. Model probability minus an explicit haircut, with an additional execution buffer.
3. A competing efficient-market hypothesis: probability capped at the coherent two-sided market midpoint (or the stressed model probability, whichever is lower), with the same costs. The midpoint is only a counter-hypothesis, never a calibrated probability or executable price. A negative result in this scenario does not prove the model wrong; it identifies the evidence burden for rejecting market efficiency.

Defaults of a 10-percentage-point haircut, 2¢ extra cost per contract, a one-minute maximum book receipt age, and two-hour model/forecast age are transparent review policy choices, not fitted confidence bounds. Source receipt time cannot establish exchange-side quote freshness. Costs assume holding to settlement and do not cover later liquidation or its fees. Model inputs are cleared when changing contracts; data/input changes invalidate the displayed review, and old book-based reviews expire automatically. No review executes orders, produces a recommendation, or establishes an edge.

The pure review calculations live in `public/review.js` and are covered by tests for YES/NO complement pricing, depth-weighted fills, fee reversal, conservative scenarios, stale/future timestamps, missing evidence, and missing two-sided markets.

## Retrospective regression evidence

The dashboard includes the supplied October 7–8 cases and their rejection reasons. The exact Austin contracts were subsequently recovered from the public API: `KXHIGHAUS-26OCT07-B91.5` and `KXHIGHAUS-26OCT08-B92.5`, both reported finalized YES. Their proposed NO positions therefore have zero settlement payout. Final outcomes are separate from decision-time evidence and do not establish historical fills, dollar P&L, or probability calibration. Los Angeles remains unresolved and Miami withdrawn. See [the adversarial review](docs/retrospective-review.md) and the preserved raw exchange records in `evidence/austin-finalized-markets.json`.

## Permanent deployment

A paid Render service with a persistent disk is configured in `render.yaml`; see [deployment and verification instructions](docs/deployment.md). The production supervisor collects every 15 minutes regardless of visits and reports health/history in the dashboard. Deployment still requires account authorization and approval of the service/disk charges. Local tests and a Git push do not establish a public deployment. Keep all unverified recommendation gates closed.
