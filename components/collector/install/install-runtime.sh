#!/usr/bin/env bash
set -euo pipefail

die()
{
    echo "ERROR: $*" >&2
    exit 1
}

require_root()
{
    [ "${EUID}" -eq 0 ] \
        || die "run this installer as root"
}

require_var()
{
    local name="$1"

    [ -n "${!name:-}" ] \
        || die "required environment variable is not set: $name"
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

require_root

require_var CLEAN_INSTALL_CONFIRM

[ "$CLEAN_INSTALL_CONFIRM" = "YES-CLEAN-COLLECTOR" ] \
    || die "CLEAN_INSTALL_CONFIRM must equal YES-CLEAN-COLLECTOR"

for name in \
    CLICKHOUSE_DEFAULT_PASSWORD_FILE \
    GRAFANA_READER_PASSWORD_FILE \
    GRAFANA_ADMIN_PASSWORD_FILE \
    VECTOR_INGEST_PASSWORD_FILE \
    GRAFANA_PUBLIC_HOST \
    CERT_NAME \
    CERTBOT_EMAIL \
    SSH_PORT \
    AI_SPOOL_READER_AUTHORIZED_KEYS_FILE \
    AI_RESULTS_WRITER_AUTHORIZED_KEYS_FILE
do
    require_var "$name"
done

require_private_file \
    "$CLICKHOUSE_DEFAULT_PASSWORD_FILE" \
    "ClickHouse default password file"

require_private_file \
    "$GRAFANA_READER_PASSWORD_FILE" \
    "Grafana reader password file"

require_private_file \
    "$GRAFANA_ADMIN_PASSWORD_FILE" \
    "Grafana administrator password file"

python3 -c 'from pathlib import Path; import sys; raw = Path(sys.argv[1]).read_text(encoding="utf-8", errors="strict"); password = raw.rstrip("\r\n"); sys.exit("ERROR: Grafana administrator password must be one non-empty line") if (not password or "\n" in password or "\r" in password) else None' "$GRAFANA_ADMIN_PASSWORD_FILE"

require_private_file \
    "$VECTOR_INGEST_PASSWORD_FILE" \
    "Vector ingest password file"

python3 - \
    "$GRAFANA_PUBLIC_HOST" \
    "$CERT_NAME" \
<<'PY'
import ipaddress
import sys

host = sys.argv[1]
cert_name = sys.argv[2]

try:
    address = ipaddress.ip_address(host)
except ValueError:
    raise SystemExit(
        "ERROR: current collector rebuild contract "
        "expects GRAFANA_PUBLIC_HOST to be an IP address"
    )

if address.version != 4:
    raise SystemExit(
        "ERROR: current collector rebuild contract "
        "expects an IPv4 Grafana certificate"
    )

if cert_name != host:
    raise SystemExit(
        "ERROR: current deployment uses the public IP "
        "as both GRAFANA_PUBLIC_HOST and CERT_NAME"
    )
PY

case "$SSH_PORT" in
    ''|*[!0-9]*)
        die "SSH_PORT must be numeric"
        ;;
esac

if [ "$SSH_PORT" -lt 1 ] || [ "$SSH_PORT" -gt 65535 ]; then
    die "SSH_PORT must be between 1 and 65535"
fi

if [ "$SSH_PORT" -eq 22 ]; then
    die "current collector rebuild contract uses a nonstandard SSH port"
fi

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

CLICKHOUSE_DIR="$REPO_ROOT/components/collector/clickhouse"
VECTOR_DIR="$REPO_ROOT/components/collector/vector"
GRAFANA_DIR="$REPO_ROOT/components/collector/grafana"
CERTBOT_DIR="$REPO_ROOT/components/collector/certbot"
SYSTEMD_DIR="$REPO_ROOT/components/collector/systemd"
SBIN_DIR="$REPO_ROOT/components/collector/sbin"
FILESYSTEM_DIR="$REPO_ROOT/components/collector/filesystem"

