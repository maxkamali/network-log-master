#!/usr/bin/env bash
set -euo pipefail

TRANSPORT_VIEW="raw"

if [ "${1:-}" = "--help" ]; then
    echo "usage: verify-runtime.sh [--transport-view raw|handoff]"
    exit 0
fi

if [ "${1:-}" = "--transport-view" ]; then
    [ "$#" -eq 2 ] \
        || {
            echo "FAIL: --transport-view requires raw or handoff" >&2
            exit 1
        }
    TRANSPORT_VIEW="$2"
    shift 2
fi

[ "$#" -eq 0 ] \
    || {
        echo "FAIL: unexpected runtime-verifier argument" >&2
        exit 1
    }

case "$TRANSPORT_VIEW" in
    raw|handoff)
        ;;
    *)
        echo "FAIL: unsupported transport view: $TRANSPORT_VIEW" >&2
        exit 1
        ;;
esac

die()
{
    echo "FAIL: $*" >&2
    exit 1
}

require_file()
{
    [ -f "$1" ] \
        || die "required file missing: $1"
}

require_private_file()
{
    local path="$1"
    local label="$2"
    local mode

    require_file "$path"

    [ -s "$path" ] \
        || die "$label is empty"

    mode="$(
        stat -c '%a' "$path"
    )"

    if (( (8#$mode & 077) != 0 )); then
        die "$label must not be group/world accessible"
    fi
}

require_active()
{
    systemctl is-active --quiet "$1" \
        || die "$1 is not active"
}

require_enabled()
{
    systemctl is-enabled --quiet "$1" \
        || die "$1 is not enabled"
}

require_metadata()
{
    local path="$1"
    local mode="$2"
    local owner="$3"
    local group="$4"
    local actual

    [ -e "$path" ] \
        || die "missing path $path"

    actual="$(
        stat -c '%a:%U:%G' "$path"
    )"

    [ "$actual" = "$mode:$owner:$group" ] \
        || die \
            "$path metadata expected=$mode:$owner:$group actual=$actual"
}

[ "${EUID}" -eq 0 ] \
    || die "run this verifier as root"

: "${CLICKHOUSE_DEFAULT_PASSWORD_FILE:?set CLICKHOUSE_DEFAULT_PASSWORD_FILE}"

require_private_file \
    "$CLICKHOUSE_DEFAULT_PASSWORD_FILE" \
    "ClickHouse default password file"

umask 077

SCRIPT_DIR="$(
    cd "$(
        dirname "${BASH_SOURCE[0]}"
    )" \
        && pwd
)"

REPO_ROOT="$(
    cd "$SCRIPT_DIR/../../.." \
        && pwd
)"

cd "$REPO_ROOT"

CLICKHOUSE_DIR="$REPO_ROOT/components/collector/clickhouse"
FILESYSTEM_DIR="$REPO_ROOT/components/collector/filesystem"
GRAFANA_DIR="$REPO_ROOT/components/collector/grafana"
CERTBOT_DIR="$REPO_ROOT/components/collector/certbot"
SBIN_DIR="$REPO_ROOT/components/collector/sbin"
SYSTEMD_DIR="$REPO_ROOT/components/collector/systemd"
VECTOR_DIR="$REPO_ROOT/components/collector/vector"

echo "=== PACKAGE CONTRACT ==="

"$SCRIPT_DIR/verify-packages.sh"

echo
echo "=== SERVICE STATE ==="

for service in \
    clickhouse-server.service \
    vector.service \
    grafana-server.service
do
    require_enabled "$service"
    require_active "$service"
    echo "$service=enabled,active"
done

for timer in \
    ai-results-gate.timer \
    certbot-renew.timer
do
    require_enabled "$timer"
    require_active "$timer"
    echo "$timer=enabled,active"
done

echo
echo "=== CUSTOM IMPLEMENTATION PARITY ==="

while read -r repo live; do
    cmp -s "$repo" "$live" \
        || die "$live differs from repository artifact"

    echo "$(basename "$live")=exact-match"
