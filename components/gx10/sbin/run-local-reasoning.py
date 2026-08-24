#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import socket
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

try:
    from runtime_config import load_runtime_config
except ModuleNotFoundError as exc:
    if exc.name != 'runtime_config':
        raise
    load_runtime_config = None


DB = load_runtime_config().database_path if load_runtime_config else None
CONFIG_PATH = Path('/etc/network-log-gx10/reasoning-runtime-v2.json')
PROMPT_PATH = Path('/etc/network-log-gx10/incident-assessment-v2.txt')
OUTPUT_SCHEMA_PATH = Path(
    '/etc/network-log-gx10/incident-assessment-output-v2.json'
)
OLLAMA_ENDPOINT = 'http://127.0.0.1:11434/api/chat'
PROMPT_SHA256 = 'c24a1e4a5af021ea66475cdb77c792b19f023caf93f344f64be4dedf1ebb634c'
OUTPUT_SCHEMA_SHA256 = (
    '1ec4e28d0d18320c7469d4f1bb26a5c766515ff008c5803d24ce214ded69928a'
)
MODEL_MANIFEST_SHA256 = (
    'c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb'
)
MODEL_CONFIG_DIGEST = (
    'sha256:f0988ff50a2458c598ff6b1b87b94d0f5c44d73061c2795391878b00b2285e11'
)
MODEL_REFERENCE = 'gemma4:latest'
MODEL_VERSION = 'ollama-gemma4-c6eb396d-v1'
PROMPT_VERSION = 'incident-assessment-v2'
VERSION_CREATED_AT = '2026-08-24T08:41:00+00:00'
OUTPUT_SCHEMA_VERSION = 2
MAX_ARTIFACT_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 128 * 1024
MAX_RESULT_BYTES = 16 * 1024
REQUEST_TIMEOUT_SECONDS = 120
TAG_RE = re.compile(r'^[a-z0-9][a-z0-9._-]*$')
CHANGE_ACTION_RE = re.compile(
    r'\b(?:restart|reload|reset|clear|change|configure|disable|enable|bounce|reseat)\b',
    re.IGNORECASE,
)
READ_ONLY_ACTION_RE = re.compile(
    r'^(?:check|verify|review|inspect|monitor|show|confirm|query|compare|collect|examine)\b',
    re.IGNORECASE,
)
TERMINAL_FAILURES = {
    'INFERENCE_UNAVAILABLE': 'inference_unavailable',
    'INFERENCE_TIMEOUT': 'inference_timeout',
    'TRANSPORT_ERROR': 'transport_error',
    'INVALID_RESPONSE': 'invalid_response',
    'INVALID_OUTPUT': 'invalid_output',
}
EXPECTED_CONFIG_KEYS = {
    'config_version',
    'model_config_digest',
    'model_manifest_sha256',
    'model_reference',
    'model_version',
    'prompt_version',
    'provider',
    'request_options',
}
EXPECTED_OUTPUT_KEYS = {
    'schema',
    'schema_version',
    'packet_id',
    'incident_id',
    'disposition',
    'severity',
    'confidence',
    'title',
    'summary',
    'likely_causes',
    'recommended_actions',
    'tags',
}
DISPOSITIONS = {
    'action_required',
    'monitor',
    'resolved_no_action',
    'insufficient_evidence',
}
SEVERITIES = {'critical', 'high', 'medium', 'low', 'informational'}
ACTION_RISKS = {'read_only', 'reversible', 'change_requires_approval'}
FORBIDDEN_PACKET_KEYS = {
    'event_json',
    'local_path',
    'message',
    'raw_message',
    'remote_path',
    'source_file',
    'source_path',
}
REQUIRED_COLUMNS = {
    'reasoning_packets': {
        'packet_id',
        'incident_id',
        'priority',
        'basis_last_seen_epoch_ms',
        'packet_json',
        'packet_sha256',
    },
    'reasoning_model_versions': {
        'model_version',
        'provider',
        'model_reference',
        'manifest_sha256',
        'config_digest',
        'request_options_json',
        'created_at',
    },
    'reasoning_prompt_versions': {
        'prompt_version',
        'system_prompt_sha256',
        'output_schema_sha256',
        'output_schema_version',
        'created_at',
    },
    'reasoning_runs': {
        'run_id',
        'packet_id',
        'model_version',
        'prompt_version',
        'attempt_number',
        'request_sha256',
        'status',
        'started_at',
        'completed_at',
        'error_code',
        'diagnostics_json',
    },
    'reasoning_results': {
        'run_id',
        'packet_id',
        'incident_id',
        'schema_version',
        'disposition',
        'severity',
        'confidence',
        'title',
        'summary',
        'result_json',
        'result_sha256',
        'created_at',
    },
}


