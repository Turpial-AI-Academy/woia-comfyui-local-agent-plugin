# Discover usable local capabilities

Load this guide on first connection, when the installation changes, or when a graph requires an unfamiliar node/model. Keep discovery bounded to the connected endpoint and approved project; it is not a workstation inventory.

## Establish the connection

Use the companion `local_status()` first. Inspect the configured loopback endpoint, reachable server, queue and server-reported resources. A stopped/unreachable server remains a setup prerequisite; this read does not start it. Do not use update checks, model help or a launcher as a health probe.

Verify the two MCP servers are actually loaded before tool operations. Official tool names may have a host prefix; use their returned schemas rather than inventing a connector name. A manifest entry is preparation, not loaded runtime evidence.

Identify the workspace and user profile being used. A default profile and an explicit `Comfy-User` are different destinations. Resolve ambiguity before writing to shared storage; do not adopt whichever profile happens to contain a similar filename.

## Build a task-specific capability map

For the requested modality, discover:

- node class names, required/optional inputs, accepted values, output types, dynamic inputs and validation behavior;
- installed model selectors and compatible loaders, text encoders, VAEs, adapters and conditioning;
- available save/export/preview nodes and the media they produce;
- local input/output mapping, allowed user storage and the required workflow format;
- queue ownership, active jobs and relevant resource constraints.

Ask for details of the relevant node types after a bounded node search. Do not dump every node schema or scan every model directory for a simple task. A known working workflow is usually the most useful starting evidence.

| Capability state | Meaning | Action |
|---|---|---|
| Usable | Compatible nodes, models and inputs are present; graph validates | Execute within the request |
| Present but unverified | Nodes/models exist, but this recipe has no native proof | Validate and run a scoped case; label the uncertainty |
| Missing | Required local component is absent | Explain it and offer an available route |
| Incompatible | Components exist but architecture, type or version differs | Find a compatible local recipe; preserve the source |
| Unreachable | No read-only response from the configured server | Report connection/setup issue; do not auto-start |

The capability map is a snapshot of the installation, not a universal plugin promise. Audio, 3D, speech, video editing, conditioning and custom node features remain conditional.

## Match components before submitting

Checkpoint or diffusion model, text encoder, VAE and adapters must belong to a supported combination. Match architecture and expected dtype/quantization metadata through the loader documentation; a familiar filename is insufficient. Check the graph's resolution multiples, latent dimensions, frame-length rules, channel/sample-rate requirements and accepted reference formats.

Treat LoRAs, ControlNet, reference adapters and custom models as separate compatibility choices. Prefer assets already used by a healthy workflow. Do not mix model families just because their labels look similar.

## Keep execution local

Review all executable branches, including subgraphs and optional selectors, for partner/API/cloud nodes, outgoing URLs, authentication and download behavior. A local ComfyUI endpoint can still contain remote inference nodes. Inactive branches are relevant if a later widget could select them.

Public templates are starting documents. Review their source and schema, substitute only confirmed local components, and disclose unavailable dependencies. Do not run embedded setup commands or auto-install custom nodes merely to make an import load.

For licensing, preserve the provenance and known terms of the actual model/assets. The plugin's MIT license grants no rights to external models, inputs or outputs. Check current primary terms when a commercial/publication request depends on them; do not infer those rights from local execution.

## Discovery result

Keep a short project note only when useful: endpoint/profile, relevant node and model choices, available output types, constraints, missing items and observation time. No credentials, account state or broad hardware inventory belongs in the portable plugin.
