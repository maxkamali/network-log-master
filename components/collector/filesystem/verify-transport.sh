#!/usr/bin/env bash
set -euo pipefail

READER_BIND_SOURCE="raw"

if [ "${1:-}" = "--help" ]; then
    echo "usage: verify-transport.sh [--reader-bind-source raw|handoff]"
    exit 0
fi

if [ "${1:-}" = "--reader-bind-source" ]; then
    [ "$#" -eq 2 ] \
        || {
            echo "FAIL: --reader-bind-source requires raw or handoff" >&2
            exit 1
        }
    READER_BIND_SOURCE="$2"
    shift 2
fi

[ "$#" -eq 0 ] \
    || {
        echo "FAIL: unexpected transport-verifier argument" >&2
        exit 1
    }

case "$READER_BIND_SOURCE" in
    raw)
        READER_SOURCE_PATH="/var/spool/vector-ai"
        READER_OTHER_SOURCE_PATH="/var/spool/network-log-normalizer-handoff"
        READER_SOURCE_OWNER="vector"
        READER_SOURCE_GROUP="vector"
        ;;
    handoff)
        READER_SOURCE_PATH="/var/spool/network-log-normalizer-handoff"
        READER_OTHER_SOURCE_PATH="/var/spool/vector-ai"
        READER_SOURCE_OWNER="network-log-normalizer"
        READER_SOURCE_GROUP="network-log-normalizer"
        ;;
    *)
        echo "FAIL: unsupported reader bind source: $READER_BIND_SOURCE" >&2
        exit 1
        ;;
esac

fail()
{
    echo "FAIL: $*" >&2
    exit 1
}

require_equal()
{
    local label="$1"
    local expected="$2"
    local actual="$3"

    if [ "$actual" != "$expected" ]; then
        fail "$label expected=$expected actual=$actual"
    fi
}

exact_line_count()
{
    local expected="$1"
    local path="$2"

    awk -v expected="$expected" \
        '$0 == expected { count += 1 } END { print count + 0 }' \
        "$path"
}

fstab_target_count()
{
    local target="$1"
    local path="$2"

    awk -v target="$target" \
        '$0 !~ /^[[:space:]]*#/ && NF > 1 && $2 == target { count += 1 } END { print count + 0 }' \
        "$path"
}

require_account()
{
    local user="$1"
    local group="$2"
    local home="$3"
    local shell="$4"

    getent passwd "$user" >/dev/null \
        || fail "missing user $user"

    require_equal \
        "$user primary group" \
        "$group" \
        "$(id -gn "$user")"

    require_equal \
        "$user home" \
        "$home" \
        "$(getent passwd "$user" | cut -d: -f6)"

    require_equal \
        "$user shell" \
        "$shell" \
        "$(getent passwd "$user" | cut -d: -f7)"

    require_equal \
        "$user password state" \
        "L" \
        "$(passwd -S "$user" | awk '{print $2}')"
}

require_metadata()
{
    local path="$1"
    local mode="$2"
    local owner="$3"
    local group="$4"

    [ -e "$path" ] \
        || fail "missing path $path"

    require_equal \
        "$path mode" \
        "$mode" \
        "$(stat -c '%a' "$path")"

    require_equal \
        "$path owner" \
        "$owner" \
        "$(stat -c '%U' "$path")"

    require_equal \
        "$path group" \
        "$group" \
        "$(stat -c '%G' "$path")"
}

require_mount_options()
{
    local target="$1"
    shift

    findmnt -rn --mountpoint "$target" >/dev/null \
        || fail "$target is not mounted"

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
                fail "$target missing mount option $required"
                ;;
        esac
    done
}

require_mount_source()
{
    local target="$1"
    local expected="$2"
    local actual

    actual="$(
        findmnt \
            -n \
            -o FSROOT \
            --mountpoint "$target"
    )"

    require_equal \
        "$target bind source" \
        "$expected" \
        "$actual"
}

require_sshd_value()
{
    local user="$1"
    local key="$2"
    local expected="$3"

    local actual

    actual="$(
        sshd \
            -T \
            -C "user=$user,host=localhost,addr=127.0.0.1" \
            | awk -v key="$key" '
                $1 == key {
                    $1 = ""
                    sub(/^ /, "")
                    print
                    exit
                }
            '
    )"

    require_equal \
        "$user sshd $key" \
        "$expected" \
        "$actual"
}

