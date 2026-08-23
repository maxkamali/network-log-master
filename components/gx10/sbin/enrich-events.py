#!/usr/bin/env python3
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from runtime_config import load_runtime_config
_CONFIG = load_runtime_config()
DB = _CONFIG.database_path
CLASSIFICATION_VERSION = 3
EVENT_CODE_RE = re.compile('%([A-Za-z0-9_.-]+)\\s*:')
EVENT_CODE_FALLBACK_RE = re.compile('%([A-Za-z0-9_.-]+)')
INTERFACE_RE = re.compile('\\bInterface\\s+([A-Za-z0-9/._:-]+)', re.IGNORECASE)
NXOS_OSPF_PROCESS_RE = re.compile('\\b(ospf-\\d+)\\s+\\[\\d+\\]', re.IGNORECASE)
OSPF_NEIGHBOR_RE = re.compile('\\bNbr\\s+([0-9A-Fa-f:.]+)', re.IGNORECASE)
REPEAT_RE = re.compile('^\\s*last message repeated\\s+(\\d+)\\s+times?\\s*$', re.IGNORECASE)
PROCESS_RE = re.compile('^\\s*([A-Za-z0-9_.-]+)\\[\\d+\\]:', re.IGNORECASE)
ARISTA_BGP_ADJ_RE = re.compile('%BGP-\\d+-ADJCHANGE:\\s+peer\\s+(?P<peer>\\S+)\\s+\\(VRF\\s+(?P<vrf>\\S+)\\s+AS\\s+(?P<asn>\\d+)\\)\\s+old\\s+state\\s+(?P<old_state>\\S+)\\s+event\\s+(?P<event>\\S+)\\s+new\\s+state\\s+(?P<new_state>\\S+)', re.IGNORECASE)
ARISTA_BGP_CLEAR_RE = re.compile('%BGP-\\d+-PEER_CLEAR:\\s+BGP\\s+peering\\s+for\\s+neighbor\\s+(?P<peer>\\S+)\\s+\\(vrf\\s+(?P<vrf>[^)]+)\\)', re.IGNORECASE)
ARISTA_BGP_NOTIFICATION_RE = re.compile('%BGP-\\d+-NOTIFICATION:.*?neighbor\\s+(?P<peer>\\S+)\\s+\\(VRF\\s+(?P<vrf>\\S+)\\s+AS\\s+(?P<asn>\\d+)\\)', re.IGNORECASE)
IOSXR_BGP_ADJ_RE = re.compile('%ROUTING-BGP-\\d+-ADJCHANGE\\s*:\\s*neighbor\\s+(?P<peer>\\S+)\\s+(?P<state>Up|Down)\\b(?P<rest>.*)\\(VRF:\\s*(?P<vrf>[^)]+)\\)(?:\\s+\\(AS:\\s*(?P<asn>\\d+)\\))?', re.IGNORECASE)
IOSXR_BGP_NSR_RE = re.compile('%ROUTING-BGP-\\d+-NBR_NSR_DISABLED_STANDBY\\s*:\\s*.*?neighbor\\s+(?P<peer>\\S+).*?\\(VRF:\\s*(?P<vrf>[^)]+)\\)', re.IGNORECASE)

def ensure_schema(conn):
    columns = {row[1] for row in conn.execute('PRAGMA table_info(event_enrichment)')}
    additions = {'repeat_count': 'INTEGER NOT NULL DEFAULT 1', 'classification_version': 'INTEGER NOT NULL DEFAULT 0', 'vendor_hint': "TEXT NOT NULL DEFAULT 'unknown'", 'protocol': "TEXT NOT NULL DEFAULT ''", 'signal_type': "TEXT NOT NULL DEFAULT 'observation'", 'attributes_json': "TEXT NOT NULL DEFAULT '{}'"}
    for name, definition in additions.items():
        if name not in columns:
            conn.execute(f'\n                ALTER TABLE event_enrichment\n                ADD COLUMN {name} {definition}\n                ')
    conn.execute('\n        CREATE INDEX IF NOT EXISTS\n        idx_enrichment_protocol\n        ON event_enrichment(protocol)\n    ')
    conn.execute('\n        CREATE INDEX IF NOT EXISTS\n        idx_enrichment_signal_type\n        ON event_enrichment(signal_type)\n    ')
    conn.execute('\n        CREATE INDEX IF NOT EXISTS\n        idx_enrichment_vendor_hint\n        ON event_enrichment(vendor_hint)\n    ')
    conn.commit()

def extract_event_code(message, raw_message):
    for text in (message, raw_message):
        if not text:
            continue
        match = EVENT_CODE_RE.search(text)
        if match:
            return match.group(1)
        match = EVENT_CODE_FALLBACK_RE.search(text)
        if match:
            return match.group(1)
    return ''

