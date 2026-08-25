#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


DATASOURCE_UID = 'efvaztlrk8ow0a'


LATEST_CTE = '''WITH latest AS (
    SELECT
        incident_id,
        argMax(device, tuple(snapshot_version, snapshot_id)) AS device,
        argMax(entity_name, tuple(snapshot_version, snapshot_id)) AS entity_name,
        argMax(entity_type, tuple(snapshot_version, snapshot_id)) AS entity_type,
        argMax(event_family, tuple(snapshot_version, snapshot_id)) AS event_family,
        argMax(protocol, tuple(snapshot_version, snapshot_id)) AS protocol,
        argMax(lifecycle_status, tuple(snapshot_version, snapshot_id)) AS lifecycle_status,
        argMax(severity, tuple(snapshot_version, snapshot_id)) AS severity,
        argMax(first_seen, tuple(snapshot_version, snapshot_id)) AS first_seen,
        argMax(last_seen, tuple(snapshot_version, snapshot_id)) AS last_seen,
        argMax(resolved_at, tuple(snapshot_version, snapshot_id)) AS resolved_at,
        argMax(occurrence_count, tuple(snapshot_version, snapshot_id)) AS occurrence_count,
        argMax(state_change_count, tuple(snapshot_version, snapshot_id)) AS state_change_count,
        argMax(last_observation_state, tuple(snapshot_version, snapshot_id)) AS last_observation_state,
        argMax(interface_flap, tuple(snapshot_version, snapshot_id)) AS interface_flap,
        argMax(title, tuple(snapshot_version, snapshot_id)) AS title
    FROM observability.incident_updates
    GROUP BY incident_id
)'''


def query(sql):
    return {
        'kind': 'PanelQuery',
        'spec': {
            'query': {
                'kind': 'DataQuery',
                'group': 'grafana-clickhouse-datasource',
                'version': 'v0',
                'datasource': {'name': DATASOURCE_UID},
                'spec': {
                    'editorType': 'sql',
                    'format': 1,
                    'meta': {
                        'builderOptions': {
                            'columns': [],
                            'database': 'observability',
                            'filters': [],
                            'limit': 500,
                            'meta': {'otelEnabled': False},
                            'mode': 'list',
                            'orderBy': [],
                            'queryType': 'table',
                            'table': 'incident_updates',
                        }
                    },
                    'pluginVersion': '4.20.0',
                    'queryType': 'table',
                    'rawSql': sql,
                },
            },
            'refId': 'A',
            'hidden': False,
        },
    }


def data(sql):
    return {
        'kind': 'QueryGroup',
        'spec': {
            'queries': [query(sql)],
            'transformations': [],
            'queryOptions': {},
        },
    }


def stat_panel(identifier, title, description, sql, color):
    return {
        'kind': 'Panel',
        'spec': {
            'id': identifier,
            'title': title,
            'description': description,
            'links': [],
            'data': data(sql),
            'vizConfig': {
                'kind': 'VizConfig',
                'group': 'stat',
                'version': '13.1.1',
                'spec': {
                    'options': {
                        'colorMode': 'background',
                        'graphMode': 'none',
                        'justifyMode': 'center',
                        'orientation': 'auto',
                        'percentChangeColorMode': 'standard',
                        'reduceOptions': {
                            'calcs': ['lastNotNull'],
                            'fields': '',
                            'values': False,
                        },
                        'showPercentChange': False,
                        'textMode': 'value_and_name',
                        'wideLayout': True,
                    },
                    'fieldConfig': {
                        'defaults': {
                            'color': {'mode': 'fixed', 'fixedColor': color},
                            'thresholds': {
                                'mode': 'absolute',
                                'steps': [{'value': 0, 'color': color}],
                            },
                        },
                        'overrides': [],
                    },
                },
            },
        },
    }


def field_override(name, properties):
    return {
        'matcher': {'id': 'byName', 'options': name},
        'properties': [
            {'id': key, 'value': value}
            for key, value in properties
        ],
    }


