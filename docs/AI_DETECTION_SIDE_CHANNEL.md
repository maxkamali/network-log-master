# AI Detection Side Channel

## Status and operator contract

Status: `ACTIVE` on the working GX10 system. Current production state is
maintained in `docs/CURRENT_STATE.md`.

The repository implementation consists of the additive `triage-v1.sql` ledger,
the deterministic selector/batcher and strict caller in
`triage-uncovered-events.py`, the one-call coordinator in `run-managed-ai.py`,
versioned Gemma configuration/prompt/schema artifacts, guarded migration and
managed-install integration, existing incident/outbox projection, independent
verification, and regression tests. It adds no dashboard panel, table, event
window, datasource, or Grafana write behavior.

Production rollout used the configured protected SQLite path without publishing
it, retained a root-only sibling backup, passed the complete 215-test GX10
suite locally and from the staged server copy, and ran shadow mode before active
bridging. The first shadow attempt safely retained its batch after a bounded
length-limited response; prompt revision `r2` required compact fields and the
same batch then returned all 24 decisions successfully. Initial active evidence
is 48 validated decisions: 33 `incident`, 15 `ignore`, zero active learned
rules, and 35 ordinary lifecycle incidents. The initial 45-record lifecycle
export passed the collector validation gate.

The side channel reviews important events that reached GX10 but did not qualify
for deterministic incident correlation. A successful model decision may admit
those events into the existing incident lifecycle. The operator must not see a
new dashboard section, record type, or workflow:

- an AI-positive event appears in the existing `Active Events` table
- it uses the existing severity, device, event, detail, state, time, count,
  category, incident-ID, search, and one-click drilldown behavior
- it later appears in the existing `Resolved Events` table
- an AI-negative event remains retained and searchable in the raw log path but
  does not appear as an incident
- the `Interface Flaps` table remains reserved for canonical interface events

Every source event remains durably captured. Side-channel rejection means
"not admitted as an incident," never deletion.

## Confirmed policy

The operator selected this admission policy:

1. Review every uncovered syslog severity 0 through 4 event.
2. Review severity 5 notice events only when the signature is novel or
   repeated.
3. If Gemma is unavailable or produces no valid decision, the affected work
   remains pending. No incident, rejection, or learned rule is inferred from a
   failed model call.
4. Repeated consistent AI decisions may automatically add learned detection
   coverage only for severity 0 through 3 events.
5. Severity 4 and selected severity 5 events always remain AI-mediated unless
   a separately implemented deterministic parser covers them.

Syslog severity uses the conventional numeric order: 0 emergency, 1 alert,
2 critical, 3 error, 4 warning, 5 notice, 6 informational, and 7 debug. The
selector uses the more urgent of the normalized severity and a valid embedded
event-code severity when both exist.

## Existing boundaries retained

The implementation must not alter collector raw capture, ClickHouse raw logs,
the normalized handoff, GX10 replay identity, or existing canonical parsers.
It retains these established rules:

- deterministic normalization remains capture-first
- explicit suppression rules prevent reasoning work but never delete data
- source events and original canonical enrichment are not rewritten
- the model receives untrusted data and has no tools or external network path
- model output is non-executable and must pass an exact versioned schema
- incident identity, correlation, counters, lifecycle, replay safety, and
  transport remain deterministic
- one managed GX10 cycle reserves at most one model invocation
- invalid or unavailable inference cannot fabricate a decision

## End-to-end flow

```text
normalized event
  -> canonical projection
  -> deterministic incident engine
       -> existing incident evidence: existing path, no side-channel duplicate
       -> not incident evidence:
            -> side-channel selector
            -> deterministic signature and aggregation
            -> durable pending batch
            -> one strict local Gemma review
                 -> invalid/unavailable: retain pending work
                 -> not incident-worthy: record decision; no dashboard row
                 -> incident-worthy:
                      -> append effective-classification override
                      -> deterministic incident bridge
                      -> existing incident/evidence/transition tables
                      -> existing lifecycle outbox
                      -> existing incident_updates table
                      -> existing Active/Resolved dashboard windows

consistent positive severity 0-3 decisions
  -> append learned exact-code coverage rule
  -> future matching events receive the same effective classification before
     the deterministic incident engine
  -> future events bypass Gemma while preserving the same incident identity
```

