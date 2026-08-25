# Grafana

## Role

Grafana is the presentation layer for observability and validated AI results. It does not own incident truth, correlation state, or durable AI working memory.

## Datasource pattern

Grafana reads network logs through ClickHouse using two captured datasource identities required by the current dashboards.

The log-oriented path uses a semantic ClickHouse view rather than requiring the raw storage table to contain presentation-specific fields.

The semantic view exposes display-oriented fields such as:

- time -> normalized event timestamp
- level -> normalized severity/level
- body -> log message body
- context -> device identity such as hostname/source address/device label

This keeps display concerns separate from raw storage and replay contracts.

The collector rebuild artifacts preserve the current datasource names, UIDs, protocol choices, database/table mappings, and plugin version. Credentials remain operator-supplied through rendered provisioning rather than stored publicly.

## Grafana 13 dashboard resource contract

The current six dashboards are captured as native Grafana 13 unified-resource API documents using:

`dashboard.grafana.app/v2`

Captured dashboard files live under:

`components/collector/grafana/dashboards/`

Production API testing against Grafana 13.1.1 proved:

- GET returns dashboard resources whose `spec` exactly matches the captured repository resource
- POST to `/apis/dashboard.grafana.app/v2/namespaces/{namespace}/dashboards` is the supported create operation
- PUT to `/apis/dashboard.grafana.app/v2/namespaces/{namespace}/dashboards/{name}` is the supported full-replacement operation
- `dryRun=All` validates create/replace operations without persisting them
- dry-run creation did not create a resource
- dry-run replacement did not change existing resource versions

Validation checkpoints include:

- `GRAFANA_UNIFIED_RESOURCE_ROUND_TRIP=PASS`
- `GRAFANA_DRYRUN_RESTORE_PROOF=PASS`
- `GRAFANA_DASHBOARD_VERIFY=PASS`
- `GRAFANA_DASHBOARD_RESTORE_DRYRUN=PASS`
- `GRAFANA_DASHBOARD_LIVE_NONDESTRUCTIVE_TEST=PASS`

## Dashboard rebuild tooling

Published scripts:

- `components/collector/grafana/scripts/dashboard_api.py`
- `components/collector/grafana/scripts/restore-dashboards.py`
- `components/collector/grafana/scripts/verify-dashboards.py`

Restore behavior:

- server-owned metadata such as creation timestamps, generation, resource version, and server UID is not forced from the captured resource
- captured name, namespace, labels/annotations, `spec`, and required resource shape are preserved
- an existing exact-match dashboard is left unchanged
- replacement is refused unless explicitly enabled
- no delete operation is part of the rebuild flow
- post-write verification re-reads the API resource and confirms captured semantics

Direct writes to Grafana's SQLite database are not part of the rebuild contract.

## Runtime installer integration

Dashboard reconstruction is wired into the clean-machine collector runtime installer after normal Grafana HTTPS health and ClickHouse datasource provisioning are verified.

The installer:

- connects only to `https://127.0.0.1:443`
- authenticates with the operator-owned private Grafana administrator password file
- creates missing captured dashboards
- leaves exact matching dashboards unchanged
- deliberately does not pass `--replace`, so a divergent existing resource fails closed
- runs the independent verifier after restore
- uses Python `-B` for restore and verification so runtime execution does not create `__pycache__` artifacts in the repository

Clean-machine end-to-end execution remains part of the later collector rebuild validation gate.

## Administrator bootstrap

Secure administrator bootstrap is now wired into the clean-machine collector installer.

Grafana 13.1.1 uses:

`/usr/share/grafana/bin/grafana cli admin reset-admin-password --password-from-stdin`

The rebuild sequence:

1. requires an operator-owned private `GRAFANA_ADMIN_PASSWORD_FILE`
2. rejects empty, multiline, or group/world-accessible password files
3. creates a temporary systemd override for HTTP on `127.0.0.1:3000`
4. starts Grafana and verifies health/database readiness
5. confirms the only TCP/3000 listener is `127.0.0.1:3000`
6. stops Grafana
7. invokes the CLI as the `grafana` account from `/usr/share/grafana`
8. explicitly supplies `/etc/grafana/grafana.ini`
9. explicitly overrides the Grafana data path to `/var/lib/grafana`
10. resets administrator user ID 1 with the password supplied through stdin
11. runs SQLite `PRAGMA quick_check` and verifies database ownership
12. removes the temporary bootstrap override before the normal HTTPS start

The installer cleanup trap also stops temporary Grafana, removes the bootstrap override, and reloads systemd if a failure occurs while that override exists.

A non-destructive behavioral proof copied the live Grafana SQLite database to a temporary directory, changed the administrator ID only in that copy, and invoked the same CLI targeting mechanism. The temporary password hash changed and the copied database passed integrity checking. The synthetic user remained absent from the live database and the live administrator password hash remained unchanged.

Do not assume `grafana` or `grafana-cli` is on `PATH`; the Debian package service uses `/usr/share/grafana/bin/grafana`.

