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
- captured name, namespace, `spec`, and required resource shape are preserved
- server/account-owned annotations, labels, UIDs, generations, timestamps, and status are rejected from repository captures and stripped from restore payloads
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

Clean-machine end-to-end execution remains `WAIVED BY OPERATOR` and
empirically unverified; this repository procedure is not evidence that the
collector rebuild has already been executed on disposable hardware.

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

## NOC least-privilege access

The working deployment has a dedicated Grafana organization for NOC Viewer access. It contains only copies of `NOC View` and `AI Incident Analysis - Enhanced` plus the two datasource definitions those dashboards require. The datasource copies retain their stable UIDs and use the existing read-only ClickHouse identity. The main organization and its six captured dashboards remain unchanged.

The NOC account is a Viewer and belongs only to that organization. `NOC View` is its home dashboard and both approved dashboards are starred. Explicit dashboard View grants are retained, persistent dashboard creation/save is denied, and a dashboard outside the NOC inventory returns not found.

Grafana OSS normally withholds Explore from Viewers. The working deployment enables `[users] viewers_can_edit = true` through a reversible systemd drop-in. This permits Viewer Explore and temporary panel editing but does not permit dashboard saves. Because Viewer Explore can query any datasource available to its organization, the separate organization contains only the two read-only datasource copies. The setting is global to future Viewer accounts, so any additional Viewer must be placed in a deliberately scoped organization.

Grafana OSS does not provide a per-user custom navigation role. The Viewer role hides administration, connection management, and persistent editing, but an exact left-menu allowlist of only Home, Bookmarks, Starred, Dashboards, and Explore is not enforceable in this edition; other standard Viewer-accessible product sections may remain visible. Exact custom navigation/RBAC would require an edition or customization that supports it.

### NOC reconstruction input contract

Perform this procedure on the collector only after the main Grafana installer
and its six-dashboard verifier pass. The operator supplies these values outside
the checkout:

- a server-administrator login and a one-line password file mode `0600` or tighter
- a new, dedicated NOC login, display name, email address, and
  separate one-line password file mode `0600` or tighter
- the private collector-side ClickHouse host value and the existing read-only
  Grafana-reader password file
- the selected NOC organization name
- an empty private staging directory such as
  `/operator/private/noc-dashboard-stage`

The password files, rendered datasource requests, API responses, backups, and
staged NOC captures are private inputs. Keep them outside Git, never pass a
password as a command argument, never print an authorization header, and delete
the private staging material when verification is complete. API clients must
connect through `https://127.0.0.1:443`; the server-administrator endpoints use
Basic authentication loaded from the private file in process memory.

Before mutation, require `GET /api/health` success, record the main
organization's six dashboard `spec` hashes, and take a consistent private
SQLite backup with the SQLite `.backup` operation. Run `PRAGMA quick_check` on
the backup, record its mode/owner, and save the current Grafana systemd drop-in
inventory. A full API response may contain server/account identity and therefore
must not be copied into this repository.

### Exact organization and account sequence

Use these server-administrator requests. Stop on any unexpected status or
pre-existing resource; do not silently adopt or alter an unrelated account or
organization.

1. Look up the organization with `GET /api/orgs/name/{url-encoded-name}`. If it
   is absent, create it with `POST /api/orgs` and payload
   `{"name":"<NOC_ORGANIZATION_NAME>"}`. Record whether this run created it and
   the returned numeric organization ID. If creation is forbidden, stop rather
   than loosening global settings ad hoc.
2. Ensure the server administrator can configure the new organization with
   `POST /api/orgs/{orgId}/users` and payload
   `{"loginOrEmail":"<SERVER_ADMIN_LOGIN>","role":"Admin"}`. A pre-existing
   membership must already be Admin.
3. Look up the dedicated login. If absent, create it with
   `POST /api/admin/users` and this shape; the password value is read from the
   private file only while assembling the in-memory request:

   ```json
   {
     "name": "<NOC_DISPLAY_NAME>",
     "email": "<NOC_EMAIL>",
     "login": "<NOC_LOGIN>",
     "password": "<NOC_PASSWORD_FROM_PRIVATE_FILE>",
     "OrgId": 12345
   }
   ```

   Here `12345` is a documentation placeholder; the actual request value is the
   numeric organization ID returned by Grafana, encoded as a JSON integer.
4. Ensure membership with `POST /api/orgs/{orgId}/users` and payload
   `{"loginOrEmail":"<NOC_LOGIN>","role":"Viewer"}`. Verify with
   `GET /api/users/{userId}/orgs` that this dedicated user belongs to exactly
   the NOC organization as Viewer. If an existing login belongs anywhere else,
   fail closed; do not remove or repurpose it automatically.