## Eligibility and race boundary

An event is eligible only when all of the following are true:

- canonical projection version is the required installed version
- the deterministic incident cursor has advanced through the event ID
- the event has no row in `incident_evidence`
- `attention_eligible = 1`
- no enabled suppression rule matched
- the event has a usable timestamp and source identity
- its effective severity is 0 through 4, or it is an admitted severity 5
  notice event

Severity 6 and 7 events remain available as supporting/raw context and are not
independently sent to the side channel.

A severity 5 signature is novel when no equal versioned signature exists in
the retained 30-day triage ledger. It is repeated when it has at least three
occurrences or at least two affected devices within 15 minutes. These constants
are versioned policy values, not model choices.

Repetition-only lines have no safe identity. They may be folded into the
immediately preceding record only when source file, source identity, and record
ordering are unambiguous. Otherwise they remain supporting raw observations and
cannot independently create a triage signature.

## Deterministic signature and aggregation

The model does not receive one request per row. Every eligible event is
accounted for by a deterministic aggregate.

`triage-signature-v1` is a SHA-256 identity over:

- normalized vendor and OS family
- event code and event family
- a versioned message-template fingerprint

The message template removes control characters and replaces volatile values
such as timestamps, addresses, counters, and identifiers with typed markers.
It does not execute model-generated regular expressions. Event-code and
template bytes are retained only in the protected local ledger; public logs
emit aggregate counts and hashes only.

The AI decision is signature-wide so one review can cover many devices. The
incident bridge retains per-device membership and creates a separate ordinary
incident identity for each affected device and signature. This keeps the device
column actionable without spending one inference per device.

Each model member contains bounded facts:

- signature ID and event code
- normalized severity and vendor/platform hints
- one bounded representative message template
- occurrence counts over 5 minutes, 1 hour, and 24 hours
- first and last observed timestamps
- number of affected devices
- repeat and rate-change indicators
- whether a prior valid decision exists

No batch exceeds 32 KiB or 24 signatures. Overflow remains pending in priority
order. Design-time read-only sizing of the observed 24-hour workload, after the
two existing
explicit ICMPv6 suppression rules, found 2,630 eligible severity 0-3 rows,
179 device/event-code groups, an average of 4.77 groups per five-minute window,
and an observed maximum of 16. The cap therefore covers the observed peak with
margin while remaining bounded.

## Model request and decision

The side channel uses a new immutable prompt and strict output schema rather
than reusing the single-incident assessment prompt. Log and template text is
explicitly untrusted data. The local model has no tools and no authority to
modify configuration.

Each requested signature must produce exactly one keyed decision:

- `incident_worthy`: `true` or `false`
- `confidence`: integer 0 through 95
- `category`: one allow-listed operational category
- `title`: bounded single-line operator title
- `summary`: bounded factual explanation
- `reason`: bounded basis for the decision
- `tags`: only allow-listed values derived from the request

An `insufficient_evidence` result is permitted but is not a negative decision.
It remains pending for later review. Missing, duplicate, unknown, oversized, or
schema-invalid members invalidate the complete batch; partial model output is
never applied.

The deterministic applicator verifies that the result references the exact
batch and signature hashes. It never accepts model-supplied SQL, regular
expressions, entity keys, lifecycle transitions, timeouts, executable actions,
or detection rules.

## Durable state

An additive schema migration introduces these protected SQLite records:

- immutable signature metadata and template hashes
- append-only batch packets and batch membership
- append-only model attempts with request/provenance hashes
- append-only validated decisions
- an append-only event-to-decision membership ledger
- append-only effective-classification overrides keyed by source event ID
- append-only learned coverage rule versions and activation/revocation records
- a small rebuildable materialized cursor/cache for efficient selection

Every event ID may have at most one effective override and remains globally
unique in incident evidence. Foreign keys, unique constraints, exact schema
inventory, `quick_check`, and `foreign_key_check` remain mandatory.