for path in \
    "$SCRIPT_DIR/render-configs.py" \
    "$SCRIPT_DIR/verify-packages.sh" \
    "$CLICKHOUSE_DIR/00-database.sql" \
    "$CLICKHOUSE_DIR/10-syslog.sql" \
    "$CLICKHOUSE_DIR/20-ai-updates.sql" \
    "$CLICKHOUSE_DIR/30-grafana-logs.sql" \
    "$CLICKHOUSE_DIR/40-access-control.sql.in" \
    "$VECTOR_DIR/vector.yaml" \
    "$GRAFANA_DIR/provisioning/datasources/clickhouse.yaml.in" \
    "$GRAFANA_DIR/systemd/grafana-server.service.d/https.conf.in" \
    "$GRAFANA_DIR/scripts/dashboard_api.py" \
    "$GRAFANA_DIR/scripts/restore-dashboards.py" \
    "$GRAFANA_DIR/scripts/verify-dashboards.py" \
    "$GRAFANA_DIR/dashboards/device-logs.json" \
    "$GRAFANA_DIR/dashboards/logs-dash.json" \
    "$GRAFANA_DIR/dashboards/noc-view.json" \
    "$GRAFANA_DIR/dashboards/noc-view-copy-backup.json" \
    "$CERTBOT_DIR/systemd/certbot-renew.service" \
    "$CERTBOT_DIR/systemd/certbot-renew.timer" \
    "$CERTBOT_DIR/renewal-hooks/deploy/10-grafana-cert.in" \
    "$SBIN_DIR/ai-results-gate" \
    "$SBIN_DIR/vector-ai-agent-retention-policy" \
    "$SYSTEMD_DIR/ai-results-gate.service" \
    "$SYSTEMD_DIR/ai-results-gate.timer" \
    "$SYSTEMD_DIR/vector-ai-agent-retention-policy.service" \
    "$SYSTEMD_DIR/vector-ai-agent-retention-policy.timer" \
    "$FILESYSTEM_DIR/bootstrap-transport.sh"
do
    require_file "$path"
done

"$SCRIPT_DIR/verify-packages.sh"

SYSLOG_UDP_ADDRESS="${SYSLOG_UDP_ADDRESS:-0.0.0.0:514}"
SYSLOG_TCP_ADDRESS="${SYSLOG_TCP_ADDRESS:-0.0.0.0:514}"
CLICKHOUSE_ENDPOINT="${CLICKHOUSE_ENDPOINT:-http://127.0.0.1:8123}"
CLICKHOUSE_HOST="${CLICKHOUSE_HOST:-127.0.0.1}"
CLICKHOUSE_USER="${CLICKHOUSE_USER:-vector_ingest}"

export \
    SYSLOG_UDP_ADDRESS \
    SYSLOG_TCP_ADDRESS \
    CLICKHOUSE_ENDPOINT \
    CLICKHOUSE_HOST \
    CLICKHOUSE_USER \
    GRAFANA_PUBLIC_HOST \
    CERT_NAME \
    GRAFANA_READER_PASSWORD_FILE \
    VECTOR_INGEST_PASSWORD_FILE \
    SSH_PORT \
    AI_SPOOL_READER_AUTHORIZED_KEYS_FILE \
    AI_RESULTS_WRITER_AUTHORIZED_KEYS_FILE

umask 077

TMPDIR="$(
    mktemp -d
)"

cleanup()
{
    if [ -n "${GRAFANA_BOOTSTRAP_DROPIN:-}" ] \
        && [ -e "$GRAFANA_BOOTSTRAP_DROPIN" ]
    then
        systemctl stop grafana-server.service \
            >/dev/null 2>&1 \
            || true

        rm -f "$GRAFANA_BOOTSTRAP_DROPIN" \
            || true

        systemctl daemon-reload \
            >/dev/null 2>&1 \
            || true
    fi

    rm -rf "$TMPDIR"
}

trap cleanup EXIT

CH_CLIENT_CONFIG="$TMPDIR/clickhouse-client.xml"