def generic_family_from_code(code):
    if not code:
        return 'unknown'
    cleaned = code.lstrip('-._')
    if not cleaned:
        return 'unknown'
    first = cleaned.split('-', 1)[0]
    if re.fullmatch('SLOT\\d+', first, re.IGNORECASE):
        return 'unknown'
    return first.lower()

def bgp_key(device, vrf, peer):
    return f'BGP|{device}|{vrf.lower()}|{peer.lower()}'

def classify_bgp(event_code, message, device):
    match = ARISTA_BGP_ADJ_RE.search(message)
    if match:
        values = match.groupdict()
        peer = values['peer']
        vrf = values['vrf']
        asn = int(values['asn'])
        old_state = values['old_state']
        new_state = values['new_state']
        event = values['event']
        if new_state.lower() == 'established':
            state = 'up'
            signal_type = 'recovery'
        elif new_state.lower() == 'idle':
            state = 'down'
            signal_type = 'state_transition'
        else:
            state = new_state.lower()
            signal_type = 'state_transition'
        return {'family': 'bgp', 'vendor_hint': 'arista_eos', 'protocol': 'bgp', 'entity_type': 'bgp_peer', 'entity_key': bgp_key(device, vrf, peer), 'state': state, 'signal_type': signal_type, 'attributes': {'peer': peer, 'vrf': vrf, 'remote_as': asn, 'old_state': old_state, 'new_state': new_state, 'event': event}}
    match = ARISTA_BGP_CLEAR_RE.search(message)
    if match:
        peer = match.group('peer')
        vrf = match.group('vrf').strip()
        return {'family': 'bgp', 'vendor_hint': 'arista_eos', 'protocol': 'bgp', 'entity_type': 'bgp_peer', 'entity_key': bgp_key(device, vrf, peer), 'state': 'clear_requested', 'signal_type': 'administrative_action', 'attributes': {'peer': peer, 'vrf': vrf}}
    match = ARISTA_BGP_NOTIFICATION_RE.search(message)
    if match:
        peer = match.group('peer')
        vrf = match.group('vrf')
        asn = int(match.group('asn'))
        return {'family': 'bgp', 'vendor_hint': 'arista_eos', 'protocol': 'bgp', 'entity_type': 'bgp_peer', 'entity_key': bgp_key(device, vrf, peer), 'state': 'notification', 'signal_type': 'protocol_notification', 'attributes': {'peer': peer, 'vrf': vrf, 'remote_as': asn}}
    match = IOSXR_BGP_ADJ_RE.search(message)
    if match:
        values = match.groupdict()
        peer = values['peer']
        vrf = values['vrf'].strip()
        asn = int(values['asn']) if values['asn'] else None
        xr_state = values['state'].lower()
        state = 'up' if xr_state == 'up' else 'down'
        signal_type = 'recovery' if state == 'up' else 'state_transition'
        attrs = {'peer': peer, 'vrf': vrf, 'xr_state': values['state']}
        if asn is not None:
            attrs['remote_as'] = asn
        rest = (values.get('rest') or '').strip()
        if rest:
            attrs['detail'] = rest
        return {'family': 'bgp', 'vendor_hint': 'cisco_ios_xr', 'protocol': 'bgp', 'entity_type': 'bgp_peer', 'entity_key': bgp_key(device, vrf, peer), 'state': state, 'signal_type': signal_type, 'attributes': attrs}
    match = IOSXR_BGP_NSR_RE.search(message)
    if match:
        peer = match.group('peer')
        vrf = match.group('vrf').strip()
        return {'family': 'bgp', 'vendor_hint': 'cisco_ios_xr', 'protocol': 'bgp', 'entity_type': 'bgp_peer', 'entity_key': bgp_key(device, vrf, peer), 'state': 'nsr_disabled_standby', 'signal_type': 'supporting_evidence', 'attributes': {'peer': peer, 'vrf': vrf}}
    if event_code.startswith('BGP-') or '-BGP-' in event_code:
        vendor = 'unknown'
        if event_code.startswith('ROUTING-BGP-'):
            vendor = 'cisco_ios_xr'
        return {'family': 'bgp', 'vendor_hint': vendor, 'protocol': 'bgp', 'entity_type': 'bgp', 'entity_key': None, 'state': None, 'signal_type': 'observation', 'attributes': {}}
    return None