Admin-only endpoints above use server-administrator Basic authentication.
Every organization-scoped legacy request below includes
`X-Grafana-Org-Id: <NOC_ORG_ID>`. Native resource requests instead use the
explicit namespace `org-<NOC_ORG_ID>`; never rely on the administrator's
currently selected organization.

### Exact datasource and dashboard sequence

Create exactly two datasource resources. For each entry in
`components/collector/grafana/provisioning/datasources/clickhouse.yaml.in`, send
`POST /api/datasources` with the entry's exact `name`, `uid`, `type`, `access`,
`isDefault`, `basicAuth`, `withCredentials`, `editable`, and `jsonData` object.
Replace only `jsonData.host` with the private collector-side value, and add
`secureJsonData` with this in-memory shape:

```json
{"password":"<GRAFANA_READER_PASSWORD_FROM_PRIVATE_FILE>"}
```

If `GET /api/datasources/uid/{uid}` already succeeds, compare every public field
to the template and require `secureJsonFields.password` to be configured; fail
on divergence rather than overwriting it. For each datasource require
`GET /api/datasources/uid/{uid}/health` success. The final inventory must contain
only UIDs `efvaztlrk8ow0a` and `bfvik20ilwoaof`.

Build the two organization-scoped dashboard resources in the private staging
directory:

```text
python3 -B components/collector/grafana/scripts/build-noc-organization-captures.py \
  --org-id <NOC_ORG_ID> \
  --output-dir /operator/private/noc-dashboard-stage
```

The helper accepts only an organization ID greater than one, copies only
`noc-view.json` and `ai-incident-analysis-enhanced.json`, changes their namespace
to `org-<NOC_ORG_ID>`, rewrites only explicit `orgId=1` drilldown parameters,
strips server-owned metadata/status, refuses repository-local output, and writes
private mode-`0600` files. It does not contact Grafana.

Use the existing guarded resource client first with `--dry-run`, then without
it only after both dry-run responses match. The two-resource directory requires
`--expected-count 2`:

```text
python3 -B components/collector/grafana/scripts/restore-dashboards.py \
  --dashboard-dir /operator/private/noc-dashboard-stage \
  --expected-count 2 \
  --username <SERVER_ADMIN_LOGIN> \
  --password-file <GRAFANA_ADMIN_PASSWORD_FILE> \
  --dry-run
```

Repeat without `--dry-run` to create missing resources. Do not use `--replace`
during reconstruction; an existing divergent NOC resource is a stop condition.
The two stable dashboard UIDs are `ad9vtst` and
`ai-incident-analysis-enhanced`.

For each dashboard, snapshot `GET /api/dashboards/uid/{uid}/permissions`, then
set the isolated default role with `POST /api/dashboards/uid/{uid}/permissions`
and exact payload:

```json
{"items":[{"role":"Viewer","permission":1}]}
```

This endpoint replaces omitted permissions, so use it only for a newly created,
isolated NOC dashboard and retain the private pre-change response for rollback.

### Explore, preferences, and playlist

Install a root-owned mode-`0644` systemd drop-in for `grafana-server.service`
containing only:

```ini
[Service]
Environment=GF_USERS_VIEWERS_CAN_EDIT=true
```

Validate the unit, reload systemd, restart Grafana through the protected service
path, and require HTTPS health before continuing. This is the global OSS
compatibility setting that gives Viewer accounts Explore and temporary editing;
organization isolation and read-only datasource credentials remain the actual
data boundary.

Authenticate as the NOC user for user-owned requests. Set the home page with
`PUT /api/user/preferences` and payload
`{"homeDashboardUID":"ad9vtst"}`. Star both dashboards with
`POST /api/user/stars/dashboard/uid/ad9vtst` and
`POST /api/user/stars/dashboard/uid/ai-incident-analysis-enhanced`.

Create the rotation as the NOC organization administrator, using
`POST /apis/playlist.grafana.app/v1/namespaces/org-<NOC_ORG_ID>/playlists`:

```json
{
  "kind": "Playlist",
  "apiVersion": "playlist.grafana.app/v1",
  "metadata": {"name": "noc-rotation"},
  "spec": {
    "title": "NOC Rotation",
    "interval": "1m",
    "items": [
      {"type": "dashboard_by_uid", "value": "ad9vtst"},
      {"type": "dashboard_by_uid", "value": "ai-incident-analysis-enhanced"}
    ]
  }
}
```

If the stable resource already exists, require an exact `spec` match and leave
it unchanged. The Viewer starts it through
`/playlists/play/noc-rotation?autofitpanels=true`; kiosk mode is an optional
playback URL flag, not stored playlist state.