python3 - \
    "$CLICKHOUSE_DEFAULT_PASSWORD_FILE" \
    "$CH_CLIENT_CONFIG" \
<<'PY'
from pathlib import Path
import os
import sys
from xml.sax.saxutils import escape

password_path = Path(sys.argv[1])
destination = Path(sys.argv[2])

password = password_path.read_text(
    encoding="utf-8",
    errors="strict",
).rstrip("\r\n")

if not password:
    raise SystemExit(
        "ERROR: ClickHouse default password is empty"
    )

if "\n" in password or "\r" in password:
    raise SystemExit(
        "ERROR: ClickHouse default password must be one line"
    )

destination.write_text(
    "<config>\n"
    "  <user>default</user>\n"
    f"  <password>{escape(password)}</password>\n"
    "</config>\n",
    encoding="utf-8",
)

os.chmod(
    destination,
    0o600,
)
PY

CH=(
    clickhouse-client
    --config-file
    "$CH_CLIENT_CONFIG"
)

systemctl enable clickhouse-server.service
systemctl start clickhouse-server.service

"${CH[@]}" \
    --query "SELECT 1" \
    >/dev/null

observability_exists="$(
    "${CH[@]}" \
        --query "
            SELECT count()
            FROM system.databases
            WHERE name = 'observability'
        " \
        --format TabSeparatedRaw
)"

if [ "$observability_exists" != "0" ]; then
    die \
        "observability database already exists; " \
        "refusing clean-machine runtime installation"
fi

RENDERED="$TMPDIR/rendered"

mkdir -p "$RENDERED"

python3 \
    "$SCRIPT_DIR/render-configs.py" \
    --output-dir "$RENDERED"

echo "=== APPLY CLICKHOUSE SCHEMA ==="

for sql in \
    "$CLICKHOUSE_DIR/00-database.sql" \
    "$CLICKHOUSE_DIR/10-syslog.sql" \
    "$CLICKHOUSE_DIR/20-ai-updates.sql" \
    "$CLICKHOUSE_DIR/30-grafana-logs.sql" \
    "$RENDERED/40-access-control.sql"
do
    echo "applying=$(basename "$sql")"

    "${CH[@]}" \
        --multiquery \
        < "$sql"
done

echo
echo "=== VERIFY CLICKHOUSE OBJECTS ==="

"${CH[@]}" \
    --query "
        SELECT
            name,
            engine
        FROM system.tables
        WHERE database = 'observability'
        ORDER BY name
        FORMAT TabSeparated
    "

object_count="$(
    "${CH[@]}" \
        --query "
            SELECT count()
            FROM system.tables
            WHERE database = 'observability'
              AND name IN (
                  'syslog',
                  'ai_updates',
                  'grafana_logs'
              )
        " \
        --format TabSeparatedRaw
)"

[ "$object_count" = "3" ] \
    || die "expected three ClickHouse observability objects"

echo
echo "=== INSTALL TRANSPORT FILESYSTEM/SSH BOUNDARY ==="

"$FILESYSTEM_DIR/bootstrap-transport.sh"

echo
echo "=== INSTALL AI RESULT GATE ==="

install \
    -o root \
    -g root \
    -m 0755 \
    "$SBIN_DIR/ai-results-gate" \
    /usr/local/sbin/ai-results-gate

install \
    -o root \
    -g root \
    -m 0644 \
    "$SYSTEMD_DIR/ai-results-gate.service" \
    /etc/systemd/system/ai-results-gate.service

install \
    -o root \
    -g root \
    -m 0644 \
    "$SYSTEMD_DIR/ai-results-gate.timer" \
    /etc/systemd/system/ai-results-gate.timer

echo
echo "=== INSTALL AI SPOOL RETENTION ==="

install \
    -o root \
    -g root \
    -m 0755 \
    "$SBIN_DIR/vector-ai-agent-retention-policy" \
    /usr/local/sbin/vector-ai-agent-retention-policy

install \
    -o root \
    -g root \
    -m 0644 \
    "$SYSTEMD_DIR/vector-ai-agent-retention-policy.service" \
    /etc/systemd/system/vector-ai-agent-retention-policy.service

