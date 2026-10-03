# Projects, assets, variants and run records

Load for organizing media work, switching projects, reproducibility, batches or jobs that continue across turns.

## Project identity

Use the official **`project/1`** structure: `comfy.yaml` plus `assets`, `fragments`, `blueprints`, `outputs` and `.comfy`. The companion's visual documents belong under `blueprints/workflows`. Inspect existing structure before creating a project; do not initialize inside an ancestor governed by another project.

Pass an explicit `project_root` to every companion project operation. Official MCP operations are anchored to their process/CLI context; pass absolute workflow/input/output paths when crossing that boundary. Switching project operations must not change the global default workspace, environment, user profile or another project's state.

A project may contain several workflows and media revisions. Choose names that explain intent and a revision/run identifier. Keep files traceable without encoding a person's account, hardware or machine path in reusable recipes.

## Inputs and source preservation

Keep source images, videos, masks, recordings and approved references in project assets or link them through an explicit, permitted mapping. Preserve original files and inspect them before use. Copy/adapt only the assets the task needs; do not scan unrelated personal folders.

Use `project_assets` to list/stage project inputs. Keep the returned destination name, subfolder and type. ComfyUI may rename an input to avoid a collision; connect the renamed asset, not the guessed basename. Do not overwrite a foreign input to satisfy a graph.

The companion stages uploads in the ComfyUI input root with a project-scoped filename derived from the project namespace, asset hash and basename. The project's local asset folders stay unchanged. Use the confirmed returned mapping rather than constructing that name yourself. This avoids requiring a loader's frontend selector to enumerate project subfolders.

Check the actual loader schema after upload. A backend may read a subfolder path and display its thumbnail while the frontend still reports **Missing Inputs** because that value is absent from its selector choices. This behavior is verified for `LoadImage` in ComfyUI 0.38; other versions and custom loaders can differ. A readable file or preview alone does not prove selector compatibility. For newly uploaded inputs, follow the [Desktop refresh and reopen route](WORKFLOWS.md#desktop-handoff) and verify the reopened revision uses the confirmed input.

Retain provenance when it matters: user-supplied source, public template URL/revision, model file/terms and generated predecessor run. Do not redistribute private inputs, licensed model files or credentials in a workflow package.

## Revisions and variants

Maintain a visual editing source and preserve it when creating parameter or structure variants. Each variant should have a clearly defined change, seed, workflow revision and output destination. Compare one changed dimension at a time for causal decisions.

Reusing a seed supports controlled comparison; it is not a complete reproducibility guarantee. Model revisions, encoder/VAE, sampler/scheduler, dimensions, inputs, node code, dtype/quantization, cache and execution environment can change the result. Record the relevant differences rather than promising bitwise identity on another system.

For batches, distinguish image batch size inside one graph, a list of items, a seed sweep and separate queued jobs. Confirm the requested output count and resource cost. The CLI's variant lists are zipped; construct combinations explicitly when the user wants a Cartesian grid.

Submit sequentially by default for a shared local instance, unless the requested batch and installed workflow support a different safe schedule. Do not submit speculative variants while another task owns the resource window.

## Run ownership

On submission, capture project, workflow revision/hash, prompt/job identifier, intended variant, input mappings, selected parameters and observation time. That record allows reconciling a wait timeout or returning to a paused task without duplication.

`record_run` queries the actual existing execution and links returned files to the project. It does not accept an agent's assertion of PASS as a substitute for history/output evidence and does not submit a run. A record can contain PENDING, failure or cache information as well as success.

Do not infer ownership from a similar output prefix alone. Keep the identifier returned by the owned submission. If a queue item belongs to someone else, preserve it and explain the effect on scheduling. Cancellation, stopping the server and deleting outputs are distinct requested operations.

## Results and exports

Keep actual generated outputs separate from delivery conversions or selected finals when the distinction is useful. Preserve native dimensions/timing and record export changes such as resize, crop, interpolation, audio mix or lossy conversion.

Collect results into a new per-run output directory. Inspect files for existence, decoded media type, relevant technical properties and content. Hashes establish file identity; they do not assess artistic quality.

A small deliverable normally needs the result and workflow. For a reproducible project, also retain input mapping, prompt/seed, relevant model selections, execution history and scoped review. Use the [run review template](../assets/run-review.template.md) without forcing it into every response.

## Pause, resume and cleanup

A pause prevents new submissions and other future effects. Observe an already running job only when the user's instruction allows it; preserve its identifiers and current evidence. On resume, reconcile current job/history/files before deciding what remains.

Do not delete an intermediate because it looks old or temporary. The plugin may remove only owned resources within an authorized cleanup. Preserve source assets, existing project history, ComfyUI models, node environments and other users' jobs. Deleting a stored workflow requires the same profile/hash/backup discipline as replacement.