### Reconstruction verification and rollback

Verification is independent of the creation requests:

1. run `verify-dashboards.py` against the private staging directory with
   `--expected-count 2`
2. authenticate as the NOC Viewer and run
   `verify-ai-dashboard-queries.py` once for each staged dashboard; it executes
   every panel query and every nonempty named or indexed one-click drilldown and
   emits only frame/row counts
3. require NOC-user API inventory of exactly two dashboards, two datasources,
   one playlist, two stars, the NOC home UID, and only one organization membership
4. require Viewer Explore and playlist read/start success, dashboard save,
   datasource mutation, playlist creation, and non-NOC dashboard lookup denial
5. recompute the main six dashboard `spec` hashes and require exact pre-change
   equality; also rerun the normal six-dashboard verifier

The two scoped dashboard/query checks are:

```text
python3 -B components/collector/grafana/scripts/verify-dashboards.py \
  --dashboard-dir /operator/private/noc-dashboard-stage \
  --expected-count 2 \
  --username <NOC_LOGIN> \
  --password-file <NOC_PASSWORD_FILE>

python3 -B components/collector/grafana/scripts/verify-ai-dashboard-queries.py \
  --dashboard /operator/private/noc-dashboard-stage/noc-view.json \
  --dashboard /operator/private/noc-dashboard-stage/ai-incident-analysis-enhanced.json \
  --username <NOC_LOGIN> \
  --password-file <NOC_PASSWORD_FILE>
```

On partial failure, first resolve any timeout with a read-after-write GET. Delete
only resources recorded as created by this run, in reverse order: playlist,
dashboards, datasources, dedicated user, then organization. Restore a changed
permission document or systemd drop-in from its private pre-change copy, reload,
restart, and recheck health. Never delete or replace a pre-existing divergent
resource. If API rollback cannot restore a database-consistent state, stop
Grafana and restore the verified SQLite backup only with explicit operator
approval; do not perform a live database overwrite.

Account passwords, datasource credentials, rendered payloads, numeric runtime
organization IDs, and server-returned metadata remain operator-owned private
inputs. Commit only redacted PASS/FAIL markers and canonical dashboard `spec`
hashes after reviewing whether those hashes disclose environment-derived state.

## NOC rotation playlist

The working NOC organization contains one playlist titled `NOC Rotation`. It uses stable dashboard UIDs rather than deprecated internal dashboard IDs and cycles in this exact order:

1. `NOC View`
2. `AI Incident Analysis - Enhanced`

The stored playlist interval is one minute. Auto-fit panels is a playback mode carried by the start route (`autofitpanels=true`), not part of the playlist resource specification. The NOC Viewer can read and start the playlist through that route; an attempted playlist creation is denied. The main organization contains no playlist.

`NOC View` remains the NOC account's login home. Grafana user/organization home preferences accept a dashboard UID, not a playlist UID. For automatic wallboard behavior, open or bookmark the playlist's shared auto-fit start link after login; select kiosk mode as well only when menus and navigation should be hidden.

Playlist dashboard copies are separate organization resources. If either approved NOC dashboard is deliberately changed later, verify the NOC copy before continuing to use the rotation.

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
- Interface Flaps: device/interface pairs with at least 10 exact NX-OS interface-down transitions in the rolling preceding 60 minutes, independent of the time picker; rows leave automatically below threshold
- Resolved Events: resolved non-interface incidents filtered by `resolved_at` and the selected time range

Active and Resolved expose Device and Incident ID. Interface Flaps exposes Device, Interface, rolling count, and first/last transition within the current hour. Separate server-side text variables search Active, Flap, and Resolved rows; the flap search is limited to device/interface while Active search also covers its displayed detail. A server-side severity variable filters Active and Resolved. Assigned-operator and AI-recommendation fields are intentionally absent. The top resolved statistic is labeled simply `Resolved`; its count still honors the selected `resolved_at` range.

Every query is a bounded `SELECT` through the existing read-only datasource and avoids exposing complete `raw_json` provenance. The permanent redacted verifier executes the original seven plus enhanced six panels through Grafana's datasource API and reports only frame/row counts. Active windows deliberately do not age out with the time picker; Resolved uses the selected resolution-time range.

Item 39 added incident-scoped `View matching logs` links to the three enhanced tables. Item 41 retains that incident-ID lookup for Active and Resolved. The rolling Interface Flaps table instead opens an exact device/interface lookup over the preceding 60 minutes, using hidden hex-encoded row keys so interface names cannot alter SQL structure. Every query remains read-only, newest first, and capped at 1,000 rows. Repository captures target the clean-install main organization; the staging helper rewrites isolated NOC copies to the runtime NOC organization ID. Item 40 implemented compact Explore panes so the SQL editor starts collapsed.

