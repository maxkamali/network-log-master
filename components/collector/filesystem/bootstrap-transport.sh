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

if [ "${EUID}" -ne 0 ]; then
    die "run this script as root"
fi

: "${SSH_PORT:?set SSH_PORT to the deployment SSH port}"
: "${AI_SPOOL_READER_AUTHORIZED_KEYS_FILE:?set AI_SPOOL_READER_AUTHORIZED_KEYS_FILE}"
: "${AI_RESULTS_WRITER_AUTHORIZED_KEYS_FILE:?set AI_RESULTS_WRITER_AUTHORIZED_KEYS_FILE}"

case "$SSH_PORT" in
    ''|*[!0-9]*)
        die "SSH_PORT must be numeric"
        ;;
esac

if [ "$SSH_PORT" -lt 1 ] || [ "$SSH_PORT" -gt 65535 ]; then
    die "SSH_PORT must be between 1 and 65535"
fi

if [ "$SSH_PORT" -eq 22 ]; then
    die "collector rebuild expects a nonstandard SSH port"
fi

for command in \
    getent \
    groupadd \
    useradd \
    usermod \
    install \
    setfacl \
    getfacl \
    mount \
    findmnt \
    sshd \
    sed \
    grep \
    stat
do
    require_command "$command"
done

for key_file in \
    "$AI_SPOOL_READER_AUTHORIZED_KEYS_FILE" \
    "$AI_RESULTS_WRITER_AUTHORIZED_KEYS_FILE"
do
    [ -f "$key_file" ] \
        || die "authorized_keys source is not a regular file"

    [ -s "$key_file" ] \
        || die "authorized_keys source is empty"

    if grep -aEq -- \
        '-----BEGIN ([A-Z0-9 ]+)?PRIVATE[[:space:]]KEY-----' \
        "$key_file"
    then
        die "private key material supplied where a public authorized_keys file is required"
    fi
done

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

SSH_SOURCE="$REPO_ROOT/components/collector/ssh/sshd_config.d"
SYSTEMD_SOURCE="$REPO_ROOT/components/collector/systemd"
FSTAB_SOURCE="$SCRIPT_DIR/fstab-bind-mounts.conf"

for path in \
    "$SSH_SOURCE/00-collector-global.conf.in" \
    "$SSH_SOURCE/90-ai-spool-reader.conf" \
    "$SSH_SOURCE/91-ai-results-writer.conf" \
    "$SYSTEMD_SOURCE/ai-results-gate.service.d/10-rw-paths.conf" \
    "$FSTAB_SOURCE"
do
    [ -f "$path" ] \
        || die "required repository artifact missing: $path"
done

ensure_group()
{
    local group="$1"

    if ! getent group "$group" >/dev/null; then
        groupadd --system "$group"
    fi
}

ensure_user()
{
    local user="$1"
    local group="$2"
    local home="$3"
    local shell="$4"

    if getent passwd "$user" >/dev/null; then
        local actual_group
        local actual_home
        local actual_shell

        actual_group="$(
            id -gn "$user"
        )"

        actual_home="$(
            getent passwd "$user" \
                | cut -d: -f6
        )"

        actual_shell="$(
            getent passwd "$user" \
                | cut -d: -f7
        )"

        [ "$actual_group" = "$group" ] \
            || die "$user has unexpected primary group"

        [ "$actual_home" = "$home" ] \
            || die "$user has unexpected home"

        [ "$actual_shell" = "$shell" ] \
            || die "$user has unexpected shell"
    else
        useradd \
            --system \
            --gid "$group" \
            --home-dir "$home" \
            --shell "$shell" \
            --no-create-home \
            "$user"
    fi

    usermod --lock "$user"

    install \
        -d \
        -o "$user" \
        -g "$group" \
        -m 0700 \
        "$home"
}

clear_acl()
{
    local path="$1"

    setfacl -b "$path"
    setfacl -k "$path" 2>/dev/null || true
}

ensure_fstab_line()
{
    local line="$1"
    local source="$2"
    local target="$3"

    if grep -Fqx "$line" /etc/fstab; then
        return
    fi

    if awk \
        -v source="$source" \
        -v target="$target" \
        '
        $1 == source || $2 == target {
            found = 1
        }

        END {
            exit(found ? 0 : 1)
        }
        ' \
        /etc/fstab
    then
        die "conflicting /etc/fstab entry for $source or $target"
    fi

    printf '%s\n' "$line" >> /etc/fstab
}

require_mount_options()
{
    local target="$1"
    shift

    local options

    options="$(
        findmnt \
            -n \
            -o OPTIONS \
            --mountpoint "$target"
    )"

    for required in "$@"; do
        case ",$options," in
            *",$required,"*)
                ;;
            *)
                die "$target is missing mount option $required"
                ;;
        esac
    done
}