done <<EOF
$SBIN_DIR/ai-results-gate /usr/local/sbin/ai-results-gate
$SYSTEMD_DIR/ai-results-gate.service /etc/systemd/system/ai-results-gate.service
$SYSTEMD_DIR/ai-results-gate.timer /etc/systemd/system/ai-results-gate.timer
$SYSTEMD_DIR/ai-results-gate.service.d/10-rw-paths.conf /etc/systemd/system/ai-results-gate.service.d/10-rw-paths.conf
$SYSTEMD_DIR/vector.service.d/50-result-ready-no-file-cap.conf /etc/systemd/system/vector.service.d/50-result-ready-no-file-cap.conf
EOF

vector_nofile="$(
    systemctl show vector.service -p LimitNOFILE --value
)"

case "$vector_nofile" in
    65536|65536:*)
        ;;
    *)
        die "Vector descriptor limit differs"
        ;;
esac

echo "vector_nofile=65536"

echo
echo "=== RETENTION CONTRACT ==="

mapfile -t retention_timers < <(
    systemctl list-unit-files \
        'vector*-retention-policy.timer' \
        --no-legend \
        --no-pager \
        | awk '
            $2 == "enabled" {
                print $1
            }
        '
)

[ "${#retention_timers[@]}" -eq 1 ] \
    || die \
        "expected exactly one enabled Vector retention timer"

RETENTION_TIMER="${retention_timers[0]}"

require_enabled "$RETENTION_TIMER"
require_active "$RETENTION_TIMER"

RETENTION_SERVICE="$(
    systemctl show \
        "$RETENTION_TIMER" \
        -p Unit \
        --value
)"

if [ -z "$RETENTION_SERVICE" ]; then
    RETENTION_SERVICE="${
        RETENTION_TIMER%.timer
    }.service"
fi

RETENTION_EXEC="$(
    systemctl show \
        "$RETENTION_SERVICE" \
        -p ExecStart \
        --value \
        | sed -n \
            's/^{ path=\([^ ;]*\).*/\1/p'
)"

[ -n "$RETENTION_EXEC" ] \
    || die "could not determine retention executable"

require_metadata \
    "$RETENTION_EXEC" \
    755 \
    root \
    root

RETENTION_TIMER_TEXT="$(
    systemctl cat "$RETENTION_TIMER"
)"

RETENTION_SERVICE_TEXT="$(
    systemctl cat "$RETENTION_SERVICE"
)"

grep -Eq \
    '^[[:space:]]*OnCalendar=daily[[:space:]]*$' \
    <<< "$RETENTION_TIMER_TEXT" \
    || die "retention timer is not daily"

grep -Eq \
    '^[[:space:]]*Persistent=true[[:space:]]*$' \
    <<< "$RETENTION_TIMER_TEXT" \
    || die "retention timer is not persistent"

grep -Eq \
    '^[[:space:]]*RandomizedDelaySec=30m[[:space:]]*$' \
    <<< "$RETENTION_TIMER_TEXT" \
    || die "retention randomized delay differs"

grep -Eq \
    '^[[:space:]]*Type=oneshot[[:space:]]*$' \
    <<< "$RETENTION_SERVICE_TEXT" \
    || die "retention service is not oneshot"

python3 - \
    "$RETENTION_EXEC" \
    "$SBIN_DIR/vector-ai-agent-retention-policy" \
<<'PYRET'
from pathlib import Path
import re
import sys

live_path = Path(sys.argv[1])
repo_path = Path(sys.argv[2])

for path, label in [
    (live_path, "live"),
    (repo_path, "repository"),
]:
    text = path.read_text(
        encoding="utf-8",
        errors="strict",
    )

    checks = {
        "spool root": (
            r'(?m)^'
            r'\s*ROOT="/var/spool/vector-ai"'
            r'\s*$'
        ),
        "90-day retention": (
            r'(?m)^'
            r'\s*RETENTION_MINUTES='
            r'\$\(\('
            r'\s*90\s*\*\s*24\s*\*\s*60\s*'
            r'\)\)'
            r'\s*$'
        ),
        "file expiry": (
            r'find\s+"\$ROOT"'
            r'\s+-type\s+f'
            r'\s+-mmin\s+\+"\$RETENTION_MINUTES"'
            r'.*?'
            r'-delete'
        ),
        "empty directory cleanup": (
            r'find\s+"\$ROOT"'
            r'\s+-depth'
            r'\s+-type\s+d'
            r'\s+-empty'
            r'\s+!\s+-path\s+"\$ROOT"'
            r'\s+-delete'
        ),
    }

    for name, pattern in checks.items():
        if not re.search(
            pattern,
            text,
            flags=re.S,
        ):
            raise SystemExit(
                f"FAIL: {label} retention script "
                f"does not satisfy: {name}"
            )

