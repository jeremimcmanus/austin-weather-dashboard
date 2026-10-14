# Permanent hosting deployment

## Prepared deployment

The repository includes a Render Blueprint (`render.yaml`) for one **paid Starter web service** and a **1 GB persistent disk**. These are billable resources. Review the current price in Render before creating them; this repository does not authorize a purchase or contain billing credentials. No hosting service has been created merely by adding these files.

Deployment entry point: https://render.com/deploy?repo=https://github.com/jeremimcmanus/austin-weather-dashboard

Authorize Render to read this GitHub repository, then review the Blueprint's service and disk before deploying. Render supplies the actual public HTTPS address after creation; the final hostname must not be guessed. Account login, GitHub app authorization, and billing approval must be performed by the account owner. No API key or trading account is needed for this app.

## Runtime and collection

The digest-pinned official Node 22 Debian image already contains Python 3, curl, and CA certificates. The build installs no application packages. `scripts/production.py` supervises the Node HTTP process and starts an independent timer thread that collects every 900 seconds, immediately on startup and then regardless of page visits. It serializes collections and records source failures rather than silently substituting demo data. When the HTTP process exits, supervision exits so the hosting platform can restart the service.

`DATA_DIR=/var/data` is the retained disk. SQLite snapshots and collector status live there; keep this path mounted on the persistent disk. Redeploying or restarting with the same disk retains history. Deleting the disk or service, exhausting storage, suspending the account, or losing upstream access can interrupt collection; no availability or perpetual-retention guarantee is implied. The dashboard reports collector state, last successful full collection, run count, source errors, and a low-free-space warning. Review disk usage and service logs periodically. One instance is intended; do not run multiple collectors against the same volume.

Live records include NWS hourly forecasts and KAUS observations, Kalshi market rules/series metadata/order books, and daily revisits of the previous seven event dates for exchange-reported results and revisions. NWS CLI reports are comparison evidence only. Weather Company outcome ingestion and complete source/rule verification are not implemented.

The hourly GitHub Actions collector is a second, visitor-independent collection path once its workflow is on the default branch and Actions is enabled. It also runs on changes to its script/workflow and can be dispatched manually. Its separate per-run SQLite artifacts retain up to 90 days. They are not an indefinite backup of the Render disk. Download them before expiration. GitHub scheduling can be delayed or disabled and usage allowances apply.

## Verification after hosting authorization

1. Confirm the hosting build and `/healthz` succeed at the actual public HTTPS address. Health reports `tradingEnabled: false`; it does not certify collection or financial-model readiness.
2. Without opening the dashboard first, wait for the startup collection. Check `/api/history`: a real `lastSuccessAt`, stored rows, and source-specific errors distinguish healthy collection from merely running HTTP.
3. Open the UI and inspect live weather, series rules, contract quotes, and order-book depth. Confirm failed sources produce visible errors.
4. Restart/redeploy with the same disk. Confirm old snapshots remain and a subsequent collection creates a new run.
5. Confirm GitHub workflow results and artifacts separately. A pushed workflow alone does not prove its first scheduled run has executed.
6. Confirm all retrospective cases remain blocked and unknown model/calibration/settlement/fee evidence cannot produce a positive recommendation.

## Data and model limits

No automatic trading routes, account connection, or order execution exist. The review assumes hold-to-settlement, checks side-specific liquidity, and reports stress scenarios. User-supplied fee totals do not independently verify the current schedule. No validated model probabilities or real out-of-sample profitability results have been manufactured. The included evaluation tool requires genuinely archived predictions, appropriate holdout separation, and independently verified labels. Until these gates are satisfied, a positive trading recommendation must remain unavailable.

## Local production smoke test

```sh
docker build -t austin-weather-dashboard:v2 .
docker run --name austin-weather-test -p 10000:10000 \
  -v austin-weather-history:/var/data austin-weather-dashboard:v2
```

If developing directly, `DATA_DIR=/path/to/retained/storage PORT=3000 python3 scripts/production.py` starts the same supervisor. Development requires Node >=22, Python >=3.9 with timezone data, curl, and verified CA trust.

Local container validation uses the cloud machine’s provided CA trust bundle for its HTTPS interception proxy. That temporary trust injection is confined to the validation container; the deployed image retains the official base image’s default CA trust, and TLS verification remains enabled.