getent passwd vector >/dev/null \
    || die "vector account must exist before transport bootstrap"

getent group vector >/dev/null \
    || die "vector group must exist before transport bootstrap"

ensure_group ai_spool_readers
ensure_group ai_results_writer
ensure_group ai_results_gate

ensure_user \
    ai_spool_reader \
    ai_spool_readers \
    /var/lib/ai-spool-reader \
    /usr/sbin/nologin

ensure_user \
    ai_results_writer \
    ai_results_writer \
    /var/lib/ai-results-writer \
    /usr/sbin/nologin

ensure_user \
    ai_results_gate \
    ai_results_gate \
    /var/lib/ai-results-gate \
    /usr/sbin/nologin

install \
    -d \
    -o ai_spool_reader \
    -g ai_spool_readers \
    -m 0700 \
    /var/lib/ai-spool-reader/.ssh

install \
    -o ai_spool_reader \
    -g ai_spool_readers \
    -m 0600 \
    "$AI_SPOOL_READER_AUTHORIZED_KEYS_FILE" \
    /var/lib/ai-spool-reader/.ssh/authorized_keys

install \
    -d \
    -o ai_results_writer \
    -g ai_results_writer \
    -m 0700 \
    /var/lib/ai-results-writer/.ssh

install \
    -o ai_results_writer \
    -g ai_results_writer \
    -m 0600 \
    "$AI_RESULTS_WRITER_AUTHORIZED_KEYS_FILE" \
    /var/lib/ai-results-writer/.ssh/authorized_keys

install \
    -d \
    -o vector \
    -g vector \
    -m 0750 \
    /var/spool/vector-ai

clear_acl /var/spool/vector-ai

setfacl \
    -m \
    u::rwx,g::r-x,g:ai_spool_readers:r-x,m::r-x,o::--- \
    /var/spool/vector-ai

setfacl \
    -m \
    d:u::rwx,d:g::r-x,d:g:ai_spool_readers:r-x,d:m::r-x,d:o::--- \
    /var/spool/vector-ai

chown vector:vector /var/spool/vector-ai
chmod 0750 /var/spool/vector-ai

install \
    -d \
    -o root \
    -g vector \
    -m 0750 \
    /var/spool/ai-results

clear_acl /var/spool/ai-results

setfacl \
    -m \
    u::rwx,u:ai_results_gate:--x,g::r-x,m::r-x,o::--- \
    /var/spool/ai-results

chown root:vector /var/spool/ai-results
chmod 0750 /var/spool/ai-results

install \
    -d \
    -o root \
    -g vector \
    -m 2770 \
    /var/spool/ai-results/incoming

clear_acl /var/spool/ai-results/incoming

setfacl \
    -m \
    u::rwx,u:ai_results_gate:rwx,u:ai_results_writer:-wx,g::r-x,m::rwx,o::--- \
    /var/spool/ai-results/incoming

setfacl \
    -m \
    d:u::rwx,d:u:ai_results_gate:r--,d:g::r-x,d:m::r-x,d:o::--- \
    /var/spool/ai-results/incoming

chown root:vector /var/spool/ai-results/incoming
chmod 2770 /var/spool/ai-results/incoming

for path in \
    /var/spool/ai-results/ready \
    /var/spool/ai-results/rejected
do
    install \
        -d \
        -o root \
        -g vector \
        -m 2770 \
        "$path"

    clear_acl "$path"

    setfacl \
        -m \
        u::rwx,u:ai_results_gate:rwx,g::r-x,m::rwx,o::--- \
        "$path"

    chown root:vector "$path"
    chmod 2770 "$path"
done

install \
    -d \
    -o root \
    -g root \
    -m 0755 \
    /srv/ai-spool-reader

install \
    -d \
    -o root \
    -g root \
    -m 0755 \
    /srv/ai-results-writer

if ! findmnt \
    -rn \
    --mountpoint /srv/ai-spool-reader/spool \
    >/dev/null
then
    install \
        -d \
        -o root \
        -g root \
        -m 0755 \
        /srv/ai-spool-reader/spool
fi

if ! findmnt \
    -rn \
    --mountpoint /srv/ai-results-writer/incoming \
    >/dev/null
then
    install \
        -d \
        -o root \
        -g root \
        -m 0755 \
        /srv/ai-results-writer/incoming
fi

mapfile -t FSTAB_LINES < <(
    grep -Ev \
        '^[[:space:]]*(#|$)' \
        "$FSTAB_SOURCE"
)

[ "${#FSTAB_LINES[@]}" -eq 2 ] \
    || die "expected exactly two bind-mount definitions"

