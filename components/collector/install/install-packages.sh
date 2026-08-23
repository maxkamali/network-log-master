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

require_file()
{
    [ -f "$1" ] \
        || die "required file missing: $1"
}

require_root

[ "${CLEAN_INSTALL_CONFIRM:-}" = "YES-CLEAN-COLLECTOR" ] \
    || die "CLEAN_INSTALL_CONFIRM must equal YES-CLEAN-COLLECTOR"

SCRIPT_DIR="$(
    cd "$(
        dirname "${BASH_SOURCE[0]}"
    )" \
        && pwd
)"

VERSIONS="$SCRIPT_DIR/versions.env"

require_file "$VERSIONS"

set -a
. "$VERSIONS"
set +a

: "${VECTOR_VERSION:?}"
: "${CLICKHOUSE_VERSION:?}"
: "${GRAFANA_VERSION:?}"
: "${GRAFANA_CLICKHOUSE_PLUGIN_VERSION:?}"
: "${CERTBOT_VERSION:?}"

if [ ! -r /etc/os-release ]; then
    die "/etc/os-release is unavailable"
fi

. /etc/os-release

[ "${ID:-}" = "debian" ] \
    || die "collector package bootstrap expects Debian"

case "${VERSION_ID:-}" in
    13|13.*)
        ;;
    *)
        die "collector package bootstrap expects Debian 13"
        ;;
esac

ARCH="$(
    dpkg --print-architecture
)"

[ "$ARCH" = "amd64" ] \
    || die "collector package bootstrap expects amd64"

TMPDIR="$(
    mktemp -d
)"

POLICY_RC_D="/usr/sbin/policy-rc.d"
POLICY_RC_D_EXPECTED="$TMPDIR/policy-rc.d.expected"
POLICY_RC_D_MANAGED=no

PACKAGE_NO_AUTOSTART_DROPIN="90-collector-rebuild-no-autostart.conf"
PACKAGE_NO_AUTOSTART_CONDITION="/run/collector-rebuild/runtime-service-start-authorized"
PACKAGE_NO_AUTOSTART_EXPECTED="$TMPDIR/package-no-autostart.expected"

cat > "$POLICY_RC_D_EXPECTED" <<'PACKAGE_POLICY_RC_D_EXPECTED'
#!/bin/sh
# Collector rebuild package-install no-autostart guard.
exit 101
PACKAGE_POLICY_RC_D_EXPECTED

cat > "$PACKAGE_NO_AUTOSTART_EXPECTED" <<PACKAGE_NO_AUTOSTART_EXPECTED
[Unit]
ConditionPathExists=$PACKAGE_NO_AUTOSTART_CONDITION
PACKAGE_NO_AUTOSTART_EXPECTED

cleanup()
{
    if [ "${POLICY_RC_D_MANAGED:-no}" = "yes" ] \
        && [ -e "$POLICY_RC_D" ] \
        && cmp -s \
            "$POLICY_RC_D_EXPECTED" \
            "$POLICY_RC_D"
    then
        rm -f "$POLICY_RC_D"
    fi

    rm -rf "$TMPDIR"
}

trap cleanup EXIT

install_policy_rc_d_guard()
{
    if [ -e "$POLICY_RC_D" ] \
        || [ -L "$POLICY_RC_D" ]
    then
        cmp -s \
            "$POLICY_RC_D_EXPECTED" \
            "$POLICY_RC_D" \
            || die \
                "existing /usr/sbin/policy-rc.d is not the managed collector rebuild guard"

        echo "policy_rc_d_guard=reusing-managed"
    else
        install \
            -o root \
            -g root \
            -m 0755 \
            "$POLICY_RC_D_EXPECTED" \
            "$POLICY_RC_D"

        echo "policy_rc_d_guard=installed"
    fi

    POLICY_RC_D_MANAGED=yes
}

remove_policy_rc_d_guard()
{
    [ "$POLICY_RC_D_MANAGED" = "yes" ] \
        || return

    [ -e "$POLICY_RC_D" ] \
        || die \
            "managed /usr/sbin/policy-rc.d disappeared during package installation"

    cmp -s \
        "$POLICY_RC_D_EXPECTED" \
        "$POLICY_RC_D" \
        || die \
            "managed /usr/sbin/policy-rc.d changed during package installation"

    rm -f "$POLICY_RC_D"
    POLICY_RC_D_MANAGED=no
}