install \
    -o root \
    -g root \
    -m 0644 \
    "$SYSTEMD_DIR/vector-ai-agent-retention-policy.timer" \
    /etc/systemd/system/vector-ai-agent-retention-policy.timer

echo
echo "=== INSTALL VECTOR CONFIGURATION ==="

install \
    -d \
    -o vector \
    -g vector \
    -m 0700 \
    /etc/vector/secrets

install \
    -o vector \
    -g vector \
    -m 0400 \
    "$VECTOR_INGEST_PASSWORD_FILE" \
    /etc/vector/secrets/clickhouse_password

install \
    -o root \
    -g root \
    -m 0644 \
    "$RENDERED/vector.yaml" \
    /etc/vector/vector.yaml

vector validate \
    /etc/vector/vector.yaml

echo
echo "=== INSTALL GRAFANA DATASOURCE ==="

install \
    -d \
    -o root \
    -g grafana \
    -m 0750 \
    /etc/grafana/provisioning/datasources

install \
    -o root \
    -g grafana \
    -m 0640 \
    "$RENDERED/clickhouse-datasources.yaml" \
    /etc/grafana/provisioning/datasources/clickhouse.yaml

echo
echo "=== BOOTSTRAP GRAFANA ADMINISTRATOR ==="

GRAFANA_BOOTSTRAP_DROPIN_DIR="/etc/systemd/system/grafana-server.service.d"
GRAFANA_BOOTSTRAP_DROPIN="$GRAFANA_BOOTSTRAP_DROPIN_DIR/zz-bootstrap-loopback.conf"

command -v runuser >/dev/null 2>&1 || die "runuser is required for Grafana administrator bootstrap"
command -v ss >/dev/null 2>&1 || die "ss is required for Grafana bootstrap listener validation"

install -d -o root -g root -m 0755 "$GRAFANA_BOOTSTRAP_DROPIN_DIR"

systemctl stop grafana-server.service

printf '%s\n' '[Service]' 'Environment="GF_SERVER_PROTOCOL=http"' 'Environment="GF_SERVER_HTTP_ADDR=127.0.0.1"' 'Environment="GF_SERVER_HTTP_PORT=3000"' 'Environment="GF_SERVER_ROOT_URL=http://127.0.0.1:3000/"' > "$GRAFANA_BOOTSTRAP_DROPIN"

chmod 0644 "$GRAFANA_BOOTSTRAP_DROPIN"

systemctl daemon-reload

systemctl start grafana-server.service

grafana_bootstrap_ready=no

for attempt in $(seq 1 60); do
    if curl --fail --silent --show-error http://127.0.0.1:3000/api/health > "$TMPDIR/grafana-bootstrap-health.json"
    then
        grafana_bootstrap_ready=yes
        break
    fi

    sleep 1
done

[ "$grafana_bootstrap_ready" = "yes" ] || {
    echo "ERROR: Grafana bootstrap health endpoint did not become ready" >&2
    false
}

grafana_bootstrap_listeners="$(
    ss -H -ltn 'sport = :3000' \
        | awk '{print $4}' \
        | sort -u
)"

[ "$grafana_bootstrap_listeners" = "127.0.0.1:3000" ] || {
    echo "ERROR: Grafana bootstrap listener is not loopback-only" >&2
    printf 'listeners=%s\n' "$grafana_bootstrap_listeners" >&2
    false
}

echo "grafana_bootstrap_listener=127.0.0.1:3000"

python3 -c 'import json, sys; from pathlib import Path; data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8", errors="strict")); database = str(data.get("database", "")).lower(); sys.exit("ERROR: Grafana bootstrap health reports database != ok") if database != "ok" else print("grafana_bootstrap_database=ok")' "$TMPDIR/grafana-bootstrap-health.json"

systemctl stop grafana-server.service

[ -s /var/lib/grafana/grafana.db ] || {
    echo "ERROR: Grafana database was not initialized" >&2
    false
}

