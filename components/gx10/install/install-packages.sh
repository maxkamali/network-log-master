#!/usr/bin/env bash
set -euo pipefail

die()
{
    echo "ERROR: $*" >&2
    exit 1
}

[ "${EUID}" -eq 0 ] || die "run this clean-machine installer as root"
[ "${CLEAN_INSTALL_CONFIRM:-}" = "YES-CLEAN-GX10" ] \
    || die "CLEAN_INSTALL_CONFIRM must equal YES-CLEAN-GX10"

SCRIPT_DIR="$(
    cd "$(dirname "${BASH_SOURCE[0]}")" \
        && pwd
)"

. "$SCRIPT_DIR/versions.env"
. /etc/os-release

[ "${ID:-}" = "$GX10_OS_ID" ] || die "unexpected operating system"
case "${VERSION_ID:-}" in
    "$GX10_OS_VERSION"|"$GX10_OS_VERSION".*)
        ;;
    *)
        die "unexpected operating-system version"
        ;;
esac

[ "$(dpkg --print-architecture)" = "$GX10_ARCH" ] \
    || die "unexpected architecture"

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install \
    --yes \
    --no-install-recommends \
    "$GX10_PYTHON_PACKAGE=$GX10_PYTHON_PACKAGE_VERSION" \
    "$GX10_OPENSSH_PACKAGE=$GX10_OPENSSH_PACKAGE_VERSION" \
    "$GX10_ZSTD_PACKAGE=$GX10_ZSTD_PACKAGE_VERSION"

echo "GX10_PACKAGE_INSTALL=PASS"