An unavailable or invalid model attempt is terminal evidence for that attempt,
but its batch remains pending. Retry attempts use bounded backoff of 5, 15, 30,
and then 60 minutes. No retry rewrites the failed attempt. A successful valid
decision closes the pending batch exactly once.

## Effective classification and ordinary incidents

The original `event_enrichment` row is never updated. A validated positive
decision appends an effective-classification override with this fixed generic
contract:

- `entity_type = event_signature`
- `entity_key = event_signature|<device>|<event-code>|<signature-id>`
- `signal_type = degradation`
- `state = detected`
- original event family and severity retained
- decision, prompt, model, packet, and signature provenance stored by hash

The incident engine reads an override when present and otherwise reads the
original canonical fields. `detected` on an `event_signature` is an explicit
immediate-open condition. The model cannot choose or alter that behavior.

For already-cursored events, the triage cursor invokes the same shared
incident-processing functions. Future learned-coverage matches are selected
after the ordinary incident cursor has established that deterministic evidence
does not own them, then receive the fixed override without a model call. The
unique event-evidence constraint makes both paths replay-safe and prevents
double admission.

An AI-positive signature creates one standard incident per device/signature.
All matching batch events become ordinary adverse evidence, so occurrence and
repeat counters reflect the underlying rows. The existing incident lifecycle
outbox exports it without a new record type.

The existing lifecycle outbox projects the latest validated triage title,
summary, and operational category into the ordinary incident record. It uses
the fixed nonempty transport label `event-triage` only in the exported
projection because generic canonical events have no protocol. The dashboard's
existing deterministic-detail fallback therefore displays the triage summary
without a query or panel change. No duplicate assessment is emitted into
`ai_updates`; complete triage provenance remains in the local append-only
ledger.

## Lifecycle

Side-channel incidents use a fixed generic lifecycle until a specialized parser
supplies authoritative recovery semantics:

1. A positive decision opens the incident immediately.
2. New matching events update the same active incident and increment its
   occurrence/repeat counters.
3. After 60 minutes with no matching evidence, the deterministic lifecycle
   moves from `OPEN` to `RECOVERING`.
4. After a further 15 quiet minutes, it moves to `RESOLVED`.
5. A matching event during `RECOVERING` returns the same incident to `OPEN` and
   increments recurrence.
6. A matching event after `RESOLVED` starts a new incident instance under the
   same stable correlation scheme.

These timed transitions contain no model judgment. Promoted generic rules keep
this lifecycle until a future explicit parser defines a recovery event or a
different reviewed monitoring period.

## Decision caching and re-evaluation

Every new event is aggregated, but identical rows do not force new inference.

- A negative decision is reused for an unchanged signature for 60 minutes.
- It is reconsidered immediately if severity becomes more urgent, the template
  changes, the affected-device count expands materially, or the event rate
  crosses a versioned threshold.
- A positive decision applies only to the reviewed membership. New material
  windows are reviewed until the signature is promoted.
- A promoted rule bypasses further triage for matching severity 0-3 events.
- Model or prompt version changes begin a new decision epoch; historical
  decisions remain immutable evidence but cannot silently authorize the new
  epoch.

## Automatic learned coverage

Automatic promotion is deliberately declarative. The model cannot write code,
regular expressions, SQL, or parser configuration.

An exact event code may be promoted only when all of these are true:

- every contributing event has effective syslog severity 0 through 3
- the event code is nonempty and satisfies the existing envelope grammar
- the current immutable model/prompt/schema epoch produced three positive
  decisions with confidence at least 70
- the decisions came from three separate batches spanning at least 30 minutes
- the decisions agree on incident worthiness and allow-listed category
- at least three source occurrences exist
- every template observed for that event code in the promotion window has a
  positive decision and none has a contradictory valid decision
- no enabled suppression rule matches
- packet, result, membership, and provenance hashes all validate

Promotion appends an exact-code rule limited to severity 0-3 and the fixed
generic `event_signature` classification/lifecycle. The rule records the three
decision IDs and their model, prompt, schema, and signature hashes. It becomes
active only in a committed transaction after a complete dry-run match report.

Severity 4 and 5 decisions never contribute to automatic promotion. A code with
mixed severity may promote only its severity 0-3 occurrences; higher-severity
occurrences continue through the AI side channel unless explicit static parser
coverage is later implemented.