def classify(event_code, message, raw_message, device):
    repeat_match = REPEAT_RE.match(message or '')
    if repeat_match:
        return {'family': 'syslog_repeat', 'vendor_hint': 'unknown', 'protocol': '', 'entity_type': 'syslog_stream', 'entity_key': f'SYSLOG_REPEAT|{device}', 'state': 'repeat', 'signal_type': 'repeat_notice', 'repeat_count': int(repeat_match.group(1)), 'attributes': {}}
    bgp = classify_bgp(event_code, message, device)
    if bgp:
        bgp['repeat_count'] = 1
        return bgp
    family = generic_family_from_code(event_code)
    if family == 'unknown':
        process_match = PROCESS_RE.match(message or '')
        if process_match:
            process_name = process_match.group(1)
            return {'family': 'process', 'vendor_hint': 'unknown', 'protocol': '', 'entity_type': 'process', 'entity_key': f'PROCESS|{device}|{process_name}', 'state': None, 'signal_type': 'observation', 'repeat_count': 1, 'attributes': {'process': process_name}}
    if family == 'ethport':
        match = INTERFACE_RE.search(message or '')
        if match:
            interface = match.group(1)
            state = None
            signal_type = 'supporting_evidence'
            if 'IF_DOWN' in event_code:
                state = 'down'
                signal_type = 'state_transition'
            elif event_code.endswith('-IF_UP'):
                state = 'up'
                signal_type = 'recovery'
            return {'family': family, 'vendor_hint': 'cisco_nxos', 'protocol': 'ethernet', 'entity_type': 'interface', 'entity_key': f'INTERFACE|{device}|{interface}', 'state': state, 'signal_type': signal_type, 'repeat_count': 1, 'attributes': {'interface': interface}}
    if family == 'ospf' and event_code.endswith('NBR_RETRANSMISSIONS'):
        nbr = OSPF_NEIGHBOR_RE.search(message or '')
        process = NXOS_OSPF_PROCESS_RE.search(message or '')
        neighbor = nbr.group(1) if nbr else None
        process_name = process.group(1) if process else 'unknown'
        entity_key = None
        if neighbor:
            entity_key = f'OSPF|{device}|{process_name}|{neighbor}'
        attrs = {}
        if neighbor:
            attrs['neighbor'] = neighbor
        if process_name != 'unknown':
            attrs['process'] = process_name
        return {'family': 'ospf', 'vendor_hint': 'cisco_nxos', 'protocol': 'ospf', 'entity_type': 'ospf_neighbor', 'entity_key': entity_key, 'state': 'retransmissions', 'signal_type': 'degradation', 'repeat_count': 1, 'attributes': attrs}
    return {'family': family, 'vendor_hint': 'unknown', 'protocol': '', 'entity_type': None, 'entity_key': None, 'state': None, 'signal_type': 'observation', 'repeat_count': 1, 'attributes': {}}

def load_suppression_rules(conn):
    rows = conn.execute('\n        SELECT\n            id,\n            name,\n            rule_type,\n            pattern\n        FROM suppression_rules\n        WHERE enabled = 1\n        ORDER BY id\n    ').fetchall()
    rules = []
    for rule_id, name, rule_type, pattern in rows:
        compiled = None
        if rule_type == 'message_regex':
            try:
                compiled = re.compile(pattern)
            except re.error as exc:
                print(f'WARNING invalid suppression regex {name}: {exc}', file=sys.stderr)
                continue
        rules.append((rule_id, name, rule_type, pattern, compiled))
    return rules

def suppression_for(event_code, message, rules):
    for rule_id, name, rule_type, pattern, compiled in rules:
        if rule_type == 'event_code_exact' and event_code == pattern:
            return rule_id
        if rule_type == 'event_code_prefix' and event_code.startswith(pattern):
            return rule_id
        if rule_type == 'message_regex' and compiled and compiled.search(message or ''):
            return rule_id
    return None