def table_panel(identifier, title, description, sql, fields):
    overrides = []
    for name, width in fields:
        properties = [('custom.width', width)]
        if name in {'First Seen', 'Last Activity', 'Resolved'}:
            properties.insert(0, ('unit', 'dateTimeFromNow'))
        if name in {'Severity', 'State', 'Resolution'}:
            properties.append((
                'custom.cellOptions',
                {'type': 'color-background', 'mode': 'basic'},
            ))
        if name == 'Severity':
            properties.append((
                'mappings',
                [{
                    'type': 'value',
                    'options': {
                        'emergency': {'color': 'dark-red', 'index': 0, 'text': 'EMERGENCY'},
                        'alert': {'color': 'dark-red', 'index': 1, 'text': 'ALERT'},
                        'critical': {'color': 'red', 'index': 2, 'text': 'CRITICAL'},
                        'error': {'color': 'orange', 'index': 3, 'text': 'ERROR'},
                        'warning': {'color': 'yellow', 'index': 4, 'text': 'WARNING'},
                        'notice': {'color': 'blue', 'index': 5, 'text': 'NOTICE'},
                        'informational': {'color': 'green', 'index': 6, 'text': 'INFO'},
                        'unknown': {'color': 'gray', 'index': 7, 'text': 'UNKNOWN'},
                    },
                }],
            ))
        if name in {'State', 'Resolution'}:
            properties.append((
                'mappings',
                [{
                    'type': 'value',
                    'options': {
                        'CANDIDATE': {'color': 'purple', 'index': 0, 'text': 'NEW'},
                        'OPEN': {'color': 'red', 'index': 1, 'text': 'OPEN'},
                        'RECOVERING': {'color': 'yellow', 'index': 2, 'text': 'RECOVERING'},
                        'RESOLVED': {'color': 'green', 'index': 3, 'text': 'RESOLVED'},
                    },
                }],
            ))
        if name in {'Event', 'Subject'}:
            properties.append(('custom.wrapText', True))
        overrides.append(field_override(name, properties))
    return {
        'kind': 'Panel',
        'spec': {
            'id': identifier,
            'title': title,
            'description': description,
            'links': [],
            'data': data(sql),
            'vizConfig': {
                'kind': 'VizConfig',
                'group': 'table',
                'version': '13.1.1',
                'spec': {
                    'options': {
                        'cellHeight': 'md',
                        'showHeader': True,
                        'enablePagination': True,
                        'frozenColumns': {'left': 2},
                        'footer': {
                            'countRows': False,
                            'enablePagination': True,
                            'fields': '',
                            'reducer': ['sum'],
                            'show': False,
                        },
                    },
                    'fieldConfig': {
                        'defaults': {
                            'custom': {
                                'align': 'left',
                                'cellOptions': {'type': 'auto'},
                                'filterable': True,
                                'inspect': False,
                                'minWidth': 70,
                                'wrapHeaderText': True,
                            }
                        },
                        'overrides': overrides,
                    },
                },
            },
        },
    }


def search_condition(variable):
    value = '${' + variable + ':sqlstring}'
    return (
        f"({value} = '' OR positionCaseInsensitiveUTF8("
        "concat(device, ' ', entity_name, ' ', event_family, ' ', "
        f"protocol, ' ', title, ' ', incident_id), {value}) > 0)"
    )


def severity_condition():
    value = '${severity_filter:sqlstring}'
    return f"({value} = 'all' OR lowerUTF8(severity) = {value})"


