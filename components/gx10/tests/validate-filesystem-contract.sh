#!/usr/bin/env bash
set -euo pipefail

die()
{
    echo "ERROR: $*" >&2
    exit 1
}

SCRIPT_DIR="$(
    cd "$(dirname "${BASH_SOURCE[0]}")" \
        && pwd
)"

GX10_DIR="$(
    cd "$SCRIPT_DIR/.." \
        && pwd
)"

INSTALLER="$GX10_DIR/install/install-filesystem.sh"
CONTRACT="$GX10_DIR/install/filesystem-contract.env"
EXAMPLE="$GX10_DIR/config/operator-inputs.env.example"

for path in "$INSTALLER" "$CONTRACT" "$EXAMPLE"; do
    [ -f "$path" ] || die "required artifact missing: $path"
done

bash -n "$INSTALLER"

set -a
. "$CONTRACT"
set +a

[ "$GX10_RUNTIME_USER" = network-log-agent ] || die "unexpected public runtime user"
[ "$GX10_RUNTIME_GROUP" = network-log-agent ] || die "unexpected public runtime group"
[ "$GX10_RUNTIME_HOME" = /var/lib/network-log-gx10 ] || die "unexpected runtime home"
[ "$GX10_SSH_DIR" = "$GX10_RUNTIME_HOME/.ssh" ] || die "SSH directory is outside runtime home"
[ "$GX10_STATE_DIR" = "$GX10_RUNTIME_HOME/state" ] || die "state directory is outside runtime home"
[ "$GX10_DATABASE_PATH" = "$GX10_STATE_DIR/events.sqlite3" ] || die "database path is outside state directory"
[ "$GX10_INCOMING_DIR" = "$GX10_SPOOL_DIR/incoming" ] || die "incoming directory is outside spool"
[ "$GX10_PROCESSED_DIR" = "$GX10_SPOOL_DIR/processed" ] || die "processed directory is outside spool"
[ "$GX10_TEMP_DIR" = "$GX10_SPOOL_DIR/tmp" ] || die "temporary directory is outside spool"

grep -Fq 'YES-CLEAN-GX10' "$INSTALLER" || die "clean-machine confirmation guard missing"
grep -Fq 'refuses an existing application database' "$INSTALLER" || die "existing-database refusal missing"
grep -Fq 'mode 0400 or 0600' "$INSTALLER" || die "private-input mode validation missing"
grep -Fq ' -m 0700 ' "$INSTALLER" || die "SSH directory mode contract missing"
[ "$(grep -Fc ' -m 0750 ' "$INSTALLER")" -ge 6 ] || die "runtime directory mode contracts missing"
grep -Fq ' -m 0600 ' "$INSTALLER" || die "private-file mode contract missing"
grep -Fq '/usr/sbin/nologin' "$INSTALLER" || die "non-login shell contract missing"
grep -Fq 'usermod --lock' "$INSTALLER" || die "runtime account lock missing"

grep -Fq 'collector.example.invalid' "$EXAMPLE" || die "synthetic collector hostname missing"

private_key_pattern='-----BEGIN ''([A-Z0-9 ]+)?PRIVATE[[:space:]]KEY-----'
github_token_pattern='github''_pat_|gh''[pousr]_[A-Za-z0-9_]{20,}'

if grep -aERq -- \
    "$private_key_pattern|$github_token_pattern" \
    "$GX10_DIR"
then
    die "secret-like content detected"
fi

if find "$GX10_DIR" -type f \( -name '*.key' -o -name 'token.txt' -o -name '*.sqlite' -o -name '*.sqlite3' \) -print -quit | grep -q .; then
    die "private/generated file detected"
fi

echo "GX10_FILESYSTEM_CONTRACT_VALIDATION=PASS"