print("RETENTION_SCRIPT_CONTRACT=PASS")
PYRET

echo "retention_timer_enabled=yes"
echo "retention_timer_active=yes"
echo "retention_schedule=daily"
echo "retention_persistent=yes"
echo "retention_randomized_delay=30m"
echo "RETENTION_RUNTIME_CONTRACT=PASS"

echo
echo "=== TRANSPORT CONTRACT ==="

"$FILESYSTEM_DIR/verify-transport.sh" \
    --reader-bind-source "$TRANSPORT_VIEW"

echo
echo "=== CLICKHOUSE ADMIN CONNECTION ==="

TMPDIR="$(
    mktemp -d
)"

cleanup()
{
    rm -rf "$TMPDIR"
}

trap cleanup EXIT

CH_CONFIG="$TMPDIR/clickhouse-client.xml"

install \
    -o root \
    -g root \
    -m 0600 \
    /dev/null \
    "$CH_CONFIG"

python3 - \
    "$CLICKHOUSE_DEFAULT_PASSWORD_FILE" \
    "$CH_CONFIG" \
<<'PY'
from pathlib import Path
import os
import sys
from xml.sax.saxutils import escape

source = Path(sys.argv[1])
destination = Path(sys.argv[2])

password = source.read_text(
    encoding="utf-8",
    errors="strict",
).rstrip("\r\n")

if not password:
    raise SystemExit(
        "FAIL: ClickHouse default password is empty"
    )

if "\n" in password or "\r" in password:
    raise SystemExit(
        "FAIL: ClickHouse password must be one line"
    )

destination.write_text(
    "<config>\n"
    "  <user>default</user>\n"
    f"  <password>{escape(password)}</password>\n"
    "</config>\n",
    encoding="utf-8",
)
PY

CH=(
    clickhouse-client
    --config-file
    "$CH_CONFIG"
)

"${CH[@]}" \
    --query "SELECT 1" \
    >/dev/null

echo "clickhouse_admin_connection=PASS"

echo
echo "=== CLICKHOUSE OBJECT CONTRACT ==="

"${CH[@]}" \
    --query "
        SELECT
            name,
            engine,
            create_table_query
        FROM system.tables
        WHERE database = 'observability'
        ORDER BY name
        FORMAT JSONEachRow
    " \
    > "$TMPDIR/clickhouse-objects.jsonl"

python3 - "$TMPDIR/clickhouse-objects.jsonl" <<'PY'
from pathlib import Path
import json
import sys

rows = [
    json.loads(line)
    for line in Path(sys.argv[1]).read_text(
        encoding="utf-8",
        errors="strict",
    ).splitlines()
    if line.strip()
]

objects = {
    row["name"]: row
    for row in rows
}

expected = {
    "syslog": "MergeTree",
    "ai_updates": "MergeTree",
    "ai_result_devices": "MergeTree",
    "incident_updates": "ReplacingMergeTree",
    "grafana_logs": "View",
}

if set(objects) != set(expected):
    raise SystemExit(
        "FAIL: unexpected observability object set: "
        + repr(sorted(objects))
    )

for name, engine in expected.items():
    actual = objects[name]["engine"]

    if actual != engine:
        raise SystemExit(
            f"FAIL: {name} expected engine={engine} "
            f"actual={actual}"
        )

for name in [
    "syslog",
    "ai_updates",
    "ai_result_devices",
]:
    query = objects[name]["create_table_query"]

    if "toIntervalMonth(12)" not in query:
        raise SystemExit(
            f"FAIL: {name} missing 12-month TTL"
        )

view = objects["grafana_logs"]["create_table_query"]

if "SQL SECURITY INVOKER" not in view:
    raise SystemExit(
        "FAIL: grafana_logs missing SQL SECURITY INVOKER"
    )

if "observability.syslog" not in view:
    raise SystemExit(
        "FAIL: grafana_logs does not reference observability.syslog"
    )

print("CLICKHOUSE_OBJECT_CONTRACT=PASS")
PY

echo
echo "=== CLICKHOUSE COLUMN CONTRACT ==="