## HTTPS and certificate contract

The current collector presents Grafana over HTTPS on TCP/443 through a systemd override captured under `components/collector/grafana/systemd/`.

The rebuild contract preserves:

- HTTPS protocol
- public root URL rendered from operator-supplied environment identity
- certificate and private-key paths under `/etc/grafana/tls`
- current file ownership/mode requirements
- certificate watch interval
- Certbot renewal and deploy-hook behavior

Certificate/private-key material is never committed to the public repository.

## Drilldown behavior

The current dashboard design supports contextual drilldowns from summary panels into underlying device logs. Proven patterns include:

- BGP summary -> BGP logs for the selected device
- OSPF summary -> OSPF logs for the selected device
- Top Devices -> all logs for the selected device
- Severity summary -> logs for the clicked severity

Drilldowns preserve the dashboard time range.

For severity drilldowns, the clicked field value is used directly. A series-name variable is not used because it resolves to the query series identifier rather than the semantic severity value.

## NOC-view rule

The primary NOC dashboard should remain a high-signal operational view. It should not contain a permanent full raw-log panel.

Raw logs remain available through drilldowns when investigation requires them.

## AI presentation

The live `AI Incident Analysis` dashboard presents the stabilized item-30 result contract from `observability.ai_updates`. The separate editable `AI Incident Analysis - Enhanced` resource preserves that original as an immediate fallback and now presents deterministic lifecycle state from `observability.incident_updates` as the operational NOC queue.

Its default seven-day, one-minute-refresh view contains:

- total validated AI updates
- critical/high result count
- unique deterministic incident count
- hourly result volume
- severity and status distributions
- a newest-first 200-row detail table with timestamp, severity, status, title, explanation, occurrence count, tags, model, incident ID, and run ID

The enhanced resource has three summary counts and three medium-row, paginated, filterable operational tables:

- Active Events: unresolved non-interface incidents, independent of the time picker, with latest AI summary and deterministic fallback detail
- Interface Flaps: every unresolved interface incident, including a first adverse observation with zero recorded state changes, independent of the time picker
- Resolved Events: resolved incidents filtered by `resolved_at` and the selected time range

All three tables expose Device and Incident ID. Separate server-side text variables search Active, Flap, and Resolved rows across device/entity/category/protocol/title/incident identity; Active search also covers its displayed detail. A server-side severity variable filters Active and Resolved. Assigned-operator and AI-recommendation fields are intentionally absent. The top resolved statistic is labeled simply `Resolved`; its count still honors the selected `resolved_at` range.

Every query is a bounded `SELECT` through the existing read-only datasource and avoids exposing complete `raw_json` provenance. The permanent redacted verifier executes the original seven plus enhanced six panels through Grafana's datasource API and reports only frame/row counts. Active windows deliberately do not age out with the time picker; Resolved uses the selected resolution-time range.

The governing pattern remains:

1. deterministic incident/evidence state remains authoritative outside Grafana
2. deterministic lifecycle snapshots and validated AI result records are stored in separate ClickHouse tables
3. the enhanced dashboard presents the deterministic NOC queue; the original presents AI assessment history
4. operators retain drilldown access to the underlying raw observations

Grafana must not become the incident state database or a substitute for deterministic correlation.

Item-32 production validation passed create-only `dryRun=All`, exact live resource reread, unchanged exact verification of the four preexisting dashboards, and all seven live datasource queries. No existing dashboard was replaced.

Item-33 production validation passed distinct create/dry-run, exact six-resource reread, all fifteen live datasource queries, backward-compatible GX10/collector Device projection, private legacy mapping, and unchanged exact verification of the original dashboard. Only the distinct enhanced resource was replaced during refinement.

Item-34 production validation passed enhanced-only replacement dry-run, exact six-resource reread, all thirteen current live datasource queries, 804 latest lifecycle rows with complete Device identity, exclusive interface-flap presentation, and zero lifecycle records in `ai_updates`. The original dashboard remained byte-exact. See `docs/NOC_WORKFLOW.md` for queue semantics.

Item-35 production validation passed pre/post execution of all thirteen live datasource queries, `dryRun=All`, enhanced-only replacement, and exact reread of all six resources. The current active split is two non-interface Active Events and 34 Interface Flaps, with zero interface entities in Active Events. Neither current Active row has a stored AI summary, so both display the deterministic detail fallback. The resolved statistic is labeled `Resolved` while retaining its selected-range semantics, and the original dashboard remains byte-exact.

## Change discipline

When changing Grafana state:

- preserve stable datasource UIDs referenced by dashboards
- use the supported resource API for dashboard reconstruction
- use dry-run validation before destructive replacement where possible
- verify actual clicked field names for drilldown changes
- preserve time-range context
- test positive drilldown behavior end to end
- avoid modifying the raw storage schema solely for formatting convenience
- preserve verified working HTTPS/plugin/datasource behavior unless evidence justifies a change

The exact current Grafana integration task is tracked in `docs/CURRENT_STATE.md`.