require_account \
    ai_spool_reader \
    ai_spool_readers \
    /var/lib/ai-spool-reader \
    /usr/sbin/nologin

require_account \
    ai_results_writer \
    ai_results_writer \
    /var/lib/ai-results-writer \
    /usr/sbin/nologin

require_account \
    ai_results_gate \
    ai_results_gate \
    /var/lib/ai-results-gate \
    /usr/sbin/nologin

require_metadata \
    /var/lib/ai-spool-reader \
    700 \
    ai_spool_reader \
    ai_spool_readers

require_metadata \
    /var/lib/ai-spool-reader/.ssh \
    700 \
    ai_spool_reader \
    ai_spool_readers

require_metadata \
    /var/lib/ai-spool-reader/.ssh/authorized_keys \
    600 \
    ai_spool_reader \
    ai_spool_readers

require_metadata \
    /var/lib/ai-results-writer \
    700 \
    ai_results_writer \
    ai_results_writer

require_metadata \
    /var/lib/ai-results-writer/.ssh \
    700 \
    ai_results_writer \
    ai_results_writer

require_metadata \
    /var/lib/ai-results-writer/.ssh/authorized_keys \
    600 \
    ai_results_writer \
    ai_results_writer

[ ! -e /var/lib/ai-results-gate/.ssh ] \
    || fail "ai_results_gate unexpectedly has an SSH directory"

require_metadata \
    /var/spool/vector-ai \
    750 \
    vector \
    vector

if [ "$READER_BIND_SOURCE" = "handoff" ]; then
    require_metadata \
        "$READER_SOURCE_PATH" \
        750 \
        "$READER_SOURCE_OWNER" \
        "$READER_SOURCE_GROUP"
fi

require_metadata \
    /var/spool/ai-results \
    750 \
    root \
    vector

require_metadata \
    /var/spool/ai-results/incoming \
    2770 \
    root \
    vector

require_metadata \
    /var/spool/ai-results/ready \
    2770 \
    root \
    vector

require_metadata \
    /var/spool/ai-results/rejected \
    2770 \
    root \
    vector

require_metadata \
    /srv/ai-spool-reader \
    755 \
    root \
    root

require_metadata \
    /srv/ai-spool-reader/spool \
    750 \
    "$READER_SOURCE_OWNER" \
    "$READER_SOURCE_GROUP"

require_metadata \
    /srv/ai-results-writer \
    755 \
    root \
    root

require_metadata \
    /srv/ai-results-writer/incoming \
    2770 \
    root \
    vector

EXPECTED_VECTOR_ACL="$(cat <<'EOF'
user::rwx
group::r-x
group:ai_spool_readers:r-x
mask::r-x
other::---
default:user::rwx
default:group::r-x
default:group:ai_spool_readers:r-x
default:mask::r-x
default:other::---
EOF
)"

require_equal \
    "vector spool ACL" \
    "$EXPECTED_VECTOR_ACL" \
    "$(getfacl --absolute-names --omit-header /var/spool/vector-ai)"

if [ "$READER_BIND_SOURCE" = "handoff" ]; then
    require_equal \
        "normalizer handoff spool ACL" \
        "$EXPECTED_VECTOR_ACL" \
        "$(getfacl --absolute-names --omit-header "$READER_SOURCE_PATH")"
fi

EXPECTED_RESULTS_ROOT_ACL="$(cat <<'EOF'
user::rwx
user:ai_results_gate:--x
group::r-x
mask::r-x
other::---
EOF
)"

require_equal \
    "AI results root ACL" \
    "$EXPECTED_RESULTS_ROOT_ACL" \
    "$(getfacl --absolute-names --omit-header /var/spool/ai-results)"

EXPECTED_INCOMING_ACL="$(cat <<'EOF'
user::rwx
user:ai_results_gate:rwx
user:ai_results_writer:-wx
group::r-x
mask::rwx
other::---
default:user::rwx
default:user:ai_results_gate:r--
default:group::r-x
default:mask::r-x
default:other::---
EOF
)"

require_equal \
    "AI results incoming ACL" \
    "$EXPECTED_INCOMING_ACL" \
    "$(getfacl --absolute-names --omit-header /var/spool/ai-results/incoming)"