class ReasoningError(ValueError):
    pass


class InferenceFailure(ReasoningError):
    def __init__(self, status, diagnostics=None):
        super().__init__(status)
        if status not in TERMINAL_FAILURES:
            raise ValueError('invalid inference failure status')
        self.status = status
        self.diagnostics = diagnostics or {}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def canonical_json(value):
    return json.dumps(value, separators=(',', ':'), sort_keys=True)


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha256_text(value):
    return sha256_bytes(value.encode('utf-8'))


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def read_exact_artifact(path, expected_sha256):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ReasoningError('reasoning runtime artifact is not a regular file')
    if path.stat().st_size > MAX_ARTIFACT_BYTES:
        raise ReasoningError('reasoning runtime artifact is too large')
    value = path.read_bytes()
    if sha256_bytes(value) != expected_sha256:
        raise ReasoningError('reasoning runtime artifact hash differs')
    try:
        return value.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ReasoningError('reasoning runtime artifact is not UTF-8') from exc


def read_json_artifact(path, expected_sha256=None):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ReasoningError('reasoning JSON artifact is not a regular file')
    if path.stat().st_size > MAX_ARTIFACT_BYTES:
        raise ReasoningError('reasoning JSON artifact is too large')
    raw = path.read_bytes()
    if expected_sha256 is not None and sha256_bytes(raw) != expected_sha256:
        raise ReasoningError('reasoning JSON artifact hash differs')
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReasoningError('reasoning JSON artifact is invalid') from exc
    if not isinstance(value, dict):
        raise ReasoningError('reasoning JSON artifact is not an object')
    return value


def load_runtime_artifacts(config_path, prompt_path, output_schema_path):
    config = read_json_artifact(config_path)
    if set(config) != EXPECTED_CONFIG_KEYS:
        raise ReasoningError('reasoning runtime configuration keys differ')
    if (
        config['config_version'] != 2
        or config['provider'] != 'ollama'
        or config['model_reference'] != MODEL_REFERENCE
        or config['model_version'] != MODEL_VERSION
        or config['model_manifest_sha256'] != MODEL_MANIFEST_SHA256
        or config['model_config_digest'] != MODEL_CONFIG_DIGEST
        or config['prompt_version'] != PROMPT_VERSION
    ):
        raise ReasoningError('reasoning runtime configuration differs')
    options = config['request_options']
    if (
        not isinstance(options, dict)
        or set(options) != {'num_ctx', 'num_predict', 'seed', 'temperature'}
        or type(options['num_ctx']) is not int
        or not 1024 <= options['num_ctx'] <= 32768
        or type(options['num_predict']) is not int
        or not 128 <= options['num_predict'] <= 4096
        or type(options['seed']) is not int
        or type(options['temperature']) not in {int, float}
        or options['temperature'] != 0
    ):
        raise ReasoningError('reasoning request options differ')
    prompt = read_exact_artifact(prompt_path, PROMPT_SHA256)
    output_schema = read_json_artifact(
        output_schema_path,
        OUTPUT_SCHEMA_SHA256,
    )
    if (
        output_schema.get('type') != 'object'
        or output_schema.get('additionalProperties') is not False
        or set(output_schema.get('required', ())) != EXPECTED_OUTPUT_KEYS
        or set(output_schema.get('properties', {})) != EXPECTED_OUTPUT_KEYS
    ):
        raise ReasoningError('reasoning output schema differs')
    return config, prompt, output_schema


def validate_database_contract(connection):
    for table, expected in REQUIRED_COLUMNS.items():
        columns = {
            row[1]
            for row in connection.execute(f'PRAGMA table_info({table})')
        }
        if not expected <= columns:
            raise ReasoningError('reasoning execution database schema differs')


