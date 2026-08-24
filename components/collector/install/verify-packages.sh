#!/usr/bin/env bash
set -euo pipefail

die()
{
    echo "FAIL: $*" >&2
    exit 1
}

require_root()
{
    [ "${EUID}" -eq 0 ] \
        || die "run this verifier as root"
}

ROOT_COMMAND_PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

require_installed_package()
{
    local package="$1"
    local status

    status="$(
        dpkg-query \
            -W \
            -f='${Status}' \
            "$package" \
            2>/dev/null
    )" \
        || die "$package is not installed"

    [ "$status" = "install ok installed" ] \
        || die "$package status differs: $status"

    echo "dependency_package=$package installed=yes"
}

require_command()
{
    local name="$1"
    local path
    local PATH="$ROOT_COMMAND_PATH"

    path="$(
        command -v "$name" \
            2>/dev/null \
            || true
    )"

    [ -n "$path" ] \
        || die "required command not found: $name"

    echo "dependency_command=$name path=$path"
}

require_root

SCRIPT_DIR="$(
    cd "$(
        dirname "${BASH_SOURCE[0]}"
    )" \
        && pwd
)"

set -a
. "$SCRIPT_DIR/versions.env"
set +a

require_version()
{
    local package="$1"
    local expected="$2"
    local actual

    actual="$(
        dpkg-query \
            -W \
            -f='${Version}' \
            "$package" \
            2>/dev/null
    )" \
        || die "$package is not installed"

    [ "$actual" = "$expected" ] \
        || die "$package expected=$expected actual=$actual"

    echo \
        "package=$package" \
        "version=$actual"
}

for package in \
    iproute2 \
    sqlite3
do
    require_installed_package "$package"
done

for command_name in \
    ss \
    sqlite3
do
    require_command "$command_name"
done

require_version \
    vector \
    "$VECTOR_VERSION"

require_version \
    clickhouse-server \
    "$CLICKHOUSE_VERSION"

require_version \
    clickhouse-client \
    "$CLICKHOUSE_VERSION"

require_version \
    grafana \
    "$GRAFANA_VERSION"

require_version \
    python3 \
    "$PYTHON3_VERSION"

require_version \
    zstd \
    "$ZSTD_VERSION"

actual_certbot="$(
    /usr/local/bin/certbot --version \
        | awk '{print $2}'
)"

[ "$actual_certbot" = "$CERTBOT_VERSION" ] \
    || die \
        "certbot expected=$CERTBOT_VERSION actual=$actual_certbot"

echo "certbot_version=$actual_certbot"

PLUGIN_JSON="/var/lib/grafana/plugins/grafana-clickhouse-datasource/plugin.json"

[ -f "$PLUGIN_JSON" ] \
    || die "Grafana ClickHouse plugin is missing"

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

plugin_id = str(
    data.get(
        "id",
        "",
    )
)

actual = str(
    (data.get("info") or {}).get(
        "version",
        "",
    )
)

if plugin_id != "grafana-clickhouse-datasource":
    raise SystemExit(
        "FAIL: unexpected Grafana plugin ID"
    )

if actual != expected:
    raise SystemExit(
        f"FAIL: Grafana plugin expected={expected} "
        f"actual={actual}"
    )

print(
    f"grafana_plugin={plugin_id} "
    f"version={actual}"
)
PY

for file in \
    /etc/apt/sources.list.d/vector.list \
    /etc/apt/sources.list.d/clickhouse.list \
    /etc/apt/sources.list.d/grafana.list
do
    [ -s "$file" ] \
        || die "repository definition missing: $file"
done

echo "COLLECTOR_PACKAGE_VERIFY=PASS"