EXPECTED_GATE_OUTPUT_ACL="$(cat <<'EOF'
user::rwx
user:ai_results_gate:rwx
group::r-x
mask::rwx
other::---
EOF
)"

for path in \
    /var/spool/ai-results/ready \
    /var/spool/ai-results/rejected
do
    require_equal \
        "$path ACL" \
        "$EXPECTED_GATE_OUTPUT_ACL" \
        "$(getfacl --absolute-names --omit-header "$path")"
done

require_mount_options \
    /srv/ai-spool-reader/spool \
    ro \
    nosuid \
    nodev \
    noexec

require_mount_source \
    /srv/ai-spool-reader/spool \
    "$READER_SOURCE_PATH"

require_mount_options \
    /srv/ai-results-writer/incoming \
    rw \
    nosuid \
    nodev \
    noexec

EXPECTED_READER_FSTAB_LINE="$READER_SOURCE_PATH /srv/ai-spool-reader/spool none bind,ro,nosuid,nodev,noexec 0 0"
OTHER_READER_FSTAB_LINE="$READER_OTHER_SOURCE_PATH /srv/ai-spool-reader/spool none bind,ro,nosuid,nodev,noexec 0 0"

[ "$(exact_line_count "$EXPECTED_READER_FSTAB_LINE" /etc/fstab)" -eq 1 ] \
    || fail "expected exactly one selected reader bind in /etc/fstab"

[ "$(fstab_target_count /srv/ai-spool-reader/spool /etc/fstab)" -eq 1 ] \
    || fail "reader bind target is absent or duplicated in /etc/fstab"

[ "$(exact_line_count "$OTHER_READER_FSTAB_LINE" /etc/fstab)" -eq 0 ] \
    || fail "unselected reader bind remains in /etc/fstab"

grep -Fqx \
    '/var/spool/ai-results/incoming /srv/ai-results-writer/incoming none bind,rw,nosuid,nodev,noexec 0 0' \
    /etc/fstab \
    || fail "writer bind mount missing from /etc/fstab"

cmp -s \
    components/collector/systemd/ai-results-gate.service.d/10-rw-paths.conf \
    /etc/systemd/system/ai-results-gate.service.d/10-rw-paths.conf \
    || fail "ai-results-gate systemd drop-in differs from repository"

sshd -t

mapfile -t ssh_ports < <(
    sshd -T \
        | awk '$1 == "port" {print $2}'
)

[ "${#ssh_ports[@]}" -eq 1 ] \
    || fail "expected exactly one SSH port"

[ "${ssh_ports[0]}" != "22" ] \
    || fail "collector SSH port must be nonstandard"

require_sshd_value \
    ai_spool_reader \
    pubkeyauthentication \
    yes

require_sshd_value \
    ai_spool_reader \
    passwordauthentication \
    no

require_sshd_value \
    ai_spool_reader \
    authenticationmethods \
    publickey

require_sshd_value \
    ai_spool_reader \
    permittty \
    no

require_sshd_value \
    ai_spool_reader \
    disableforwarding \
    yes

require_sshd_value \
    ai_spool_reader \
    chrootdirectory \
    /srv/ai-spool-reader

require_sshd_value \
    ai_spool_reader \
    forcecommand \
    'internal-sftp -R -d /spool'

require_sshd_value \
    ai_results_writer \
    pubkeyauthentication \
    yes

require_sshd_value \
    ai_results_writer \
    passwordauthentication \
    no

require_sshd_value \
    ai_results_writer \
    authenticationmethods \
    publickey

require_sshd_value \
    ai_results_writer \
    permittty \
    no

require_sshd_value \
    ai_results_writer \
    disableforwarding \
    yes

require_sshd_value \
    ai_results_writer \
    chrootdirectory \
    /srv/ai-results-writer

require_sshd_value \
    ai_results_writer \
    forcecommand \
    'internal-sftp -d /incoming -u 0437 -P read,opendir,readdir,remove,mkdir,rmdir,rename,readlink,symlink,posix-rename,hardlink,copy-data,setstat,fsetstat,lsetstat'

echo "reader_bind_source=$READER_BIND_SOURCE"
echo "TRANSPORT_VERIFY=PASS"
