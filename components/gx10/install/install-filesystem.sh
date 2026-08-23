#!/usr/bin/env bash
set -euo pipefail

die()
{
    echo "ERROR: $*" >&2
    exit 1
}

require_command()
{
    command -v "$1" >/dev/null 2>&1 \
        || die "required command not found: $1"
}

require_root()
{
    [ "${EUID}" -eq 0 ] \
        || die "run this clean-machine installer as root"
}

require_private_input()
{
    local path="$1"
    local label="$2"
    local mode

    [ -f "$path" ] \
        || die "$label source is not a regular file"

    [ ! -L "$path" ] \
        || die "$label source must not be a symbolic link"

    [ -s "$path" ] \
        || die "$label source is empty"

    mode="$(stat -c '%a' "$path")"

    case "$mode" in
        400|600)
            ;;
        *)
            die "$label source must have mode 0400 or 0600"
            ;;
    esac
}

install_or_verify_private_file()
{
    local source="$1"
    local destination="$2"

    if [ -e "$destination" ] || [ -L "$destination" ]; then
        [ ! -L "$destination" ] \
            || die "existing private destination must not be a symbolic link"

        [ -f "$destination" ] \
            || die "existing private destination is not a regular file"

        [ "$(stat -c '%h' "$destination")" -eq 1 ] \
            || die "existing private destination must not be hard-linked"

        cmp -s "$source" "$destination" \
            || die "existing private destination differs from operator input"

        chown "$GX10_RUNTIME_USER:$GX10_RUNTIME_GROUP" "$destination"
        chmod 0600 "$destination"
    else
        install \
            -o "$GX10_RUNTIME_USER" \
            -g "$GX10_RUNTIME_GROUP" \
            -m 0600 \
            "$source" \
            "$destination"
    fi
}

require_root

[ "${CLEAN_INSTALL_CONFIRM:-}" = "YES-CLEAN-GX10" ] \
    || die "CLEAN_INSTALL_CONFIRM must equal YES-CLEAN-GX10"

: "${GX10_SFTP_PRIVATE_KEY_FILE:?set GX10_SFTP_PRIVATE_KEY_FILE}"
: "${GX10_SFTP_KNOWN_HOSTS_FILE:?set GX10_SFTP_KNOWN_HOSTS_FILE}"

for command_name in \
    basename \
    chmod \
    chown \
    cmp \
    cut \
    getent \
    groupadd \
    id \
    install \
    stat \
    useradd \
    usermod \
    wc
do
    require_command "$command_name"
done

SCRIPT_DIR="$(
    cd "$(dirname "${BASH_SOURCE[0]}")" \
        && pwd
)"

CONTRACT="$SCRIPT_DIR/filesystem-contract.env"

[ -f "$CONTRACT" ] \
    || die "filesystem contract missing"

set -a
. "$CONTRACT"
set +a

for required_name in \
    GX10_RUNTIME_USER \
    GX10_RUNTIME_GROUP \
    GX10_RUNTIME_HOME \
    GX10_CONFIG_DIR \
    GX10_RUNTIME_CONFIG_PATH \
    GX10_SSH_DIR \
    GX10_PRIVATE_KEY_PATH \
    GX10_KNOWN_HOSTS_PATH \
    GX10_SPOOL_DIR \
    GX10_INCOMING_DIR \
    GX10_PROCESSED_DIR \
    GX10_TEMP_DIR \
    GX10_STATE_DIR \
    GX10_DATABASE_PATH \
    GX10_LIBEXEC_DIR
do
    [ -n "${!required_name:-}" ] \
        || die "filesystem contract value missing: $required_name"
done

require_private_input "$GX10_SFTP_PRIVATE_KEY_FILE" "SFTP private key"
require_private_input "$GX10_SFTP_KNOWN_HOSTS_FILE" "SFTP known-hosts"

if [ -e "$GX10_DATABASE_PATH" ] || [ -L "$GX10_DATABASE_PATH" ]; then
    die "clean-machine filesystem bootstrap refuses an existing application database"
fi

if ! getent group "$GX10_RUNTIME_GROUP" >/dev/null; then
    groupadd --system "$GX10_RUNTIME_GROUP"
fi

if getent passwd "$GX10_RUNTIME_USER" >/dev/null; then
    [ "$(id -gn "$GX10_RUNTIME_USER")" = "$GX10_RUNTIME_GROUP" ] \
        || die "existing runtime user has unexpected primary group"

    [ "$(getent passwd "$GX10_RUNTIME_USER" | cut -d: -f6)" = "$GX10_RUNTIME_HOME" ] \
        || die "existing runtime user has unexpected home"

    [ "$(basename "$(getent passwd "$GX10_RUNTIME_USER" | cut -d: -f7)")" = nologin ] \
        || die "existing runtime user has unexpected login shell"

    [ "$(id -Gn "$GX10_RUNTIME_USER" | wc -w)" -eq 1 ] \
        || die "existing runtime user has unexpected supplementary groups"
else
    useradd \
        --system \
        --gid "$GX10_RUNTIME_GROUP" \
        --home-dir "$GX10_RUNTIME_HOME" \
        --shell /usr/sbin/nologin \
        --no-create-home \
        "$GX10_RUNTIME_USER"
fi

usermod --lock "$GX10_RUNTIME_USER"

install -d -o root -g root -m 0755 "$GX10_LIBEXEC_DIR"
install -d -o root -g "$GX10_RUNTIME_GROUP" -m 0750 "$GX10_CONFIG_DIR"
install -d -o "$GX10_RUNTIME_USER" -g "$GX10_RUNTIME_GROUP" -m 0750 "$GX10_RUNTIME_HOME"
install -d -o "$GX10_RUNTIME_USER" -g "$GX10_RUNTIME_GROUP" -m 0700 "$GX10_SSH_DIR"
install -d -o "$GX10_RUNTIME_USER" -g "$GX10_RUNTIME_GROUP" -m 0750 "$GX10_SPOOL_DIR"
install -d -o "$GX10_RUNTIME_USER" -g "$GX10_RUNTIME_GROUP" -m 0750 "$GX10_INCOMING_DIR"
install -d -o "$GX10_RUNTIME_USER" -g "$GX10_RUNTIME_GROUP" -m 0750 "$GX10_PROCESSED_DIR"
install -d -o "$GX10_RUNTIME_USER" -g "$GX10_RUNTIME_GROUP" -m 0750 "$GX10_TEMP_DIR"
install -d -o "$GX10_RUNTIME_USER" -g "$GX10_RUNTIME_GROUP" -m 0750 "$GX10_STATE_DIR"

install_or_verify_private_file \
    "$GX10_SFTP_PRIVATE_KEY_FILE" \
    "$GX10_PRIVATE_KEY_PATH"

install_or_verify_private_file \
    "$GX10_SFTP_KNOWN_HOSTS_FILE" \
    "$GX10_KNOWN_HOSTS_PATH"

echo "GX10_FILESYSTEM_BOOTSTRAP=PASS"
