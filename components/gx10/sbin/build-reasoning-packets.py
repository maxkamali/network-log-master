#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone

try:
    from runtime_config import load_runtime_config
except ModuleNotFoundError as exc:
    if exc.name != 'runtime_config':
        raise
    load_runtime_config = None


DB = load_runtime_config().database_path if load_runtime_config else None
POLICY_VERSION = 1
PACKET_VERSION = 1
MAX_PACKET_BYTES = 32 * 1024
MAX_TEXT_BYTES = 1024
MAX_ATTRIBUTES_BYTES = 2048
MAX_EVIDENCE = 8
MAX_TRANSITIONS = 8
CRITICAL_COOLDOWN_MS = 5 * 60 * 1000
SPECIAL_COOLDOWN_MS = 15 * 60 * 1000
PERIODIC_INTERVAL_MS = 15 * 60 * 1000
PERIODIC_EVIDENCE_DELTA = 5
PERIODIC_REPEAT_DELTA = 10
CRITICAL_SEVERITIES = {'critical', 'crit', 'alert', 'emergency', 'emerg'}
OSPF_FAMILIES = {'ospf', 'ospfv3'}
FORBIDDEN_ATTRIBUTE_KEYS = {
    'event_json',
    'local_path',
    'message',
    'raw_message',
    'remote_path',
    'source_file',
    'source_path',
}
REASON_PRIORITY = {
    'critical_condition': 100,
    'incident_reopened': 95,
    'incident_opened': 90,
    'interface_flap': 85,
    'ospf_retransmission': 80,
    'incident_recovering': 65,
    'incident_resolved': 60,
    'meaningful_update': 40,
}
REQUIRED_COLUMNS = {
    'incidents': {
        'incident_id',
        'status',
        'event_family',
        'protocol',
        'entity_type',
        'entity_key',
        'severity',
        'first_seen',
        'first_seen_epoch_ms',
        'last_seen',
        'last_seen_epoch_ms',
        'occurrence_count',
        'repeat_count_total',
        'observation_state_changes',
        'last_observation_state',
        'opened_at',
        'recovering_at',
        'resolved_at',
        'last_event_id',
        'context_json',
        'engine_version',
    },
    'incident_evidence': {
        'incident_id',
        'evidence_sequence',
        'event_id',
        'evidence_kind',
        'observed_at',
        'observed_at_epoch_ms',
        'event_code',
        'signal_type',
        'observation_state',
        'repeat_count',
        'attributes_json',
    },
    'incident_transitions': {
        'incident_id',
        'transition_sequence',
        'from_status',
        'to_status',
        'event_id',
        'reason',
        'occurred_at',
        'occurred_at_epoch_ms',
    },
    'reasoning_packets': {
        'packet_id',
        'incident_id',
        'policy_version',
        'packet_version',
        'primary_reason',
        'wake_reasons_json',
        'priority',
        'as_of_event_id',
        'as_of_evidence_sequence',
        'as_of_transition_sequence',
        'basis_repeat_count_total',
        'basis_state_change_count',
        'basis_last_seen_epoch_ms',
        'created_at',
        'packet_json',
        'packet_sha256',
    },
}


class PacketError(ValueError):
    pass


def canonical_json(value):
    return json.dumps(value, separators=(',', ':'), sort_keys=True)


def sha256_text(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def iso_from_epoch(epoch_ms):
    return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).isoformat()