def build_document():
    active_filter = (
        "lifecycle_status IN ('CANDIDATE', 'OPEN', 'RECOVERING')\n"
        "  AND interface_flap = false"
    )
    flap_filter = (
        "lifecycle_status IN ('CANDIDATE', 'OPEN', 'RECOVERING')\n"
        "  AND interface_flap = true"
    )
    active_count = (
        LATEST_CTE + "\nSELECT count() AS \"Active Events\"\nFROM latest\n"
        "WHERE " + active_filter
    )
    flap_count = (
        LATEST_CTE + "\nSELECT count() AS \"Active Flaps\"\nFROM latest\n"
        "WHERE " + flap_filter
    )
    resolved_count = (
        LATEST_CTE + "\nSELECT count() AS \"Resolved in Range\"\nFROM latest\n"
        "WHERE lifecycle_status = 'RESOLVED'\n"
        "  AND resolved_at >= $__fromTime\n  AND resolved_at <= $__toTime"
    )
    active_sql = LATEST_CTE + f'''\nSELECT
    severity AS "Severity",
    device AS "Device",
    title AS "Event",
    lifecycle_status AS "State",
    first_seen AS "First Seen",
    last_seen AS "Last Activity",
    dateDiff('minute', first_seen, now()) AS "Age (min)",
    occurrence_count AS "Occurrences",
    event_family AS "Category",
    incident_id AS "Incident ID"
FROM latest
WHERE {active_filter}
  AND {severity_condition()}
  AND {search_condition('active_search')}
ORDER BY multiIf(severity IN ('emergency', 'alert'), 0, severity = 'critical', 1, severity = 'error', 2, severity = 'warning', 3, 4), last_seen DESC
LIMIT 500'''
    flap_sql = LATEST_CTE + f'''\nSELECT
    device AS "Device",
    entity_name AS "Interface",
    last_observation_state AS "Current State",
    lifecycle_status AS "State",
    first_seen AS "First Seen",
    last_seen AS "Last Activity",
    state_change_count AS "Flaps",
    occurrence_count AS "Occurrences",
    dateDiff('minute', first_seen, now()) AS "Age (min)",
    incident_id AS "Incident ID"
FROM latest
WHERE {flap_filter}
  AND {search_condition('flap_search')}
ORDER BY last_seen DESC, state_change_count DESC
LIMIT 500'''
    resolved_sql = LATEST_CTE + f'''\nSELECT
    severity AS "Severity",
    device AS "Device",
    title AS "Event",
    lifecycle_status AS "Resolution",
    first_seen AS "First Seen",
    resolved_at AS "Resolved",
    dateDiff('minute', first_seen, assumeNotNull(resolved_at)) AS "Duration (min)",
    occurrence_count AS "Occurrences",
    event_family AS "Category",
    if(interface_flap, 'yes', 'no') AS "Interface Flap",
    incident_id AS "Incident ID"
FROM latest
WHERE lifecycle_status = 'RESOLVED'
  AND resolved_at >= $__fromTime
  AND resolved_at <= $__toTime
  AND {severity_condition()}
  AND {search_condition('resolved_search')}
ORDER BY resolved_at DESC
LIMIT 500'''

    elements = {
        'panel-1': stat_panel(1, 'Active Events', 'Current non-flap incidents; active state is never hidden by the dashboard time range.', active_count, 'red'),
        'panel-2': stat_panel(2, 'Interface Flaps', 'Current interface-flap incidents kept in their own operational queue.', flap_count, 'orange'),
        'panel-3': stat_panel(3, 'Resolved', 'Incidents resolved during the selected dashboard time range.', resolved_count, 'green'),
        'panel-4': table_panel(4, 'Active Events', 'One current row per unresolved non-flap incident. Search is server-side and the time picker does not hide persistent incidents.', active_sql, [
            ('Severity', 105), ('Device', 190), ('Event', 330), ('State', 125),
            ('First Seen', 135), ('Last Activity', 135), ('Age (min)', 95),
            ('Occurrences', 95), ('Category', 120), ('Incident ID', 220),
        ]),
        'panel-5': table_panel(5, 'Interface Flaps', 'One current row per device/interface while deterministic state changes continue; recovery moves it to Resolved after the quiet-period gate.', flap_sql, [
            ('Device', 190), ('Interface', 220), ('Current State', 120), ('State', 125),
            ('First Seen', 135), ('Last Activity', 135), ('Flaps', 85),
            ('Occurrences', 95), ('Age (min)', 95), ('Incident ID', 220),
        ]),
        'panel-6': table_panel(6, 'Resolved Events', 'Resolved incident episodes in the selected time range. Records remain searchable history and are not deleted by dashboard actions.', resolved_sql, [
            ('Severity', 105), ('Device', 190), ('Event', 330), ('Resolution', 125),
            ('First Seen', 135), ('Resolved', 135), ('Duration (min)', 110),
            ('Occurrences', 95), ('Category', 120), ('Interface Flap', 110),
            ('Incident ID', 220),
        ]),
    }
    layout = []
    for name, x, y, width, height in (
        ('panel-1', 0, 0, 8, 5),
        ('panel-2', 8, 0, 8, 5),
        ('panel-3', 16, 0, 8, 5),
        ('panel-4', 0, 5, 24, 15),
        ('panel-5', 0, 20, 24, 15),
        ('panel-6', 0, 35, 24, 15),
    ):
        layout.append({
            'kind': 'GridLayoutItem',
            'spec': {
                'x': x, 'y': y, 'width': width, 'height': height,
                'element': {'kind': 'ElementReference', 'name': name},
            },
        })

    variables = []
    for name, label, description in (
        ('active_search', 'Search Active', 'Search device, event, category, protocol, and incident ID.'),
        ('flap_search', 'Search Flaps', 'Search device, interface, and incident ID.'),
        ('resolved_search', 'Search Resolved', 'Search resolved device, event, category, protocol, and incident ID.'),
    ):
        variables.append({
            'kind': 'TextVariable',
            'spec': {
                'name': name,
                'current': {'text': '', 'value': ''},
                'query': '',
                'label': label,
                'hide': 'dontHide',
                'skipUrlSync': False,
                'description': description,
            },
        })
    variables.append({
        'kind': 'CustomVariable',
        'spec': {
            'name': 'severity_filter',
            'query': 'all,emergency,alert,critical,error,warning,notice,informational,unknown',
            'current': {'text': 'All', 'value': 'all'},
            'options': [
                {'text': value.title(), 'value': value}
                for value in ('all', 'emergency', 'alert', 'critical', 'error', 'warning', 'notice', 'informational', 'unknown')
            ],
            'multi': False,
            'includeAll': False,
            'label': 'Severity',
            'hide': 'dontHide',
            'skipUrlSync': False,
            'description': 'Server-side severity filter for Active and Resolved events.',
            'allowCustomValue': False,
        },
    })
    return {
        'kind': 'Dashboard',
        'apiVersion': 'dashboard.grafana.app/v2',
        'metadata': {
            'name': 'ai-incident-analysis-enhanced',
            'namespace': 'default',
        },
        'spec': {
            'annotations': [],
            'cursorSync': 'Off',
            'description': 'Deterministic NOC incident workflow. The original AI dashboard remains available as an unchanged fallback.',
            'editable': True,
            'elements': elements,
            'layout': {'kind': 'GridLayout', 'spec': {'items': layout}},
            'links': [],
            'liveNow': False,
            'preload': False,
            'tags': ['noc', 'incidents', 'lifecycle'],
            'timeSettings': {
                'timezone': 'browser',
                'from': 'now-7d',
                'to': 'now',
                'autoRefresh': '1m',
                'autoRefreshIntervals': ['10s', '30s', '1m', '5m', '15m', '30m', '1h'],
                'hideTimepicker': False,
                'fiscalYearStartMonth': 0,
            },
            'title': 'AI Incident Analysis - Enhanced',
            'variables': variables,
            'preferences': {'layout': {'kind': 'GridLayout', 'spec': {'items': []}}},
        },
        'status': {},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(build_document(), indent=2, ensure_ascii=False) + '\n',
        encoding='utf-8',
    )


if __name__ == '__main__':
    main()