install_service_no_autostart_guard()
{
    local unit="$1"
    local directory
    local path

    directory="/etc/systemd/system/${unit}.d"
    path="$directory/$PACKAGE_NO_AUTOSTART_DROPIN"

    install \
        -d \
        -o root \
        -g root \
        -m 0755 \
        "$directory"

    if [ -e "$path" ] \
        || [ -L "$path" ]
    then
        cmp -s \
            "$PACKAGE_NO_AUTOSTART_EXPECTED" \
            "$path" \
            || die \
                "unexpected existing no-autostart guard for $unit"
    else
        install \
            -o root \
            -g root \
            -m 0644 \
            "$PACKAGE_NO_AUTOSTART_EXPECTED" \
            "$path"
    fi

    echo "package_no_autostart_guard=$unit"
}

command -v systemctl >/dev/null 2>&1 \
    || die "systemctl is required for package no-autostart protection"

[ ! -e "$PACKAGE_NO_AUTOSTART_CONDITION" ] \
    || die \
        "package no-autostart release condition unexpectedly exists"

SSH_MANAGEMENT_WAS_ACTIVE=no

if systemctl is-active --quiet ssh.service \
    || systemctl is-active --quiet ssh.socket
then
    SSH_MANAGEMENT_WAS_ACTIVE=yes
fi

install_policy_rc_d_guard

for unit in \
    vector.service \
    clickhouse-server.service \
    grafana-server.service
do
    install_service_no_autostart_guard "$unit"
done

if [ "$SSH_MANAGEMENT_WAS_ACTIVE" = "no" ]; then
    install_service_no_autostart_guard ssh.service
    install_service_no_autostart_guard ssh.socket
    echo "ssh_management_plane=held-inactive"
else
    echo "ssh_management_plane=preserve-existing-active"
fi

systemctl daemon-reload

export DEBIAN_FRONTEND=interactive

apt-get update

apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    wget \
    zstd \
    jq \
    acl \
    openssh-server \
    python3 \
    python3-dev \
    python3-venv \
    libaugeas-dev \
    gcc

curl \
    -fsSL \
    https://setup.vector.dev \
    -o "$TMPDIR/vector-repository-setup.sh"

bash \
    "$TMPDIR/vector-repository-setup.sh"

[ -f /usr/share/keyrings/datadog-archive-keyring.gpg ] \
    || die "Vector repository keyring was not installed"

cat > /etc/apt/sources.list.d/vector.list <<'EOF'
deb [signed-by=/usr/share/keyrings/datadog-archive-keyring.gpg] https://apt.vector.dev/ stable vector-0
EOF

curl \
    -fsSL \
    https://packages.clickhouse.com/rpm/lts/repodata/repomd.xml.key \
    -o "$TMPDIR/clickhouse-key"

gpg \
    --dearmor \
    --yes \
    -o /usr/share/keyrings/clickhouse-keyring.gpg \
    "$TMPDIR/clickhouse-key"

chmod 0644 \
    /usr/share/keyrings/clickhouse-keyring.gpg

cat > /etc/apt/sources.list.d/clickhouse.list <<EOF
deb [signed-by=/usr/share/keyrings/clickhouse-keyring.gpg arch=${ARCH}] https://packages.clickhouse.com/deb lts main
EOF

install \
    -d \
    -o root \
    -g root \
    -m 0755 \
    /etc/apt/keyrings

curl \
    -fsSL \
    https://apt.grafana.com/gpg-full.key \
    -o /etc/apt/keyrings/grafana.asc

chmod 0644 \
    /etc/apt/keyrings/grafana.asc

cat > /etc/apt/sources.list.d/grafana.list <<'EOF'
deb [signed-by=/etc/apt/keyrings/grafana.asc] https://apt.grafana.com stable main
EOF

apt-get update

require_available_version()
{
    local package="$1"
    local wanted="$2"

    if ! apt-cache madison "$package" \
        | awk -F'|' -v wanted="$wanted" '
            {
                value = $2
                gsub(
                    /^[[:space:]]+|[[:space:]]+$/,
                    "",
                    value
                )

                if (value == wanted) {
                    found = 1
                }
            }

            END {
                exit(found ? 0 : 1)
            }
        '
    then
        die "$package version $wanted is not available"
    fi
}

require_available_version \
    vector \
    "$VECTOR_VERSION"

require_available_version \
    clickhouse-server \
    "$CLICKHOUSE_VERSION"

require_available_version \
    clickhouse-client \
    "$CLICKHOUSE_VERSION"

require_available_version \
    grafana \
    "$GRAFANA_VERSION"

echo
echo "ClickHouse package installation may request the"
echo "fresh default administrative password locally."
echo "Do not reuse or record an existing deployment password."
echo

apt-get install \
    -y \
    --allow-downgrades \
    "vector=${VECTOR_VERSION}" \
    "clickhouse-server=${CLICKHOUSE_VERSION}" \
    "clickhouse-client=${CLICKHOUSE_VERSION}" \
    "grafana=${GRAFANA_VERSION}"

actual_version()
{
    dpkg-query \
        -W \
        -f='${Version}' \
        "$1"
}