grafana_db_owner="$(
    stat -c '%U:%G' /var/lib/grafana/grafana.db
)"

[ "$grafana_db_owner" = "grafana:grafana" ] || {
    echo "ERROR: unexpected Grafana database ownership: $grafana_db_owner" >&2
    false
}

(
    cd /usr/share/grafana

    runuser \
        -u grafana \
        -- \
        /usr/share/grafana/bin/grafana \
        cli \
        --homepath /usr/share/grafana \
        --config /etc/grafana/grafana.ini \
        --configOverrides "cfg:default.paths.data=/var/lib/grafana" \
        admin \
        reset-admin-password \
        --user-id 1 \
        --password-from-stdin \
        < "$GRAFANA_ADMIN_PASSWORD_FILE"
)

grafana_admin_count="$(
    sqlite3 /var/lib/grafana/grafana.db \
        "SELECT count(*) FROM user WHERE id = 1;"
)"

[ "$grafana_admin_count" = "1" ] || {
    echo "ERROR: expected Grafana administrator user ID 1" >&2
    false
}

grafana_db_check="$(
    sqlite3 /var/lib/grafana/grafana.db \
        "PRAGMA quick_check;"
)"

[ "$grafana_db_check" = "ok" ] || {
    echo "ERROR: Grafana database quick_check failed" >&2
    false
}

grafana_db_owner="$(
    stat -c '%U:%G' /var/lib/grafana/grafana.db
)"

[ "$grafana_db_owner" = "grafana:grafana" ] || {
    echo "ERROR: Grafana CLI changed database ownership: $grafana_db_owner" >&2
    false
}

echo "grafana_admin_user_id=1"
echo "grafana_admin_password_reset=PASS"
echo "grafana_database_quick_check=PASS"

rm -f "$GRAFANA_BOOTSTRAP_DROPIN"
systemctl daemon-reload

echo "grafana_bootstrap_override_removed=yes"
echo "GRAFANA_ADMIN_BOOTSTRAP=PASS"

echo
echo "=== OBTAIN/REUSE GRAFANA CERTIFICATE ==="

CERT_LINEAGE="/etc/letsencrypt/live/$CERT_NAME"

if [ ! -s "$CERT_LINEAGE/fullchain.pem" ] \
    || [ ! -s "$CERT_LINEAGE/privkey.pem" ]
then
    echo \
        "ACME standalone validation requires TCP/80 " \
        "to reach this collector."

    certbot \
        certonly \
        --non-interactive \
        --agree-tos \
        --email "$CERTBOT_EMAIL" \
        --preferred-profile shortlived \
        --standalone \
        --ip-address "$GRAFANA_PUBLIC_HOST" \
        --cert-name "$CERT_NAME"
fi

[ -s "$CERT_LINEAGE/fullchain.pem" ] \
    || die "Grafana certificate full chain is missing"

[ -s "$CERT_LINEAGE/privkey.pem" ] \
    || die "Grafana certificate private key is missing"

install \
    -d \
    -o grafana \
    -g grafana \
    -m 0750 \
    /etc/grafana/tls

install \
    -o grafana \
    -g grafana \
    -m 0440 \
    "$CERT_LINEAGE/fullchain.pem" \
    /etc/grafana/tls/fullchain.pem

install \
    -o grafana \
    -g grafana \
    -m 0400 \
    "$CERT_LINEAGE/privkey.pem" \
    /etc/grafana/tls/privkey.pem

echo
echo "=== INSTALL GRAFANA HTTPS OVERRIDE ==="

install \
    -d \
    -o root \
    -g root \
    -m 0755 \
    /etc/systemd/system/grafana-server.service.d

install \
    -o root \
    -g root \
    -m 0644 \
    "$RENDERED/grafana-https.conf" \
    /etc/systemd/system/grafana-server.service.d/https.conf

echo
echo "=== INSTALL CERTBOT RENEWAL ==="

install \
    -d \
    -o root \
    -g root \
    -m 0755 \
    /etc/letsencrypt/renewal-hooks/deploy

