# Quality, performance and troubleshooting

Load for result review, failed jobs, missing outputs, resource pressure or performance changes. Start with the affected job/workflow; do not widen into a machine overhaul.

## Evidence scopes

| Scope | What establishes it | What it does not establish |
|---|---|---|
| Connection | A read-only response from the configured endpoint | Loaded models or generation |
| Tools loaded | Actual MCP handshake and tool inventory | A runnable graph |
| Graph preflight | Schema validation and inspected inputs | Native execution or media quality |
| Native run | Owned job history, real processing and produced outputs | New sampling if that stage was cached |
| File integrity | Media decode, format/timing checks and file identity | Artistic/semantic correctness |
| Visual/audio review | Observed frames, playback or listening against the brief | Unobserved intervals or human acceptance |

Use PASS/FAIL/PENDING/NOT_RUN with the named scope. For sampled review, state sampling explicitly. A JSON-valid workflow or an old image shown in the UI cannot close a new-generation request.

## Review against the brief

Inspect the actual deliverable at its intended scale. Check subject, action, composition, style, references and constraints; review masks, exact text, alpha, anatomy/geometry and local detail as relevant. For video, inspect motion/continuity and timing; for audio, listen and verify synchronization; for 3D, inspect multiple views and the requested representation.

Explain material defects in ordinary language. Use a targeted correction: prompt/conditioning for semantic errors, masks/composition for local changes, temporal/reference controls for video coherence, or export settings for delivery problems. Preserve useful accepted outputs and avoid broad parameter churn.

## Diagnose by stage

| Symptom | First evidence | Bounded action |
|---|---|---|
| Tools unavailable | Loaded server inventory and runtime error | Explain missing prepared runtime; no silent install |
| Server unreachable | `local_status` and configured endpoint | Verify intended instance; lifecycle only if requested |
| Unknown node/model | Exact node schema/model choices and workflow dependencies | Adapt to a compatible installed recipe or report missing dependency |
| Validation fails | Required inputs, enums, socket types and dynamic fields | Repair the affected graph revision; retain source |
| Submission uncertain | Queue/history and known identifiers | Reconcile before any retry |
| Job fails | Owned history/error, failing node and relevant logs | Fix the specific cause before rerunning |
| Memory failure | Actual error and scoped RAM/VRAM observations | Propose a measured lower-cost route or idle resource step |
| No output after success | Connected save nodes and history output mapping | Check reachable output path and cache; do not invent a file |
| Wrong input/result | Returned upload mapping and actual execution path | Correct the mapping/branch and rerun affected work |
| Desktop reports Missing Inputs despite a thumbnail | Loader's live selector choices, confirmed upload mapping and frontend node definitions | Check selector-compatible filename; refresh node definitions, refresh Workflows and reopen the new revision |
| Desktop lacks a flow | Server/profile, storage readback and document format | Open correct saved revision or import the visual JSON |
| File is unreadable/wrong length | Decoder, codec/container and timestamps | Repair the export stage; retain native source |

Do not use automatic package upgrades, reinstalling ComfyUI, drivers, execution-policy changes or cloud inference as routine repairs. Unknown custom node behavior may require its matching primary documentation and explicit setup work.

For missing-media triage, distinguish file existence, backend readability and frontend selector membership. In ComfyUI 0.38, `LoadImage` can read subfolder inputs that are absent from its root-file selector enumeration. The companion stages uploads at the input root with owned names and retains the actual mapping; do not move the local project assets or overwrite another input to work around the warning. Inspect the connected version's schema and follow the [targeted Desktop refresh route](WORKFLOWS.md#desktop-handoff). Reopening without **Missing Inputs** is UI readiness evidence; it is not a new native generation.

## Resource and performance work

Measure a baseline from actual runs: workflow/model revision, inputs, seed, dimensions/frame count, steps, time, cache state and observed RAM/VRAM. Compare the same workload under comparable conditions. Loading/cold start, cached runs and native sampling are different timings.

Estimate runtime from a relevant completed case, not a GPU name alone. Peak monitoring is observed within the sampling window; record gaps and do not claim an unobserved maximum. Queue wait time and execution time should be distinguished when available.

Change one factor for a useful comparison: supported dtype/quantization, resolution/length, batch size, tiling, offload/cache policy, or model-specific quality settings. Explain quality and memory tradeoffs. Do not silently lower requested quality, duration or output count to manufacture success.

An installed memory-release tool is not permission to unload another task's models. Check queue/ownership before requesting idle unload/cache changes. Do not change system paging, global environment, launch flags or other services under an ordinary media-generation request.

## Cache and reproducibility

Inspect execution/cache events when proving new sampling. Identical graphs may reuse cached stages. If a new result is required, use an intentional new seed or relevant changed input and confirm the affected stage actually executes. Do not disable all caching globally just to make a test look active.

Reuse durable evidence for unchanged components when it is identifiable and applicable. A changed prompt invalidates semantic result review; changed model/export/nodes invalidate their relevant runtime checks. Do not repeat expensive unaffected tests merely because a new turn begins.

## Report the remaining boundary

Record technical properties and observed quality separately. State any missing modality, unperformed playback/listening, limited visual sampling, uncertain remote/custom-node behavior or unresolved error. Never turn configuration readiness, a template's existence or a repaired graph into native PASS before it runs.