[ "$(actual_version vector)" = "$VECTOR_VERSION" ] \
    || die "Vector version differs after installation"

[ "$(actual_version clickhouse-server)" = "$CLICKHOUSE_VERSION" ] \
    || die "ClickHouse server version differs after installation"

[ "$(actual_version clickhouse-client)" = "$CLICKHOUSE_VERSION" ] \
    || die "ClickHouse client version differs after installation"

[ "$(actual_version grafana)" = "$GRAFANA_VERSION" ] \
    || die "Grafana version differs after installation"

rm -rf /opt/certbot

python3 \
    -m venv \
    /opt/certbot

/opt/certbot/bin/pip \
    install \
    --upgrade \
    pip

/opt/certbot/bin/pip \
    install \
    "certbot==${CERTBOT_VERSION}"

ln \
    -sfn \
    /opt/certbot/bin/certbot \
    /usr/local/bin/certbot

actual_certbot="$(
    /usr/local/bin/certbot --version \
        | awk '{print $2}'
)"

[ "$actual_certbot" = "$CERTBOT_VERSION" ] \
    || die "Certbot version differs after installation"

GRAFANA_CLI=""

if command -v grafana >/dev/null 2>&1; then
    GRAFANA_CLI="grafana cli"
elif command -v grafana-cli >/dev/null 2>&1; then
    GRAFANA_CLI="grafana-cli"
else
    die "Grafana CLI not found"
fi

if [ "$GRAFANA_CLI" = "grafana cli" ]; then
    grafana cli plugins install \
        grafana-clickhouse-datasource \
        "$GRAFANA_CLICKHOUSE_PLUGIN_VERSION"
else
    grafana-cli plugins install \
        grafana-clickhouse-datasource \
        "$GRAFANA_CLICKHOUSE_PLUGIN_VERSION"
fi

PLUGIN_JSON="/var/lib/grafana/plugins/grafana-clickhouse-datasource/plugin.json"

[ -f "$PLUGIN_JSON" ] \
    || die "Grafana ClickHouse plugin was not installed"

python3 - "$PLUGIN_JSON" "$GRAFANA_CLICKHOUSE_PLUGIN_VERSION" <<'PY'
from pathlib import Path
import json
import sys

path = Path(sys.argv[1])
expected = sys.argv[2]

data = json.loads(
    path.read_text(
        encoding="utf-8",
        errors="strict",
    )
)

actual = str(
    (data.get("info") or {}).get(
        "version",
        "",
    )
)

if actual != expected:
    raise SystemExit(
        f"ERROR: plugin version expected={expected} "
        f"actual={actual}"
    )
PY

echo
echo "=== VERIFY PACKAGE NO-AUTOSTART HOLD ==="

systemctl daemon-reload

for unit in \
    vector.service \
    clickhouse-server.service \
    grafana-server.service
do
    guard="/etc/systemd/system/${unit}.d/$PACKAGE_NO_AUTOSTART_DROPIN"

    [ -f "$guard" ] \
        || die \
            "package no-autostart guard missing for $unit"

    cmp -s \
        "$PACKAGE_NO_AUTOSTART_EXPECTED" \
        "$guard" \
        || die \
            "package no-autostart guard changed for $unit"

    if systemctl is-active --quiet "$unit"; then
        die \
            "$unit became active before runtime configuration"
    fi

    enabled_state="$(
        systemctl is-enabled "$unit" \
            2>/dev/null \
            || true
    )"

    echo \
        "unit=$unit" \
        "active=inactive" \
        "guard=present" \
        "enabled=$enabled_state"
done

if [ "$SSH_MANAGEMENT_WAS_ACTIVE" = "no" ]; then
    for unit in \
        ssh.service \
        ssh.socket
    do
        guard="/etc/systemd/system/${unit}.d/$PACKAGE_NO_AUTOSTART_DROPIN"

        [ -f "$guard" ] \
            || die \
                "package no-autostart guard missing for $unit"

        cmp -s \
            "$PACKAGE_NO_AUTOSTART_EXPECTED" \
            "$guard" \
            || die \
                "package no-autostart guard changed for $unit"

        if systemctl is-active --quiet "$unit"; then
            die \
                "$unit became active despite package no-autostart protection"
        fi
    done

    echo "ssh_package_no_autostart_hold=PASS"
else
    echo "ssh_existing_management_plane_preserved=yes"
fi

remove_policy_rc_d_guard

[ ! -e "$POLICY_RC_D" ] \
    || die \
        "temporary package policy guard was not removed"

echo "policy_rc_d_guard_removed=yes"
echo "PACKAGE_NO_AUTOSTART_HOLD=PASS"

echo
echo "COLLECTOR_PACKAGE_INSTALL=PASS"
echo "Packages are installed but collector application services remain held until runtime configuration releases them."
