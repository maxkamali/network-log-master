# Detection Coverage Backlog

This file records public-safe deterministic detection gaps found during normal
NOC evaluation. An entry here is not implemented behavior and does not change
the completed project sequence in `docs/CURRENT_STATE.md`.

`docs/AI_DETECTION_SIDE_CHANNEL.md` defines the implementation-ready generic
AI-review and learned-coverage design for future gaps. Specialized parsers in
this backlog remain valuable because they can extract richer entities and
authoritative recovery behavior than generic learned coverage.

The listed events are already captured and retained. They currently pass
through the normalizer as attention-eligible generic observations, but they do
not have the entity identity, adverse/recovery signal, or state required by the
GX10 incident engine. They are not suppression-rule matches.

Do not add a parser from the event-code name alone. Each implementation must
include synthetic fixtures, deterministic correlation identity, repeat
semantics, recovery behavior, replay/backfill policy, and protected production
validation.

## Pending NX-OS event coverage

| Event code | Intended incident meaning | Candidate correlation identity | Required lifecycle behavior |
| --- | --- | --- | --- |
| `TAHUSD-SLOT1-4-BUFFER_THRESHOLD_EXCEEDED` | ASIC buffer-pool pressure above the reported threshold | device, module/slot, ASIC instance, pool-group | Create an immediately visible adverse buffer-pressure incident and increment it for repeated reports. No matching clear event has yet been observed, so recovery requires an explicitly chosen quiet period or authoritative telemetry signal. |
| `STATSCLIENT-SLOT1-2-STATSCL_CRIT` | CRC errors on an internal fabric/interface path | device, module, internal interface | Create an adverse internal-link/fabric-health incident; preserve interval and cumulative error counts as evidence, and increment the same incident for subsequent intervals. Define recovery from a sustained error-free interval or authoritative clear signal. |
| `PLATFORM-2-MOD_TEMPMINALRM` | Module temperature sensor entered a minor alarm | device, module, sensor | Create an adverse module-temperature incident and correlate subsequent alarm reports to it. |
| `PLATFORM-2-MOD_TEMPOK` | Module temperature sensor recovered from its minor alarm | device, module, sensor | Act as recovery evidence for the matching temperature incident, not as an independent incident. |
| `ICAM-2-SCALE_THRESHOLD_EXCEEDED_CRIT` | A finite hardware/software scale resource reached its critical threshold | device, named feature/resource | Create an immediately visible critical capacity incident and increment repeated reports. Recovery needs a below-threshold or authoritative resource reading. |
| `ARP-2-DUP_SRCIP` | A received ARP packet conflicts with a locally owned IP address | device, interface, conflicted IP; retain observed MAC as evidence | Create an immediately visible duplicate-address incident and correlate repeats without merging unrelated interfaces or addresses. Define a conservative quiet-period recovery if the platform emits no clear event. |

## Repetition-only records

Messages such as `last message repeated N time(s)` contain no event code or
entity of their own. They currently remain generic supporting observations.
Supporting them safely requires deterministic association with the preceding
event from the same ordered source stream; they must never be attached across
devices, source files, or ambiguous ordering boundaries.