"${CH[@]}" \
    --query "
        SELECT
            table,
            name,
            type
        FROM system.columns
        WHERE database = 'observability'
        ORDER BY table, position
        FORMAT JSONEachRow
    " \
    > "$TMPDIR/clickhouse-columns.jsonl"

python3 - "$TMPDIR/clickhouse-columns.jsonl" <<'PY'
from pathlib import Path
import json
import sys

rows = [
    json.loads(line)
    for line in Path(sys.argv[1]).read_text(
        encoding="utf-8",
        errors="strict",
    ).splitlines()
    if line.strip()
]

observed = {}

for row in rows:
    observed.setdefault(
        row["table"],
        {},
    )[row["name"]] = row["type"]

expected = {
    "syslog": {
        "timestamp": "DateTime64(9, 'UTC')",
        "ingest_timestamp": "DateTime64(9, 'UTC')",
        "device_timestamp": "Nullable(DateTime64(9, 'UTC'))",
        "collector_local_time": "String",
        "source_ip": "String",
        "source_port": "UInt16",
        "hostname": "String",
        "host": "String",
        "facility": "LowCardinality(String)",
        "severity": "LowCardinality(String)",
        "appname": "String",
        "message": "String",
        "raw_message": "String",
        "parse_status": "LowCardinality(String)",
        "source_type": "LowCardinality(String)",
        "version": "UInt8",
        "event_json": "String",
    },
    "ai_updates": {
        "timestamp": "DateTime64(3, 'UTC')",
        "incident_id": "String",
        "run_id": "String",
        "device": "String",
        "model": "LowCardinality(String)",
        "type": "LowCardinality(String)",
        "status": "LowCardinality(String)",
        "severity": "LowCardinality(String)",
        "first_seen": "Nullable(DateTime64(3, 'UTC'))",
        "last_seen": "Nullable(DateTime64(3, 'UTC'))",
        "occurrence_count": "UInt32",
        "title": "String",
        "body": "String",
        "tags": "Array(String)",
        "raw_json": "String",
    },
    "ai_result_devices": {
        "run_id": "String",
        "device": "String",
        "mapped_at": "DateTime64(3, 'UTC')",
    },
    "incident_updates": {
        "timestamp": "DateTime64(3, 'UTC')",
        "snapshot_id": "String",
        "snapshot_version": "UInt64",
        "incident_id": "String",
        "device": "String",
        "entity_type": "LowCardinality(String)",
        "entity_name": "String",
        "event_family": "LowCardinality(String)",
        "protocol": "LowCardinality(String)",
        "lifecycle_status": "LowCardinality(String)",
        "severity": "LowCardinality(String)",
        "first_seen": "DateTime64(3, 'UTC')",
        "last_seen": "DateTime64(3, 'UTC')",
        "opened_at": "Nullable(DateTime64(3, 'UTC'))",
        "recovering_at": "Nullable(DateTime64(3, 'UTC'))",
        "resolved_at": "Nullable(DateTime64(3, 'UTC'))",
        "occurrence_count": "UInt32",
        "recurrence_count": "UInt32",
        "repeat_count_total": "UInt64",
        "state_change_count": "UInt32",
        "last_observation_state": "LowCardinality(String)",
        "interface_flap": "Bool",
        "engine_version": "UInt16",
        "title": "String",
        "body": "String",
        "type": "LowCardinality(String)",
        "producer_schema": "LowCardinality(String)",
        "producer_version": "UInt16",
        "raw_json": "String",
    },
    "grafana_logs": {
        "timestamp": "DateTime64(9, 'UTC')",
        "body": "String",
        "level": "LowCardinality(String)",
        "device": "String",
        "hostname": "String",
        "source_ip": "String",
        "source_port": "UInt16",
        "facility": "LowCardinality(String)",
        "appname": "String",
        "message": "String",
        "raw_message": "String",
        "parse_status": "LowCardinality(String)",
        "device_timestamp": "Nullable(DateTime64(9, 'UTC'))",
        "ingest_timestamp": "DateTime64(9, 'UTC')",
        "source_type": "LowCardinality(String)",
    },
}

if observed != expected:
    for table in sorted(
        set(observed) | set(expected)
    ):
        if observed.get(table) != expected.get(table):
            print(
                f"table={table}",
                file=sys.stderr,
            )
            print(
                " expected="
                + repr(expected.get(table)),
                file=sys.stderr,
            )
            print(
                " observed="
                + repr(observed.get(table)),
                file=sys.stderr,
            )

    raise SystemExit(
        "FAIL: ClickHouse column contract differs"
    )