def main():
    conn = sqlite3.connect(DB)
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=5000')
    ensure_schema(conn)
    rules = load_suppression_rules(conn)
    rows = conn.execute('\n        SELECT\n            r.id,\n            r.hostname,\n            r.source_ip,\n            r.message,\n            r.raw_message\n\n        FROM recent_events AS r\n\n        LEFT JOIN event_enrichment AS e\n            ON e.event_id = r.id\n\n        WHERE\n            e.event_id IS NULL\n            OR e.classification_version < ?\n\n        ORDER BY r.id\n    ', (CLASSIFICATION_VERSION,)).fetchall()
    print(f'QUEUE {len(rows)} event(s) for classification v{CLASSIFICATION_VERSION}')
    now = datetime.now(timezone.utc).isoformat()
    classified = 0
    suppressed_this_run = 0
    conn.execute('BEGIN IMMEDIATE')
    try:
        for event_id, hostname, source_ip, message, raw_message in rows:
            message = message or ''
            raw_message = raw_message or ''
            device = hostname or source_ip or 'unknown'
            event_code = extract_event_code(message, raw_message)
            result = classify(event_code, message, raw_message, device)
            suppression_rule_id = suppression_for(event_code, message, rules)
            attention_eligible = 0 if suppression_rule_id is not None else 1
            if not attention_eligible:
                suppressed_this_run += 1
            conn.execute('\n                INSERT INTO event_enrichment\n                (\n                    event_id,\n                    event_code,\n                    family,\n                    device,\n                    entity_type,\n                    entity_key,\n                    state,\n                    attention_eligible,\n                    suppression_rule_id,\n                    classified_at,\n                    repeat_count,\n                    classification_version,\n                    vendor_hint,\n                    protocol,\n                    signal_type,\n                    attributes_json\n                )\n                VALUES (\n                    ?, ?, ?, ?, ?, ?, ?, ?, ?,\n                    ?, ?, ?, ?, ?, ?, ?\n                )\n\n                ON CONFLICT(event_id) DO UPDATE SET\n                    event_code =\n                        excluded.event_code,\n\n                    family =\n                        excluded.family,\n\n                    device =\n                        excluded.device,\n\n                    entity_type =\n                        excluded.entity_type,\n\n                    entity_key =\n                        excluded.entity_key,\n\n                    state =\n                        excluded.state,\n\n                    attention_eligible =\n                        excluded.attention_eligible,\n\n                    suppression_rule_id =\n                        excluded.suppression_rule_id,\n\n                    classified_at =\n                        excluded.classified_at,\n\n                    repeat_count =\n                        excluded.repeat_count,\n\n                    classification_version =\n                        excluded.classification_version,\n\n                    vendor_hint =\n                        excluded.vendor_hint,\n\n                    protocol =\n                        excluded.protocol,\n\n                    signal_type =\n                        excluded.signal_type,\n\n                    attributes_json =\n                        excluded.attributes_json\n            ', (event_id, event_code, result['family'], device, result['entity_type'], result['entity_key'], result['state'], attention_eligible, suppression_rule_id, now, result['repeat_count'], CLASSIFICATION_VERSION, result['vendor_hint'], result['protocol'], result['signal_type'], json.dumps(result['attributes'], separators=(',', ':'), sort_keys=True)))
            classified += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    print()
    print('=== CLASSIFICATION V3 ===')
    print(f'classified={classified}')
    total = conn.execute('\n        SELECT COUNT(*)\n        FROM event_enrichment\n    ').fetchone()[0]
    eligible = conn.execute('\n        SELECT COUNT(*)\n        FROM event_enrichment\n        WHERE attention_eligible = 1\n    ').fetchone()[0]
    suppressed = conn.execute('\n        SELECT COUNT(*)\n        FROM event_enrichment\n        WHERE attention_eligible = 0\n    ').fetchone()[0]
    unknown = conn.execute("\n        SELECT COUNT(*)\n        FROM event_enrichment\n        WHERE family = 'unknown'\n    ").fetchone()[0]
    print(f'enriched_total={total}')
    print(f'attention_eligible={eligible}')
    print(f'suppressed={suppressed}')
    print(f'unknown={unknown}')
    print()
    print('=== BGP ENTITY CHECK ===')
    for row in conn.execute("\n        SELECT\n            r.timestamp,\n            e.vendor_hint,\n            e.device,\n            e.event_code,\n            e.entity_key,\n            e.state,\n            e.signal_type,\n            e.attributes_json\n\n        FROM event_enrichment AS e\n\n        JOIN recent_events AS r\n            ON r.id = e.event_id\n\n        WHERE e.protocol = 'bgp'\n\n        ORDER BY r.timestamp_epoch_ms DESC\n\n        LIMIT 40\n    "):
        ts, vendor, device, code, key, state, signal_type, attrs = row
        print()
        print(f'{ts} vendor={vendor} device={device}')
        print(f'code={code} state={state} signal={signal_type}')
        print(f'key={key}')
        print(f'attrs={attrs}')
    print()
    print('=== BGP KEY CONSOLIDATION ===')
    for key, count in conn.execute("\n        SELECT\n            entity_key,\n            COUNT(*)\n\n        FROM event_enrichment\n\n        WHERE\n            protocol = 'bgp'\n            AND entity_key IS NOT NULL\n\n        GROUP BY entity_key\n\n        ORDER BY COUNT(*) DESC\n    "):
        print(f'{count:5d}  {key}')
    print()
    print('=== SIGNAL TYPES ===')
    for signal_type, count in conn.execute('\n        SELECT\n            signal_type,\n            COUNT(*)\n\n        FROM event_enrichment\n\n        GROUP BY signal_type\n\n        ORDER BY COUNT(*) DESC\n    '):
        print(f'{count:7d}  {signal_type}')
    conn.close()
    return 0
if __name__ == '__main__':
    sys.exit(main())