Learned rules are reversible but not erased. Revocation appends a new state
record, immediately returns future matches to side-channel review, and preserves
all prior incidents, decisions, and provenance. Specialized source-code parsers
remain the preferred final coverage for events needing module, interface,
sensor, peer, resource, or explicit recovery extraction.

## Managed scheduling and resource control

The existing five-minute managed reasoning service remains the only scheduled
model boundary. Its single-inference budget chooses one job per cycle:

Existing incident-reasoning backlog has first priority. When none is pending,
one triage call may decide up to 24 signatures. If triage performs no model
call because it is idle or inside retry backoff, the ordinary builder/caller
may use the cycle. Calls remain serialized under the managed owner,
loopback-only endpoint, three-minute service timeout, one-CPU quota, 1-GiB
memory limit, and bounded response size.

If no signature is new or materially changed, no triage batch is created. If
Gemma is unavailable, the attempt is recorded and the batch waits; no dashboard
incident is emitted. Fetch, ingest, canonical correlation, lifecycle export,
and raw logging continue independently.

## Dashboard compatibility

No dashboard layout or query change is required. The existing enhanced
dashboard selects all non-interface incidents from
`observability.incident_updates`, prefers any separately stored ordinary AI
assessment, falls back to the lifecycle detail, and derives Active versus
Resolved solely from lifecycle state. The side-channel summary is that
lifecycle fallback, so its incident inherits:

- existing active and resolved searches and severity filtering
- the existing color and state presentation
- existing occurrence and age columns
- the existing one-click compact Explore drilldown
- both the main and isolated NOC organization copies

The entity name contains the real event code, enabling the current drilldown to
match the originating log body. No `AI side channel`, `unclassified`, or learned
coverage label is added to operator-visible event categories.

## Failure and rollback behavior

- Selector or batch failure: cursor does not advance; no inference or incident.
- Model unavailable/invalid: immutable failed attempt; batch remains pending.
- Decision application failure: complete transaction rollback; retry from the
  same validated decision.
- Incident/outbox failure: existing independent schedules retry from durable
  state; no source event or decision is lost.
- Promotion validation failure: no rule becomes active; positive incidents
  already created from valid decisions remain ordinary incident truth.
- Disable/rollback: disable side-channel admission and learned-rule matching,
  retain all additive tables and existing incidents, and continue the original
  deterministic and reasoning paths.

The production migration requires an online SQLite backup, exact predecessor
hashes, additive-schema rehearsal on a current protected copy, and a rollback
that restores executable/configuration bytes while preserving new append-only
evidence. It must never delete learned decisions or incidents to make rollback
appear clean.

## Validation and rollout gates

Implementation must pass these gates in order:

1. Repository unit tests for severity admission, notice novelty/repetition,
   template normalization, signature stability, batching, exact output
   validation, retry, decision caching, and promotion criteria.
2. Incident tests proving same-window visibility, per-device identity,
   occurrence increments, timed recovery/resolution, relapse, replay safety,
   and no interface-flap misclassification.
3. Negative tests proving no automatic severity 4/5 promotion, no model-created
   executable rule, no partial batch application, no fail-open incident, and no
   suppressed-event admission.
4. Result/outbox/gate tests proving triage summaries are projected into the
   existing lifecycle title/body/category fields and enter `incident_updates`
   without dashboard query changes. They do not create a second assessment or
   duplicate `ai_updates` record.
5. Current-production-copy replay over at least 24 hours, with exact row-to-
   aggregate accounting, bounded packet sizes, no event duplication, and
   reviewed model decisions for the known coverage backlog.
6. Live shadow mode with batch construction and real local inference enabled,
   but incident application and learned-rule activation disabled.
7. Protected incident-bridge activation after a fresh backup, followed by
   natural-cadence verification in both Grafana organizations.
8. Separate learned-coverage activation only after three real consistent
   production decisions satisfy the exact promotion gate.

The design-only publication changed no production state. The later explicitly
authorized implementation completed gates 1–7. Gate 8 remains automatic and
data-driven: no learned rule is active until real production decisions satisfy
the immutable promotion criteria.