print("CLICKHOUSE_COLUMN_CONTRACT=PASS")
PY

echo
echo "=== CLICKHOUSE USER POLICY ==="

"${CH[@]}" \
    --query "
        SELECT
            name,
            storage,
            auth_type,
            host_ip
        FROM system.users
        WHERE name IN (
            'default',
            'grafana_reader',
            'vector_ingest'
        )
        ORDER BY name
        FORMAT JSONEachRow
    " \
    > "$TMPDIR/clickhouse-users.jsonl"

python3 - "$TMPDIR/clickhouse-users.jsonl" <<'PY'
from pathlib import Path
import ipaddress
import json
import sys

rows = [
    json.loads(line)
    for line in Path(sys.argv[1]).read_text(
        encoding="utf-8",
        errors="strict",
    ).splitlines()
    if line.strip()
]

users = {
    row["name"]: row
    for row in rows
}

expected_storage = {
    "default": "users_xml",
    "grafana_reader": "local_directory",
    "vector_ingest": "local_directory",
}

if set(users) != set(expected_storage):
    raise SystemExit(
        "FAIL: expected ClickHouse users are missing"
    )

for name, storage in expected_storage.items():
    row = users[name]

    if row["storage"] != storage:
        raise SystemExit(
            f"FAIL: {name} storage differs"
        )

    auth = row.get("auth_type") or []

    if isinstance(auth, str):
        auth = [auth]

    if "sha256_password" not in auth:
        raise SystemExit(
            f"FAIL: {name} is not using sha256_password"
        )

    hosts = row.get("host_ip") or []

    if isinstance(hosts, str):
        hosts = [hosts]

    any_address = False

    for value in hosts:
        try:
            network = ipaddress.ip_network(
                value,
                strict=False,
            )
        except ValueError:
            continue

        if network.prefixlen == 0:
            any_address = True

    if not any_address:
        raise SystemExit(
            f"FAIL: {name} HOST ANY policy differs"
        )

print("CLICKHOUSE_USER_POLICY=PASS")
PY

"${CH[@]}" \
    --query "
        SHOW CREATE SETTINGS PROFILE grafana_reader
        FORMAT TabSeparatedRaw
    " \
    > "$TMPDIR/grafana-profile.txt"

expected_profile='CREATE SETTINGS PROFILE `grafana_reader` SETTINGS readonly = 1, max_execution_time CHANGEABLE_IN_READONLY TO grafana_reader'

actual_profile="$(
    cat "$TMPDIR/grafana-profile.txt"
)"

[ "$actual_profile" = "$expected_profile" ] \
    || die "grafana_reader settings profile differs"

echo "clickhouse_grafana_profile=PASS"

"${CH[@]}" \
    --query "
        SHOW GRANTS FOR grafana_reader
        FORMAT TabSeparatedRaw
    " \
    > "$TMPDIR/grafana-grants.txt"

"${CH[@]}" \
    --query "
        SHOW GRANTS FOR vector_ingest
        FORMAT TabSeparatedRaw
    " \
    > "$TMPDIR/vector-grants.txt"

python3 - \
    "$TMPDIR/grafana-grants.txt" \
    "$TMPDIR/vector-grants.txt" \
<<'PY'
from pathlib import Path
import sys

grafana = {
    line
    for line in Path(sys.argv[1]).read_text(
        encoding="utf-8",
        errors="strict",
    ).splitlines()
    if line
}

vector = {
    line
    for line in Path(sys.argv[2]).read_text(
        encoding="utf-8",
        errors="strict",
    ).splitlines()
    if line
}

expected_grafana = {
    "GRANT SELECT ON observability.ai_result_devices TO grafana_reader",
    "GRANT SELECT ON observability.ai_updates TO grafana_reader",
    "GRANT SELECT ON observability.incident_updates TO grafana_reader",
    "GRANT SELECT ON observability.grafana_logs TO grafana_reader",
    "GRANT SELECT ON observability.syslog TO grafana_reader",
    "GRANT SELECT ON system.columns TO grafana_reader",
    "GRANT SELECT ON system.databases TO grafana_reader",
    "GRANT SELECT ON system.tables TO grafana_reader",
}