reader_line="$(
    printf '%s\n' "${FSTAB_LINES[@]}" \
        | awk '
            $1 == "/var/spool/vector-ai" &&
            $2 == "/srv/ai-spool-reader/spool" {
                print
            }
        '
)"

writer_line="$(
    printf '%s\n' "${FSTAB_LINES[@]}" \
        | awk '
            $1 == "/var/spool/ai-results/incoming" &&
            $2 == "/srv/ai-results-writer/incoming" {
                print
            }
        '
)"

[ -n "$reader_line" ] \
    || die "reader bind-mount definition missing"

[ -n "$writer_line" ] \
    || die "writer bind-mount definition missing"

ensure_fstab_line \
    "$reader_line" \
    /var/spool/vector-ai \
    /srv/ai-spool-reader/spool

ensure_fstab_line \
    "$writer_line" \
    /var/spool/ai-results/incoming \
    /srv/ai-results-writer/incoming

if ! findmnt \
    -rn \
    --mountpoint /srv/ai-spool-reader/spool \
    >/dev/null
then
    mount /srv/ai-spool-reader/spool
fi

mount \
    -o remount,bind,ro,nosuid,nodev,noexec \
    /srv/ai-spool-reader/spool

if ! findmnt \
    -rn \
    --mountpoint /srv/ai-results-writer/incoming \
    >/dev/null
then
    mount /srv/ai-results-writer/incoming
fi

mount \
    -o remount,bind,rw,nosuid,nodev,noexec \
    /srv/ai-results-writer/incoming

require_mount_options \
    /srv/ai-spool-reader/spool \
    ro \
    nosuid \
    nodev \
    noexec

require_mount_options \
    /srv/ai-results-writer/incoming \
    rw \
    nosuid \
    nodev \
    noexec

install \
    -d \
    -o root \
    -g root \
    -m 0755 \
    /etc/systemd/system/ai-results-gate.service.d

install \
    -o root \
    -g root \
    -m 0644 \
    "$SYSTEMD_SOURCE/ai-results-gate.service.d/10-rw-paths.conf" \
    /etc/systemd/system/ai-results-gate.service.d/10-rw-paths.conf

install \
    -d \
    -o root \
    -g root \
    -m 0755 \
    /etc/ssh/sshd_config.d

SSH_RENDERED="$(
    mktemp
)"

cleanup()
{
    rm -f "$SSH_RENDERED"
}

trap cleanup EXIT

sed \
    "s/__SSH_PORT__/${SSH_PORT}/g" \
    "$SSH_SOURCE/00-collector-global.conf.in" \
    > "$SSH_RENDERED"

if grep -q '__SSH_PORT__' "$SSH_RENDERED"; then
    die "SSH port placeholder was not rendered"
fi

install \
    -o root \
    -g root \
    -m 0644 \
    "$SSH_RENDERED" \
    /etc/ssh/sshd_config.d/00-collector-global.conf

install \
    -o root \
    -g root \
    -m 0644 \
    "$SSH_SOURCE/90-ai-spool-reader.conf" \
    /etc/ssh/sshd_config.d/90-ai-spool-reader.conf

install \
    -o root \
    -g root \
    -m 0644 \
    "$SSH_SOURCE/91-ai-results-writer.conf" \
    /etc/ssh/sshd_config.d/91-ai-results-writer.conf

sshd -t

echo "=== TRANSPORT ACCOUNT STATE ==="

for user in \
    ai_spool_reader \
    ai_results_writer \
    ai_results_gate
do
    getent passwd "$user" \
        | awk -F: '{
            printf "user=%s home=%s shell=%s\n",
                $1, $6, $7
        }'

    passwd -S "$user" \
        | awk '{
            printf "  password_state=%s\n", $2
        }'
done

echo
echo "=== TRANSPORT PATH STATE ==="

for path in \
    /var/spool/vector-ai \
    /var/spool/ai-results \
    /var/spool/ai-results/incoming \
    /var/spool/ai-results/ready \
    /var/spool/ai-results/rejected \
    /srv/ai-spool-reader \
    /srv/ai-spool-reader/spool \
    /srv/ai-results-writer \
    /srv/ai-results-writer/incoming
do
    stat \
        -c 'path=%n mode=%a owner=%U group=%G' \
        "$path"
done

echo
echo "=== TRANSPORT MOUNTS ==="

findmnt \
    -no TARGET,FSTYPE,OPTIONS \
    /srv/ai-spool-reader/spool

findmnt \
    -no TARGET,FSTYPE,OPTIONS \
    /srv/ai-results-writer/incoming

echo
echo "=== SSH CONFIG CHECK ==="

sshd -t
echo "sshd_config_valid=yes"

echo
echo "TRANSPORT_BOOTSTRAP=PASS"
echo "SSH configuration is installed but the SSH service was not reloaded."