Item 40 also marks the existing Severity Breakdown, Top Devices, OSPF Events, and BGP Events links in `NOC View` as one-click targets. Their destination SQL, selected dashboard time range, read-only datasource, and 1,000-row limit remain unchanged. Their Explore panes also start compact. Grafana permits only one one-click link per visualization; each affected panel has exactly one.

The redacted query verifier also recognizes these links. For each nonempty linked table it selects one incident identity only in process memory, executes the rendered Explore query, and prints only frame and row counts. No incident identity, device, or log content is emitted.

The governing pattern remains:

1. deterministic incident/evidence state remains authoritative outside Grafana
2. deterministic lifecycle snapshots and validated AI result records are stored in separate ClickHouse tables
3. the enhanced dashboard presents the deterministic NOC queue; the original presents AI assessment history
4. operators retain drilldown access to the underlying raw observations

Grafana must not become the incident state database or a substitute for deterministic correlation.

Item-32 production validation passed create-only `dryRun=All`, exact live resource reread, unchanged exact verification of the four preexisting dashboards, and all seven live datasource queries. No existing dashboard was replaced.

Item-33 production validation passed distinct create/dry-run, exact six-resource reread, all fifteen live datasource queries, backward-compatible GX10/collector Device projection, private legacy mapping, and unchanged exact verification of the original dashboard. Only the distinct enhanced resource was replaced during refinement.

Item-34 production validation passed enhanced-only replacement dry-run, exact six-resource reread, all thirteen current live datasource queries, 804 latest lifecycle rows with complete Device identity, exclusive interface-flap presentation, and zero lifecycle records in `ai_updates`. The original dashboard remained byte-exact. See `docs/NOC_WORKFLOW.md` for queue semantics.

Item-40 production validation passed main-organization `dryRun=All`, exact six-resource reread, and organization-scoped legacy rereads for the isolated NOC copies. The native v2 `default` namespace exposes the main resources even while the administrator is scoped elsewhere, so NOC mutations and verification must use the explicit runtime organization namespace. Both enhanced panel/query and sampled incident-drilldown passes succeeded, all four NOC View drilldown queries executed through the read-only datasource, and main/NOC links retained their respective organization scopes. The live and rollback Grafana databases passed integrity checks; Grafana, ClickHouse, Vector, and the result gate remained healthy with zero restarts.

Item-41 production validation used the explicit native runtime NOC namespace rather than relying on the active administrator organization. Main and NOC `dryRun=All` passes persisted nothing; the protected replacements changed exactly the two organization-local enhanced resources and zero other resources. Exact main six-resource and NOC enhanced rereads passed, all six enhanced queries plus sampled Active/Flap/Resolved drilldowns passed in each organization, and all three NOC links retained the runtime NOC organization scope. Both live and rollback databases pass integrity checks; Grafana, ClickHouse, Vector, and the result gate remain active with zero restarts.

At item-35 closure, production validation passed pre/post execution of all thirteen live datasource queries, `dryRun=All`, enhanced-only replacement, and exact reread of all six resources. That checkpoint observed two non-interface Active Events and 34 Interface Flaps, with zero interface entities in Active Events. Those counts are historical; current queue counts are dynamic. Neither then-current Active row had a stored AI summary, so both displayed the deterministic detail fallback. The resolved statistic is labeled `Resolved` while retaining its selected-range semantics, and the original dashboard remains byte-exact.

Item-36 production validation passed the ordered collector-first deployment, exact six-resource reread, all thirteen original/enhanced queries, enhanced-only replacement, recurrence parity, and unchanged existing resolved protocol history. Active Events maps deterministic `RECOVERING` to `MONITORING` only for BGP/OSPF/OSPFv3 and displays distinct issue episodes as lifecycle `recurrence_count + 1`; the additive default-zero collector column keeps immutable version-1 history queryable.

Item-37 production validation passed the isolated NOC Viewer boundary, two-dashboard/two-datasource inventory, home/star preferences, non-scoped dashboard denial, persistent-write denial, all fourteen panel queries executed as the NOC Viewer, exact unchanged verification of all six main-organization dashboards, and healthy Grafana/data-path services.

Item-38 production validation passed one-minute playlist creation in the isolated NOC namespace, exact stable-UID order, Viewer read/start access, Viewer create denial, the auto-fit play route, zero main-organization playlists, exact unchanged verification of all six main dashboards, database integrity, and healthy Grafana/data-path services.

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

Current Grafana state and residual clean-host risk are tracked in
`docs/CURRENT_STATE.md`; there is no separate current Grafana integration task.