expected_vector = {
    "GRANT INSERT ON observability.ai_updates TO vector_ingest",
    "GRANT INSERT ON observability.incident_updates TO vector_ingest",
    "GRANT INSERT ON observability.syslog TO vector_ingest",
}

if grafana != expected_grafana:
    raise SystemExit(
        "FAIL: grafana_reader grants differ"
    )

if vector != expected_vector:
    raise SystemExit(
        "FAIL: vector_ingest grants differ"
    )

print("CLICKHOUSE_GRANT_CONTRACT=PASS")
PY

echo
echo "=== CLICKHOUSE LISTENER BOUNDARY ==="

ss -H -lntp \
    > "$TMPDIR/tcp-listeners.txt"

python3 - "$TMPDIR/tcp-listeners.txt" <<'PY'
from pathlib import Path
import ipaddress
import sys

required = {
    "8123",
    "9000",
}

observed = set()

for line in Path(sys.argv[1]).read_text(
    encoding="utf-8",
    errors="replace",
).splitlines():
    if "clickhouse" not in line.casefold():
        continue

    parts = line.split()

    if len(parts) < 5:
        continue

    local = parts[3]

    host = ""
    port = ""

    if local.startswith("[") and "]:" in local:
        host, port = local[1:].rsplit("]:", 1)
    else:
        host, port = local.rsplit(":", 1)

    address = ipaddress.ip_address(host)

    if not address.is_loopback:
        raise SystemExit(
            "FAIL: ClickHouse has a non-loopback listener"
        )

    observed.add(port)

missing = required - observed

if missing:
    raise SystemExit(
        "FAIL: missing ClickHouse listeners: "
        + repr(sorted(missing))
    )

print("CLICKHOUSE_LOOPBACK_LISTENERS=PASS")
PY

echo
echo "=== VECTOR CONFIGURATION ==="

require_metadata \
    /etc/vector/secrets/clickhouse_password \
    400 \
    vector \
    vector

[ -s /etc/vector/secrets/clickhouse_password ] \
    || die "Vector ClickHouse secret file is empty"

vector validate \
    /etc/vector/vector.yaml \
    >/dev/null 2>&1

echo "vector_live_config_validate=PASS"

python3 - \
    "$VECTOR_DIR/vector.yaml" \
    /etc/vector/vector.yaml \
<<'PY'
from pathlib import Path
import re
import sys

repo = Path(sys.argv[1]).read_text(
    encoding="utf-8",
    errors="strict",
)

live = Path(sys.argv[2]).read_text(
    encoding="utf-8",
    errors="strict",
)


def extract(text, name):
    lines = text.splitlines()

    marker = f"  {name}:"

    try:
        start = lines.index(marker)
    except ValueError:
        raise SystemExit(
            f"FAIL: block {name} not found"
        )

    result = []

    for index in range(
        start,
        len(lines),
    ):
        line = lines[index]

        if index > start:
            if line and not line.startswith(" "):
                break

            if (
                line.startswith("  ")
                and not line.startswith("    ")
                and re.match(
                    r"^  [A-Za-z0-9_.-]+:\s*$",
                    line,
                )
            ):
                break

        result.append(line)

    return "\n".join(result).rstrip()


for block in [
    "normalize_udp",
    "normalize_tcp",
    "ai_spool",
]:
    if extract(repo, block) != extract(live, block):
        raise SystemExit(
            f"FAIL: Vector block differs: {block}"
        )

required_literals = [
    "ai_results_ready:",
    "clickhouse_ai_updates:",
    "clickhouse_incident_updates:",
    "clickhouse_syslog:",
    "/var/spool/vector-ai/%Y/%m/%d/%H/syslog-%Y%m%d-%H%M.jsonl.zst",
    "SECRET[clickhouse_secrets.clickhouse_password]",
]

for value in required_literals:
    if value not in live:
        raise SystemExit(
            f"FAIL: Vector configuration missing {value}"
        )

healthchecks = re.findall(
    r"(?m)"
    r"^\s+healthcheck:\s*$"
    r"\n"
    r"^\s+enabled:\s+false\s*$",
    live,
)

if len(healthchecks) != 3:
    raise SystemExit(
        "FAIL: expected three disabled ClickHouse healthchecks"
    )