install \
    -o root \
    -g root \
    -m 0755 \
    "$RENDERED/10-grafana-cert" \
    /etc/letsencrypt/renewal-hooks/deploy/10-grafana-cert

install \
    -o root \
    -g root \
    -m 0644 \
    "$CERTBOT_DIR/systemd/certbot-renew.service" \
    /etc/systemd/system/certbot-renew.service

install \
    -o root \
    -g root \
    -m 0644 \
    "$CERTBOT_DIR/systemd/certbot-renew.timer" \
    /etc/systemd/system/certbot-renew.timer

echo
echo "=== ACTIVATE SERVICES ==="

systemctl daemon-reload

systemctl enable \
    vector.service \
    grafana-server.service \
    ai-results-gate.timer \
    vector-ai-agent-retention-policy.timer \
    certbot-renew.timer

systemctl restart clickhouse-server.service
systemctl restart vector.service
systemctl restart grafana-server.service

systemctl start ai-results-gate.timer
systemctl start vector-ai-agent-retention-policy.timer
systemctl start certbot-renew.timer

for service in \
    clickhouse-server.service \
    vector.service \
    grafana-server.service
do
    systemctl is-active --quiet "$service" \
        || die "$service is not active"
done

for timer in \
    ai-results-gate.timer \
    vector-ai-agent-retention-policy.timer \
    certbot-renew.timer
do
    systemctl is-enabled --quiet "$timer" \
        || die "$timer is not enabled"

    systemctl is-active --quiet "$timer" \
        || die "$timer is not active"
done

echo
echo "=== GRAFANA HEALTH ==="

grafana_ready=no

for attempt in $(seq 1 30); do
    if curl \
        --insecure \
        --fail \
        --silent \
        --show-error \
        https://127.0.0.1:443/api/health \
        > "$TMPDIR/grafana-health.json"
    then
        grafana_ready=yes
        break
    fi

    sleep 1
done

[ "$grafana_ready" = "yes" ] \
    || die "Grafana HTTPS health endpoint did not become ready"

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

database = str(
    data.get(
        "database",
        "",
    )
).lower()

if database != "ok":
    raise SystemExit(
        "ERROR: Grafana health reports database != ok"
    )

print("grafana_database=ok")
PY

echo
echo "=== GRAFANA DATASOURCE PROVISIONING ==="

datasource_count="$(
    sqlite3 \
        /var/lib/grafana/grafana.db \
        "
        SELECT count(*)
        FROM data_source
        WHERE uid IN (
            'efvaztlrk8ow0a',
            'bfvik20ilwoaof'
        );
        "
)"

[ "$datasource_count" = "2" ] \
    || die "expected both Grafana ClickHouse datasources"

echo "grafana_clickhouse_datasources=2"

echo
echo "=== RESTORE GRAFANA DASHBOARDS ==="

python3 -B \
    "$GRAFANA_DIR/scripts/restore-dashboards.py" \
    --dashboard-dir "$GRAFANA_DIR/dashboards" \
    --base-url "https://127.0.0.1:443" \
    --username admin \
    --password-file "$GRAFANA_ADMIN_PASSWORD_FILE"

echo
echo "=== VERIFY GRAFANA DASHBOARDS ==="

python3 -B \
    "$GRAFANA_DIR/scripts/verify-dashboards.py" \
    --dashboard-dir "$GRAFANA_DIR/dashboards" \
    --base-url "https://127.0.0.1:443" \
    --username admin \
    --password-file "$GRAFANA_ADMIN_PASSWORD_FILE"

echo
echo "=== SSH RELOAD POLICY ==="

if [ "${RELOAD_SSH:-no}" = "yes" ]; then
    sshd -t
    systemctl reload ssh.service
    echo "ssh_reload=performed"
else
    echo "ssh_reload=deferred"
    echo \
        "Run 'sshd -t' and reload ssh.service only after " \
        "confirming access to the configured SSH port."
fi

echo
echo "COLLECTOR_RUNTIME_INSTALL=PASS"