def compact_text(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise PacketError('reasoning packet text field is invalid')
    encoded = value.encode('utf-8')
    if len(encoded) <= MAX_TEXT_BYTES:
        return value
    prefix = encoded[:MAX_TEXT_BYTES]
    while prefix:
        try:
            text = prefix.decode('utf-8')
            break
        except UnicodeDecodeError:
            prefix = prefix[:-1]
    else:
        text = ''
    return {
        'prefix': text,
        'sha256': hashlib.sha256(encoded).hexdigest(),
        'utf8_bytes': len(encoded),
    }


def validate_database_contract(connection):
    for table, expected in REQUIRED_COLUMNS.items():
        columns = {
            row[1]
            for row in connection.execute(f'PRAGMA table_info({table})')
        }
        if not expected <= columns:
            raise PacketError('reasoning packet database schema differs')


def parse_canonical_object(value, label):
    if not isinstance(value, str):
        raise PacketError(f'{label} is invalid')
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise PacketError(f'{label} is invalid') from exc
    if not isinstance(parsed, dict) or canonical_json(parsed) != value:
        raise PacketError(f'{label} is not canonical')
    return parsed


def validate_existing_packets(connection):
    for row in connection.execute(
        'SELECT * FROM reasoning_packets ORDER BY packet_id'
    ).fetchall():
        packet = parse_canonical_object(
            row['packet_json'],
            'stored reasoning packet',
        )
        try:
            reasons = json.loads(row['wake_reasons_json'])
        except json.JSONDecodeError as exc:
            raise PacketError('stored wake reasons are invalid') from exc
        if (
            not isinstance(reasons, list)
            or not reasons
            or canonical_json(reasons) != row['wake_reasons_json']
            or packet.get('packet_id') != row['packet_id']
            or packet.get('policy_version') != row['policy_version']
            or packet.get('packet_version') != row['packet_version']
            or packet.get('wake', {}).get('reasons') != reasons
            or packet.get('wake', {}).get('primary_reason')
            != row['primary_reason']
            or packet.get('wake', {}).get('priority') != row['priority']
            or sha256_text(row['packet_json']) != row['packet_sha256']
        ):
            raise PacketError('stored reasoning packet differs')


def packet_id(incident_id, evidence_sequence, transition_sequence):
    material = canonical_json(
        [
            'reasoning-packet-v1',
            POLICY_VERSION,
            PACKET_VERSION,
            incident_id,
            evidence_sequence,
            transition_sequence,
        ]
    )
    return 'pkt-v1-' + sha256_text(material)[:32]


def previous_packet(connection, incident_id):
    return connection.execute(
        '''
        SELECT * FROM reasoning_packets
        WHERE incident_id = ? AND policy_version = ? AND packet_version = ?
        ORDER BY as_of_evidence_sequence DESC,
                 as_of_transition_sequence DESC
        LIMIT 1
        ''',
        (incident_id, POLICY_VERSION, PACKET_VERSION),
    ).fetchone()


def incident_basis(connection, incident):
    evidence = connection.execute(
        '''
        SELECT
            COUNT(*),
            COALESCE(MAX(evidence_sequence), 0),
            COALESCE(SUM(repeat_count), 0),
            COALESCE(MAX(observed_at_epoch_ms), 0)
        FROM incident_evidence WHERE incident_id = ?
        ''',
        (incident['incident_id'],),
    ).fetchone()
    transition = connection.execute(
        '''
        SELECT COUNT(*), COALESCE(MAX(transition_sequence), 0),
               COALESCE(MAX(occurred_at_epoch_ms), 0)
        FROM incident_transitions WHERE incident_id = ?
        ''',
        (incident['incident_id'],),
    ).fetchone()
    if (
        evidence[0] != incident['occurrence_count']
        or evidence[2] != incident['repeat_count_total']
        or evidence[1] < 1
        or transition[1] < 1
    ):
        raise PacketError('incident packet basis differs')
    return {
        'evidence_count': evidence[0],
        'evidence_sequence': evidence[1],
        'repeat_count_total': evidence[2],
        'evidence_time_ms': evidence[3],
        'transition_count': transition[0],
        'transition_sequence': transition[1],
        'transition_time_ms': transition[2],
    }


def new_evidence(connection, incident_id, after_sequence):
    return connection.execute(
        '''
        SELECT * FROM incident_evidence
        WHERE incident_id = ? AND evidence_sequence > ?
        ORDER BY evidence_sequence
        ''',
        (incident_id, after_sequence),
    ).fetchall()


def new_transitions(connection, incident_id, after_sequence):
    return connection.execute(
        '''
        SELECT * FROM incident_transitions
        WHERE incident_id = ? AND transition_sequence > ?
        ORDER BY transition_sequence
        ''',
        (incident_id, after_sequence),
    ).fetchall()


def ordered_reasons(incident, basis, evidence, transitions, previous):
    reasons = set()
    for transition in transitions:
        if transition['to_status'] == 'OPEN':
            reasons.add(
                'incident_reopened'
                if transition['reason'] == 'adverse_relapse'
                else 'incident_opened'
            )
        elif transition['to_status'] == 'RECOVERING':
            reasons.add('incident_recovering')
        elif transition['to_status'] == 'RESOLVED':
            reasons.add('incident_resolved')

    if previous is None and incident['status'] == 'RESOLVED':
        return []
    previous_time = (
        previous['basis_last_seen_epoch_ms']
        if previous is not None
        else None
    )
    elapsed = (
        basis['evidence_time_ms'] - previous_time
        if previous_time is not None
        else None
    )
    lifecycle_wake = any(
        reason in reasons
        for reason in ('incident_opened', 'incident_reopened')
    )
    if evidence and incident['severity'].casefold() in CRITICAL_SEVERITIES:
        if previous is None or elapsed >= CRITICAL_COOLDOWN_MS or lifecycle_wake:
            reasons.add('critical_condition')

    prior_state_changes = (
        previous['basis_state_change_count'] if previous is not None else 0
    )
    if (
        (incident['entity_type'] or '').casefold() == 'interface'
        and incident['observation_state_changes'] > prior_state_changes
    ):
        reasons.add('interface_flap')

    ospf_retransmission = (
        incident['event_family'].casefold() in OSPF_FAMILIES
        and any(
            row['signal_type'].casefold() == 'degradation'
            and (row['observation_state'] or '').casefold()
            == 'retransmissions'
            for row in evidence
        )
    )
    if ospf_retransmission and (
        previous is None or elapsed >= SPECIAL_COOLDOWN_MS or lifecycle_wake
    ):
        reasons.add('ospf_retransmission')

    previous_evidence = (
        previous['as_of_evidence_sequence'] if previous is not None else 0
    )
    previous_repeats = (
        previous['basis_repeat_count_total'] if previous is not None else 0
    )
    evidence_delta = incident['occurrence_count'] - previous_evidence
    repeat_delta = incident['repeat_count_total'] - previous_repeats
    if (
        previous is not None
        and evidence
        and incident['status'] != 'RESOLVED'
        and (
            evidence_delta >= PERIODIC_EVIDENCE_DELTA
            or repeat_delta >= PERIODIC_REPEAT_DELTA
            or elapsed >= PERIODIC_INTERVAL_MS
        )
    ):
        reasons.add('meaningful_update')

    return sorted(reasons, key=lambda reason: (-REASON_PRIORITY[reason], reason))


def sanitize_attribute_value(value):
    if isinstance(value, dict):
        result = {}
        removed = 0
        for key in sorted(value):
            if key.casefold() in FORBIDDEN_ATTRIBUTE_KEYS:
                removed += 1
                continue
            child, child_removed = sanitize_attribute_value(value[key])
            result[key] = child
            removed += child_removed
        return result, removed
    if isinstance(value, list):
        result = []
        removed = 0
        for item in value:
            child, child_removed = sanitize_attribute_value(item)
            result.append(child)
            removed += child_removed
        return result, removed
    return value, 0


def compact_attributes(value):
    attributes = parse_canonical_object(value, 'incident evidence attributes')
    original = canonical_json(attributes)
    sanitized, removed = sanitize_attribute_value(attributes)
    canonical = canonical_json(sanitized)
    size = len(canonical.encode('utf-8'))
    if size <= MAX_ATTRIBUTES_BYTES:
        result = {'attributes': sanitized}
        if removed:
            result.update(
                {
                    'attributes_redacted_keys': removed,
                    'attributes_sha256': sha256_text(original),
                }
            )
        return result
    return {
        'attributes_omitted': True,
        'attributes_sha256': sha256_text(original),
        'attributes_utf8_bytes': len(original.encode('utf-8')),
    }


def evidence_packet_rows(rows):
    result = []
    for row in rows[-MAX_EVIDENCE:]:
        item = {
            'sequence': row['evidence_sequence'],
            'kind': row['evidence_kind'],
            'observed_at': row['observed_at'],
            'event_code': compact_text(row['event_code']),
            'signal_type': compact_text(row['signal_type']),
            'observation_state': compact_text(row['observation_state']),
            'repeat_count': row['repeat_count'],
        }
        item.update(compact_attributes(row['attributes_json']))
        result.append(item)
    return result


def transition_packet_rows(rows):
    return [
        {
            'sequence': row['transition_sequence'],
            'from_status': row['from_status'],
            'to_status': row['to_status'],
            'reason': row['reason'],
            'occurred_at': row['occurred_at'],
        }
        for row in rows[-MAX_TRANSITIONS:]
    ]


def build_packet(incident, basis, previous, evidence, transitions, reasons):
    identifier = packet_id(
        incident['incident_id'],
        basis['evidence_sequence'],
        basis['transition_sequence'],
    )
    prior_evidence = previous['as_of_evidence_sequence'] if previous else 0
    prior_transitions = previous['as_of_transition_sequence'] if previous else 0
    prior_repeats = previous['basis_repeat_count_total'] if previous else 0
    prior_state_changes = previous['basis_state_change_count'] if previous else 0
    context = parse_canonical_object(
        incident['context_json'],
        'incident context',
    )
    created_at = iso_from_epoch(
        max(basis['transition_time_ms'], basis['evidence_time_ms'])
    )
    packet = {
        'schema': 'gx10-incident-reasoning-packet',
        'packet_version': PACKET_VERSION,
        'policy_version': POLICY_VERSION,
        'packet_id': identifier,
        'created_at': created_at,
        'wake': {
            'primary_reason': reasons[0],
            'reasons': reasons,
            'priority': REASON_PRIORITY[reasons[0]],
        },
        'incident': {
            'incident_id': incident['incident_id'],
            'engine_version': incident['engine_version'],
            'status': incident['status'],
            'event_family': compact_text(incident['event_family']),
            'protocol': compact_text(incident['protocol']),
            'entity_type': compact_text(incident['entity_type']),
            'entity_key': compact_text(incident['entity_key']),
            'severity': compact_text(incident['severity']),
            'first_seen': incident['first_seen'],
            'last_seen': incident['last_seen'],
            'occurrence_count': incident['occurrence_count'],
            'repeat_count_total': incident['repeat_count_total'],
            'observation_state_changes': (
                incident['observation_state_changes']
            ),
            'last_observation_state': compact_text(
                incident['last_observation_state']
            ),
            'opened_at': incident['opened_at'],
            'recovering_at': incident['recovering_at'],
            'resolved_at': incident['resolved_at'],
            'context': context,
        },
        'delta': {
            'evidence_count': basis['evidence_sequence'] - prior_evidence,
            'repeat_count_total': (
                incident['repeat_count_total'] - prior_repeats
            ),
            'state_change_count': (
                incident['observation_state_changes'] - prior_state_changes
            ),
            'transition_count': (
                basis['transition_sequence'] - prior_transitions
            ),
            'evidence_omitted_from_packet': max(
                0,
                len(evidence) - MAX_EVIDENCE,
            ),
            'transitions_omitted_from_packet': max(
                0,
                len(transitions) - MAX_TRANSITIONS,
            ),
        },
        'evidence': evidence_packet_rows(evidence),
        'transitions': transition_packet_rows(transitions),
    }
    encoded = canonical_json(packet)
    if len(encoded.encode('utf-8')) > MAX_PACKET_BYTES:
        raise PacketError('reasoning packet exceeds size limit')
    return identifier, created_at, encoded


def process_incident(connection, incident):
    basis = incident_basis(connection, incident)
    previous = previous_packet(connection, incident['incident_id'])
    after_evidence = previous['as_of_evidence_sequence'] if previous else 0
    after_transition = previous['as_of_transition_sequence'] if previous else 0
    if (
        basis['evidence_sequence'] == after_evidence
        and basis['transition_sequence'] == after_transition
    ):
        return False
    evidence = new_evidence(
        connection,
        incident['incident_id'],
        after_evidence,
    )
    transitions = new_transitions(
        connection,
        incident['incident_id'],
        after_transition,
    )
    reasons = ordered_reasons(
        incident,
        basis,
        evidence,
        transitions,
        previous,
    )
    if not reasons:
        return False
    identifier, created_at, packet_json = build_packet(
        incident,
        basis,
        previous,
        evidence,
        transitions,
        reasons,
    )
    connection.execute(
        '''
        INSERT INTO reasoning_packets (
            packet_id, incident_id, policy_version, packet_version,
            primary_reason, wake_reasons_json, priority, as_of_event_id,
            as_of_evidence_sequence, as_of_transition_sequence,
            basis_repeat_count_total, basis_state_change_count,
            basis_last_seen_epoch_ms, created_at, packet_json, packet_sha256
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            identifier,
            incident['incident_id'],
            POLICY_VERSION,
            PACKET_VERSION,
            reasons[0],
            canonical_json(reasons),
            REASON_PRIORITY[reasons[0]],
            incident['last_event_id'],
            basis['evidence_sequence'],
            basis['transition_sequence'],
            incident['repeat_count_total'],
            incident['observation_state_changes'],
            basis['evidence_time_ms'],
            created_at,
            packet_json,
            sha256_text(packet_json),
        ),
    )
    return True


def run(database=DB):
    if database is None:
        raise PacketError('reasoning packet database is not configured')
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA busy_timeout=5000')
        if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise PacketError('reasoning packet quick_check failed')
        if connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
            raise PacketError('reasoning packet foreign_key_check failed')
        validate_database_contract(connection)
        validate_existing_packets(connection)
        connection.execute('BEGIN IMMEDIATE')
        created = 0
        incidents = connection.execute(
            '''
            SELECT * FROM incidents
            WHERE entity_type != 'event_signature'
            ORDER BY first_seen_epoch_ms, incident_id
            '''
        ).fetchall()
        for incident in incidents:
            created += int(process_incident(connection, incident))
        validate_existing_packets(connection)
        connection.commit()
        total = connection.execute(
            'SELECT COUNT(*) FROM reasoning_packets'
        ).fetchone()[0]
        print(
            'REASONING_PACKETS '
            f'policy={POLICY_VERSION} packet={PACKET_VERSION} '
            f'incidents_scanned={len(incidents)} created={created} total={total}'
        )
        print('GX10_REASONING_PACKETS=PASS')
        return 0
    except (OSError, sqlite3.Error, PacketError, ValueError) as exc:
        connection.rollback()
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1
    finally:
        connection.close()


if __name__ == '__main__':
    sys.exit(run())
