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

## Verified backups, monitoring, and error diagnostics

On startup (before collection writes to an existing database) and then daily, the supervisor creates an online SQLite backup. This includes committed WAL data. It checks SQLite integrity, compresses the copy, restores the exact compressed archive in an isolated location, compares checksums and row metadata, then publishes `backups/latest.json`. Three generated local backup archives are retained; raw snapshot history is never pruned. Capacity checks reserve room for both uncompressed temporary copies and the archive. Low space or a backup failure is reported without deleting source history.

`GET /api/backup/latest` downloads the latest verified compressed SQLite backup; its checksum and row/time metadata appear under `backup` in `/api/history`. This archive contains public upstream weather/market payloads, source URLs, collection timestamps, and error codes only. It intentionally has no login because the app stores no user accounts, credentials, model submissions, or trade positions. Do not add private data to the snapshot table without first restricting this export endpoint.

The hourly GitHub monitor fails its workflow if collection has no full success within 45 minutes, collector state is unhealthy, fewer than 100 MB remain, or no restore-verified backup exists from the last 36 hours. Daily, it also downloads an off-site copy, verifies its SHA-256 and declared size, and retains the artifact for seven days. Archives exceeding 10 MB fail visibly instead of silently increasing the configured artifact-storage budget; review the limit and storage plan as history grows. Independent per-run collector artifacts are now gzip-compressed with their existing retention period.

GitHub Actions failures appear in the repository's Actions tab. Email notification delivery depends on the account's Actions notification settings and has not been independently verified. There is no configured SMS, Slack, or email webhook. No new paid notification or storage provider is activated. Actions usage remains subject to the account's existing allowances and billing settings. These checks are hourly, not an instant paging service.

Historical errors are grouped by source, stored error type, count, and first/last occurrence in `/api/history`. Pre-upgrade errors captured only an exception class, so their original HTTP status or TLS/timeout cause may be irrecoverable. Future curl failures record only a safe HTTP status and curl exit code, without proxy credentials, raw error output, or response bodies. Transient curl failures receive bounded retries. A later successful run does not erase historical errors.

### Restore without overwriting production

Download the archive and its manifest, compare its SHA-256, then run:

```sh
python3 scripts/backup.py --restore snapshots.sqlite.gz --destination restored/snapshots.sqlite
```

This checks database integrity and refuses an existing destination. Never restore directly over the collecting production database. A full production recovery requires stopping collection, preserving the old disk, and choosing a verified recovery point. A local backup on the same disk is not disaster recovery; retain and verify off-site artifacts as well.