print("VECTOR_CRITICAL_CONFIG_PARITY=PASS")
PY

ss -H -lntup \
    > "$TMPDIR/all-listeners.txt"

python3 - "$TMPDIR/all-listeners.txt" <<'PY'
from pathlib import Path
import sys

protocols = set()

for line in Path(sys.argv[1]).read_text(
    encoding="utf-8",
    errors="replace",
).splitlines():
    if "vector" not in line.casefold():
        continue

    parts = line.split()

    if len(parts) < 5:
        continue

    protocol = parts[0]
    local = parts[4]

    try:
        port = local.rsplit(":", 1)[1]
    except IndexError:
        continue

    if port == "514":
        protocols.add(protocol)

if "tcp" not in protocols:
    raise SystemExit(
        "FAIL: Vector TCP/514 listener missing"
    )

if "udp" not in protocols:
    raise SystemExit(
        "FAIL: Vector UDP/514 listener missing"
    )

print("VECTOR_SYSLOG_LISTENERS=PASS")
PY

echo
echo "=== GRAFANA TLS / HEALTH ==="

require_metadata \
    /etc/grafana/tls \
    750 \
    grafana \
    grafana

require_metadata \
    /etc/grafana/tls/fullchain.pem \
    440 \
    grafana \
    grafana

require_metadata \
    /etc/grafana/tls/privkey.pem \
    400 \
    grafana \
    grafana

[ -s /etc/grafana/tls/fullchain.pem ] \
    || die "Grafana fullchain is empty"

[ -s /etc/grafana/tls/privkey.pem ] \
    || die "Grafana private key is empty"

if command -v openssl >/dev/null 2>&1; then
    openssl x509 \
        -checkend 0 \
        -noout \
        -in /etc/grafana/tls/fullchain.pem \
        >/dev/null \
        || die "Grafana certificate is expired"

    echo "grafana_certificate_current=yes"
fi

HTTPS_CONF="/etc/systemd/system/grafana-server.service.d/https.conf"

require_file "$HTTPS_CONF"

python3 - "$HTTPS_CONF" <<'PY'
from pathlib import Path
import re
import sys

text = Path(sys.argv[1]).read_text(
    encoding="utf-8",
    errors="strict",
)

required = [
    'Environment="GF_SERVER_PROTOCOL=https"',
    'Environment="GF_SERVER_HTTP_ADDR=0.0.0.0"',
    'Environment="GF_SERVER_HTTP_PORT=443"',
    'Environment="GF_SERVER_CERT_FILE=/etc/grafana/tls/fullchain.pem"',
    'Environment="GF_SERVER_CERT_KEY=/etc/grafana/tls/privkey.pem"',
    'Environment="GF_SERVER_CERTS_WATCH_INTERVAL=5m"',
]

for line in required:
    if line not in text:
        raise SystemExit(
            f"FAIL: Grafana HTTPS override missing {line}"
        )

if not re.search(
    r'Environment="GF_SERVER_ROOT_URL=https://[^/"]+/"',
    text,
):
    raise SystemExit(
        "FAIL: Grafana HTTPS root URL missing"
    )

print("GRAFANA_HTTPS_OVERRIDE=PASS")
PY

curl \
    --insecure \
    --fail \
    --silent \
    https://127.0.0.1:443/api/health \
    > "$TMPDIR/grafana-health.json"

python3 - "$TMPDIR/grafana-health.json" <<'PY'
from pathlib import Path
import json
import sys

data = json.loads(
    Path(sys.argv[1]).read_text(
        encoding="utf-8",
        errors="strict",
    )
)

if str(data.get("database", "")).lower() != "ok":
    raise SystemExit(
        "FAIL: Grafana database health is not OK"
    )

print("GRAFANA_HTTPS_HEALTH=PASS")
PY

echo
echo "=== GRAFANA DATASOURCES ==="

sqlite3 \
    -readonly \
    -json \
    /var/lib/grafana/grafana.db \
    "
    SELECT
        name,
        uid,
        type,
        json_data,
        CASE
            WHEN length(secure_json_data) > 0
            THEN 1
            ELSE 0
        END AS has_secure_data
    FROM data_source
    WHERE uid IN (
        'efvaztlrk8ow0a',
        'bfvik20ilwoaof'
    )
    ORDER BY uid;
    " \
    > "$TMPDIR/grafana-datasources.json"