def parse_canonical_object(value, label):
    if not isinstance(value, str):
        raise ReasoningError(f'{label} is invalid')
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ReasoningError(f'{label} is invalid') from exc
    if not isinstance(parsed, dict) or canonical_json(parsed) != value:
        raise ReasoningError(f'{label} is not canonical')
    return parsed


def validate_packet_content(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key.casefold() in FORBIDDEN_PACKET_KEYS:
                raise ReasoningError('reasoning packet contains forbidden content')
            validate_packet_content(child)
    elif isinstance(value, list):
        for child in value:
            validate_packet_content(child)


def register_versions(connection, config):
    options_json = canonical_json(config['request_options'])
    connection.execute(
        '''
        INSERT OR IGNORE INTO reasoning_model_versions (
            model_version, provider, model_reference, manifest_sha256,
            config_digest, request_options_json, created_at
        ) VALUES (?, 'ollama', ?, ?, ?, ?, ?)
        ''',
        (
            MODEL_VERSION,
            MODEL_REFERENCE,
            MODEL_MANIFEST_SHA256,
            MODEL_CONFIG_DIGEST,
            options_json,
            VERSION_CREATED_AT,
        ),
    )
    connection.execute(
        '''
        INSERT OR IGNORE INTO reasoning_prompt_versions (
            prompt_version, system_prompt_sha256, output_schema_sha256,
            output_schema_version, created_at
        ) VALUES (?, ?, ?, ?, ?)
        ''',
        (
            PROMPT_VERSION,
            PROMPT_SHA256,
            OUTPUT_SCHEMA_SHA256,
            OUTPUT_SCHEMA_VERSION,
            VERSION_CREATED_AT,
        ),
    )
    model = connection.execute(
        'SELECT * FROM reasoning_model_versions WHERE model_version = ?',
        (MODEL_VERSION,),
    ).fetchone()
    prompt = connection.execute(
        'SELECT * FROM reasoning_prompt_versions WHERE prompt_version = ?',
        (PROMPT_VERSION,),
    ).fetchone()
    if model is None or tuple(model) != (
        MODEL_VERSION,
        'ollama',
        MODEL_REFERENCE,
        MODEL_MANIFEST_SHA256,
        MODEL_CONFIG_DIGEST,
        options_json,
        VERSION_CREATED_AT,
    ):
        raise ReasoningError('registered reasoning model version differs')
    if prompt is None or tuple(prompt) != (
        PROMPT_VERSION,
        PROMPT_SHA256,
        OUTPUT_SCHEMA_SHA256,
        OUTPUT_SCHEMA_VERSION,
        VERSION_CREATED_AT,
    ):
        raise ReasoningError('registered reasoning prompt version differs')


def validate_existing_state(connection):
    packet_incidents = {}
    packet_values = {}
    for row in connection.execute(
        'SELECT packet_id, incident_id, packet_json, packet_sha256 '
        'FROM reasoning_packets ORDER BY packet_id'
    ):
        packet = parse_canonical_object(row['packet_json'], 'stored reasoning packet')
        validate_packet_content(packet)
        if (
            sha256_text(row['packet_json']) != row['packet_sha256']
            or packet.get('packet_id') != row['packet_id']
            or packet.get('incident', {}).get('incident_id') != row['incident_id']
        ):
            raise ReasoningError('stored reasoning packet differs')
        packet_incidents[row['packet_id']] = row['incident_id']
        packet_values[row['packet_id']] = packet

    results = {
        row['run_id']: row
        for row in connection.execute(
            'SELECT * FROM reasoning_results ORDER BY run_id'
        )
    }
    for row in connection.execute('SELECT * FROM reasoning_runs ORDER BY run_id'):
        diagnostics = parse_canonical_object(
            row['diagnostics_json'],
            'reasoning run diagnostics',
        )
        if diagnostics is None or row['packet_id'] not in packet_incidents:
            raise ReasoningError('stored reasoning run differs')
        result = results.get(row['run_id'])
        if row['status'] == 'STARTED':
            if row['completed_at'] is not None or row['error_code'] is not None or result:
                raise ReasoningError('started reasoning run differs')
        elif row['status'] == 'SUCCEEDED':
            if row['completed_at'] is None or row['error_code'] is not None or result is None:
                raise ReasoningError('successful reasoning run differs')
        elif row['status'] in TERMINAL_FAILURES:
            if (
                row['completed_at'] is None
                or row['error_code'] != TERMINAL_FAILURES[row['status']]
                or result is not None
            ):
                raise ReasoningError('failed reasoning run differs')
        else:
            raise ReasoningError('reasoning run status differs')

    run_ids = {
        row[0]
        for row in connection.execute('SELECT run_id FROM reasoning_runs')
    }
    for run_id, row in results.items():
        result = parse_canonical_object(row['result_json'], 'reasoning result')
        validated_result = validate_output(
            result,
            row['packet_id'],
            row['incident_id'],
            packet_values.get(row['packet_id'], {}),
        )
        if (
            run_id not in run_ids
            or sha256_text(row['result_json']) != row['result_sha256']
            or result.get('packet_id') != row['packet_id']
            or result.get('incident_id') != row['incident_id']
            or packet_incidents.get(row['packet_id']) != row['incident_id']
            or result.get('schema_version') != row['schema_version']
            or result.get('disposition') != row['disposition']
            or result.get('severity') != row['severity']
            or result.get('confidence') != row['confidence']
            or result.get('title') != row['title']
            or result.get('summary') != row['summary']
            or validated_result != row['result_json']
        ):
            raise ReasoningError('stored reasoning result differs')


def allowed_output_tags(packet):
    candidates = set(packet.get('wake', {}).get('reasons', ()))
    incident = packet.get('incident', {})
    for key in (
        'event_family',
        'protocol',
        'entity_type',
        'severity',
        'status',
        'last_observation_state',
    ):
        candidates.add(incident.get(key))
    for evidence in packet.get('evidence', ()):
        if not isinstance(evidence, dict):
            continue
        for key in ('event_code', 'signal_type', 'observation_state'):
            candidates.add(evidence.get(key))
    return sorted(
        value.casefold()
        for value in candidates
        if isinstance(value, str) and TAG_RE.fullmatch(value.casefold())
    )


def request_object(config, prompt, output_schema, packet, packet_sha256):
    user_payload = canonical_json(
        {
            'allowed_tags': allowed_output_tags(packet),
            'packet': packet,
            'packet_sha256': packet_sha256,
        }
    )
    return {
        'format': output_schema,
        'messages': [
            {'content': prompt, 'role': 'system'},
            {'content': user_payload, 'role': 'user'},
        ],
        'model': config['model_reference'],
        'options': config['request_options'],
        'stream': False,
        'think': False,
    }


def run_identifier(packet_id, packet_sha256, attempt_number=1):
    material = canonical_json(
        [
            'reasoning-run-v1',
            packet_id,
            packet_sha256,
            MODEL_VERSION,
            PROMPT_VERSION,
            attempt_number,
        ]
    )
    return 'run-v1-' + sha256_text(material)[:32]


def reserve_next_run(connection, config, prompt, output_schema, started_at):
    register_versions(connection, config)
    validate_existing_state(connection)
    packet = connection.execute(
        '''
        SELECT * FROM reasoning_packets AS packet
        WHERE NOT EXISTS (
            SELECT 1 FROM reasoning_runs AS run
            WHERE run.packet_id = packet.packet_id
              AND run.model_version = ?
              AND run.prompt_version = ?
              AND run.attempt_number = 1
        )
        ORDER BY packet.priority DESC,
                 packet.basis_last_seen_epoch_ms,
                 packet.packet_id
        LIMIT 1
        ''',
        (MODEL_VERSION, PROMPT_VERSION),
    ).fetchone()
    if packet is None:
        return None
    packet_value = parse_canonical_object(packet['packet_json'], 'reasoning packet')
    if sha256_text(packet['packet_json']) != packet['packet_sha256']:
        raise ReasoningError('reasoning packet hash differs')
    request = request_object(
        config,
        prompt,
        output_schema,
        packet_value,
        packet['packet_sha256'],
    )
    request_json = canonical_json(request)
    run_id = run_identifier(packet['packet_id'], packet['packet_sha256'])
    connection.execute(
        '''
        INSERT INTO reasoning_runs (
            run_id, packet_id, model_version, prompt_version, attempt_number,
            request_sha256, status, started_at, completed_at, error_code,
            diagnostics_json
        ) VALUES (?, ?, ?, ?, 1, ?, 'STARTED', ?, NULL, NULL, '{}')
        ''',
        (
            run_id,
            packet['packet_id'],
            MODEL_VERSION,
            PROMPT_VERSION,
            sha256_text(request_json),
            started_at,
        ),
    )
    return {
        'run_id': run_id,
        'packet_id': packet['packet_id'],
        'incident_id': packet['incident_id'],
        'packet': packet_value,
        'request_json': request_json,
    }


def ollama_request(request_json, endpoint=OLLAMA_ENDPOINT):
    parsed = urllib.parse.urlsplit(endpoint)
    if (
        parsed.scheme != 'http'
        or parsed.hostname != '127.0.0.1'
        or parsed.port != 11434
        or parsed.path != '/api/chat'
        or parsed.query
        or parsed.fragment
    ):
        raise InferenceFailure('TRANSPORT_ERROR')
    request = urllib.request.Request(
        endpoint,
        data=request_json.encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                raise InferenceFailure(
                    'INFERENCE_UNAVAILABLE',
                    {'http_status': response.status},
                )
            payload = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if exc.code in {408, 504}:
            raise InferenceFailure(
                'INFERENCE_TIMEOUT',
                {'http_status': exc.code},
            ) from exc
        if exc.code in {429, 502, 503}:
            raise InferenceFailure(
                'INFERENCE_UNAVAILABLE',
                {'http_status': exc.code},
            ) from exc
        raise InferenceFailure(
            'TRANSPORT_ERROR',
            {'http_status': exc.code},
        ) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise InferenceFailure('INFERENCE_TIMEOUT') from exc
    except (OSError, urllib.error.URLError) as exc:
        raise InferenceFailure('INFERENCE_UNAVAILABLE') from exc
    if len(payload) > MAX_RESPONSE_BYTES:
        raise InferenceFailure('INVALID_RESPONSE')
    return payload


def response_diagnostics(response):
    diagnostics = {}
    for key in (
        'done_reason',
        'total_duration',
        'load_duration',
        'prompt_eval_count',
        'prompt_eval_duration',
        'eval_count',
        'eval_duration',
    ):
        value = response.get(key)
        if type(value) in {str, int} and not isinstance(value, bool):
            if isinstance(value, str) and len(value) > 64:
                continue
            if isinstance(value, int) and value < 0:
                continue
            diagnostics[key] = value
    return diagnostics


def parse_response(payload):
    if not isinstance(payload, bytes):
        raise InferenceFailure('INVALID_RESPONSE')
    try:
        response = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InferenceFailure('INVALID_RESPONSE') from exc
    if (
        not isinstance(response, dict)
        or response.get('model') != MODEL_REFERENCE
        or response.get('done') is not True
        or not isinstance(response.get('message'), dict)
        or response['message'].get('role') != 'assistant'
        or not isinstance(response['message'].get('content'), str)
    ):
        raise InferenceFailure('INVALID_RESPONSE')
    content = response['message']['content']
    if len(content.encode('utf-8')) > MAX_RESULT_BYTES:
        raise InferenceFailure('INVALID_OUTPUT', response_diagnostics(response))
    try:
        result = json.loads(content)
    except json.JSONDecodeError as exc:
        raise InferenceFailure(
            'INVALID_OUTPUT',
            response_diagnostics(response),
        ) from exc
    if not isinstance(result, dict):
        raise InferenceFailure('INVALID_OUTPUT', response_diagnostics(response))
    return result, response_diagnostics(response)


def require_string(value, minimum, maximum, label, single_line=False):
    if (
        not isinstance(value, str)
        or not minimum <= len(value) <= maximum
        or (single_line and ('\n' in value or '\r' in value))
    ):
        raise ReasoningError(f'invalid {label}')


def validate_output(result, packet_id, incident_id, packet):
    try:
        if set(result) != EXPECTED_OUTPUT_KEYS:
            raise ReasoningError('invalid output keys')
        if result['schema'] != 'gx10-incident-assessment':
            raise ReasoningError('invalid output schema')
        if result['schema_version'] != OUTPUT_SCHEMA_VERSION:
            raise ReasoningError('invalid output schema version')
        if result['packet_id'] != packet_id or result['incident_id'] != incident_id:
            raise ReasoningError('output identity differs')
        if result['disposition'] not in DISPOSITIONS:
            raise ReasoningError('invalid output disposition')
        if result['severity'] not in SEVERITIES:
            raise ReasoningError('invalid output severity')
        if type(result['confidence']) is not int or not 0 <= result['confidence'] <= 95:
            raise ReasoningError('invalid output confidence')
        if (
            result['disposition'] == 'action_required'
            and result['confidence'] < 50
        ):
            raise ReasoningError('action-required output confidence differs')
        require_string(result['title'], 1, 160, 'output title', single_line=True)
        require_string(result['summary'], 1, 4000, 'output summary')
        causes = result['likely_causes']
        if not isinstance(causes, list) or len(causes) > 3:
            raise ReasoningError('invalid output likely causes')
        for cause in causes:
            if not isinstance(cause, dict) or set(cause) != {
                'cause', 'basis', 'confidence'
            }:
                raise ReasoningError('invalid output likely cause')
            require_string(cause['cause'], 1, 300, 'output cause')
            require_string(cause['basis'], 1, 500, 'output cause basis')
            if type(cause['confidence']) is not int or not 1 <= cause['confidence'] <= 95:
                raise ReasoningError('invalid output cause confidence')
        actions = result['recommended_actions']
        if not isinstance(actions, list) or len(actions) > 5:
            raise ReasoningError('invalid output actions')
        if result['disposition'] == 'action_required' and (
            len(actions) < 2
            or not isinstance(actions[0], dict)
            or actions[0].get('risk') != 'read_only'
        ):
            raise ReasoningError('invalid action-required output actions')
        for action in actions:
            if not isinstance(action, dict) or set(action) != {
                'action', 'priority', 'risk'
            }:
                raise ReasoningError('invalid output action')
            require_string(action['action'], 8, 500, 'output action text')
            if action['action'].casefold() in ACTION_RISKS:
                raise ReasoningError('invalid output action text')
            if type(action['priority']) is not int or not 1 <= action['priority'] <= 5:
                raise ReasoningError('invalid output action priority')
            if action['risk'] not in ACTION_RISKS:
                raise ReasoningError('invalid output action risk')
            if (
                CHANGE_ACTION_RE.search(action['action'])
                and action['risk'] != 'change_requires_approval'
            ):
                raise ReasoningError('output change action lacks approval label')
            if (
                READ_ONLY_ACTION_RE.search(action['action'])
                and not CHANGE_ACTION_RE.search(action['action'])
                and action['risk'] != 'read_only'
            ):
                raise ReasoningError('output read-only action risk differs')
        tags = result['tags']
        if (
            not isinstance(tags, list)
            or len(tags) > 8
            or len(set(tags)) != len(tags)
            or any(
                not isinstance(tag, str)
                or len(tag) > 64
                or TAG_RE.fullmatch(tag) is None
                for tag in tags
            )
        ):
            raise ReasoningError('invalid output tags')
        if not set(tags) <= set(allowed_output_tags(packet)):
            raise ReasoningError('output tags are not packet-derived')
        reasons = packet.get('wake', {}).get('reasons')
        if not isinstance(reasons, list):
            raise ReasoningError('invalid packet wake reasons')
        if 'critical_condition' in reasons:
            if result['severity'] != 'critical':
                raise ReasoningError('critical output severity differs')
        elif result['severity'] == 'critical' or 'critical_condition' in tags:
            raise ReasoningError('noncritical output severity differs')
        result_json = canonical_json(result)
        if len(result_json.encode('utf-8')) > MAX_RESULT_BYTES:
            raise ReasoningError('reasoning output is too large')
        return result_json
    except (KeyError, TypeError) as exc:
        raise ReasoningError('reasoning output differs') from exc


def finalize_failure(database, run_id, failure, completed_at):
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA busy_timeout=5000')
        connection.execute('BEGIN IMMEDIATE')
        row = connection.execute(
            'SELECT status FROM reasoning_runs WHERE run_id = ?',
            (run_id,),
        ).fetchone()
        if row is None or row['status'] != 'STARTED':
            raise ReasoningError('reasoning run reservation differs')
        connection.execute(
            '''
            UPDATE reasoning_runs
            SET status = ?, completed_at = ?, error_code = ?,
                diagnostics_json = ?
            WHERE run_id = ?
            ''',
            (
                failure.status,
                completed_at,
                TERMINAL_FAILURES[failure.status],
                canonical_json(failure.diagnostics),
                run_id,
            ),
        )
        validate_existing_state(connection)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def finalize_success(database, reserved, result, diagnostics, completed_at):
    result_json = validate_output(
        result,
        reserved['packet_id'],
        reserved['incident_id'],
        reserved['packet'],
    )
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA busy_timeout=5000')
        connection.execute('BEGIN IMMEDIATE')
        row = connection.execute(
            'SELECT status FROM reasoning_runs WHERE run_id = ?',
            (reserved['run_id'],),
        ).fetchone()
        if row is None or row['status'] != 'STARTED':
            raise ReasoningError('reasoning run reservation differs')
        connection.execute(
            '''
            INSERT INTO reasoning_results (
                run_id, packet_id, incident_id, schema_version,
                disposition, severity, confidence, title, summary,
                result_json, result_sha256, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                reserved['run_id'],
                reserved['packet_id'],
                reserved['incident_id'],
                OUTPUT_SCHEMA_VERSION,
                result['disposition'],
                result['severity'],
                result['confidence'],
                result['title'],
                result['summary'],
                result_json,
                sha256_text(result_json),
                completed_at,
            ),
        )
        connection.execute(
            '''
            UPDATE reasoning_runs
            SET status = 'SUCCEEDED', completed_at = ?, error_code = NULL,
                diagnostics_json = ?
            WHERE run_id = ?
            ''',
            (
                completed_at,
                canonical_json(diagnostics),
                reserved['run_id'],
            ),
        )
        validate_existing_state(connection)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def run(
    database=DB,
    *,
    config_path=CONFIG_PATH,
    prompt_path=PROMPT_PATH,
    output_schema_path=OUTPUT_SCHEMA_PATH,
    transport=ollama_request,
    now=utc_now,
):
    if database is None:
        raise ReasoningError('reasoning database is not configured')
    try:
        config, prompt, output_schema = load_runtime_artifacts(
            config_path,
            prompt_path,
            output_schema_path,
        )
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('PRAGMA busy_timeout=5000')
            if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ReasoningError('reasoning execution quick_check failed')
            if connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
                raise ReasoningError('reasoning execution foreign_key_check failed')
            validate_database_contract(connection)
            connection.execute('BEGIN IMMEDIATE')
            reserved = reserve_next_run(
                connection,
                config,
                prompt,
                output_schema,
                now(),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        if reserved is None:
            print('REASONING_RUN pending=0 invoked=0')
            print('GX10_REASONING_RUN=PASS')
            return 0

        try:
            payload = transport(reserved['request_json'])
            result, diagnostics = parse_response(payload)
            try:
                finalize_success(
                    database,
                    reserved,
                    result,
                    diagnostics,
                    now(),
                )
            except ReasoningError as exc:
                failure = InferenceFailure('INVALID_OUTPUT')
                finalize_failure(database, reserved['run_id'], failure, now())
                raise exc
        except InferenceFailure as failure:
            finalize_failure(database, reserved['run_id'], failure, now())
            print(
                'GX10_REASONING_RUN=SAFE_FAILURE '
                f'status={failure.status}',
                file=sys.stderr,
            )
            return 1
        except ReasoningError:
            print(
                'GX10_REASONING_RUN=SAFE_FAILURE status=INVALID_OUTPUT',
                file=sys.stderr,
            )
            return 1

        print(
            f"REASONING_RUN run_id={reserved['run_id']} "
            f"packet_id={reserved['packet_id']} status=SUCCEEDED"
        )
        print('GX10_REASONING_RUN=PASS')
        return 0
    except (OSError, sqlite3.Error, ReasoningError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(run())