python3 - "$TMPDIR/grafana-datasources.json" <<'PY'
from pathlib import Path
import ipaddress
import json
import sys

rows = json.loads(
    Path(sys.argv[1]).read_text(
        encoding="utf-8",
        errors="strict",
    )
)

expected = {
    "efvaztlrk8ow0a": {
        "name": "grafana-clickhouse-datasource-1",
        "protocol": "native",
        "port": 9000,
        "table": "syslog",
    },
    "bfvik20ilwoaof": {
        "name": "grafana-clickhouse-logs",
        "protocol": "http",
        "port": 8123,
        "table": "grafana_logs",
    },
}

if len(rows) != 2:
    raise SystemExit(
        f"FAIL: expected 2 Grafana datasources, found {len(rows)}"
    )

for row in rows:
    uid = row["uid"]

    if uid not in expected:
        raise SystemExit(
            f"FAIL: unexpected datasource UID {uid}"
        )

    wanted = expected[uid]

    if row["name"] != wanted["name"]:
        raise SystemExit(
            f"FAIL: datasource name differs for {uid}"
        )

    if row["type"] != "grafana-clickhouse-datasource":
        raise SystemExit(
            f"FAIL: datasource type differs for {uid}"
        )

    if int(row["has_secure_data"]) != 1:
        raise SystemExit(
            f"FAIL: datasource {uid} lacks secure data"
        )

    config = json.loads(
        row["json_data"] or "{}"
    )

    if config.get("protocol") != wanted["protocol"]:
        raise SystemExit(
            f"FAIL: datasource protocol differs for {uid}"
        )

    if config.get("port") != wanted["port"]:
        raise SystemExit(
            f"FAIL: datasource port differs for {uid}"
        )

    if config.get("username") != "grafana_reader":
        raise SystemExit(
            f"FAIL: datasource username differs for {uid}"
        )

    host = str(
        config.get(
            "host",
            "",
        )
    )

    if host == "localhost":
        pass
    else:
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            raise SystemExit(
                f"FAIL: datasource host is not loopback for {uid}"
            )

        if not address.is_loopback:
            raise SystemExit(
                f"FAIL: datasource host is not loopback for {uid}"
            )

    logs = config.get("logs") or {}

    if logs.get("defaultDatabase") != "observability":
        raise SystemExit(
            f"FAIL: datasource database differs for {uid}"
        )

    if logs.get("defaultTable") != wanted["table"]:
        raise SystemExit(
            f"FAIL: datasource table differs for {uid}"
        )

print("GRAFANA_DATASOURCE_CONTRACT=PASS")
PY

echo
echo "=== CERTBOT CONTRACT ==="

require_metadata \
    /etc/letsencrypt/renewal-hooks/deploy/10-grafana-cert \
    755 \
    root \
    root

grep -Fqx \
    'ExecStart=/usr/local/bin/certbot renew --quiet' \
    /etc/systemd/system/certbot-renew.service \
    || die "Certbot renewal ExecStart differs"

grep -Fqx \
    'OnCalendar=*-*-* 00,06,12,18:00:00' \
    /etc/systemd/system/certbot-renew.timer \
    || die "Certbot renewal schedule differs"

grep -Fqx \
    'RandomizedDelaySec=30m' \
    /etc/systemd/system/certbot-renew.timer \
    || die "Certbot randomized delay differs"

grep -Fqx \
    'Persistent=true' \
    /etc/systemd/system/certbot-renew.timer \
    || die "Certbot timer persistence differs"

grep -Fq \
    'systemctl restart grafana-server' \
    /etc/letsencrypt/renewal-hooks/deploy/10-grafana-cert \
    || die "Grafana certificate deploy hook does not restart Grafana"

echo "CERTBOT_RUNTIME_CONTRACT=PASS"

echo
echo "=== FINAL SERVICE CHECK ==="

systemctl daemon-reload

for service in \
    clickhouse-server.service \
    vector.service \
    grafana-server.service
do
    require_active "$service"
done

for timer in \
    ai-results-gate.timer \
    certbot-renew.timer
do
    require_enabled "$timer"
    require_active "$timer"
done

echo "collector_transport_view=$TRANSPORT_VIEW"
echo "COLLECTOR_RUNTIME_VERIFY=PASS"
