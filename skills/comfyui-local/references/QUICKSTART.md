# Quick start: request -> project -> media -> Desktop

Use this route for a first task. Respond in the user's language and keep instructions centered on what they need to do.

1. Ask the user for the intended result in ordinary language: for example, a product photo, an illustration, an image edit or a moving shot. Accept reference files. Infer routine choices from the request; ask only where an answer changes the result materially.
2. Inspect the connected local ComfyUI and explain what is usable now. Choose a working local workflow; do not ask the user to choose loaders, tensor types or samplers unless that is their intent.
3. Create or reuse an explicit project, map its inputs, and save a new editable workflow revision. For a video from an image, inspect the image first and treat it as the continuity reference.
4. Run the intended generation once. Keep the job identifier and provide useful progress while observing that job. Long model loading or a wait timeout is not a reason to click Run again.
5. Inspect the actual image, video, audio or 3D output. Deliver the file and state any material mismatch or unsupported part of the request.
6. Tell the user: **Open ComfyUI Desktop -> Workflows -> open the saved workflow revision**. If storage is unavailable, provide the full visual JSON to import. They can change exposed prompts and controls, select an input and press **Run** for another result.

## Controls worth explaining

| Control | Meaning for the user |
|---|---|
| Prompt | What should appear, or what should change |
| Reference/input | The image, video, mask or sound the graph actually consumes |
| Seed | A reproducible random starting point; change it to explore variants |
| Size/aspect ratio | Composition and export shape; supported sizes depend on the model |
| Duration/FPS | Playback length and frame timing, constrained by the video graph |
| Strength/denoise | How far an edit can depart from its input, when the graph exposes it |
| Steps/quality preset | A model-specific quality/time choice, not a universal quality guarantee |
| Batch/variant count | How many outputs will be queued or produced |

Explain only controls relevant to the current graph. Prefer a small set of clearly labeled exposed controls and retain the editable internals for advanced use.

## Working in Desktop

Open a workflow before editing. The canvas shows connected processing steps; select a node to change its exposed widgets, and connect compatible outputs to inputs when adapting the recipe. Use the installation's node search/library for new nodes and its node documentation for unfamiliar inputs. Preserve a known working revision before structural changes.

The template browser offers starting workflows, not proof that required local components exist. Groups organize stages; notes explain reference roles and controls. A subgraph can expose a simpler interface while retaining its internals. APP mode, partial execution and alternative node interfaces are frontend/version-dependent; use them only when present and explain what changes in the current view.

If newly uploaded media is missing from an input selector, use **Edit -> Refresh Node Definitions -> Workflows -> Refresh -> open the new saved revision**, where those actions are available. If the installed shortcut is `r`, focus the canvas before using it. Keep unsaved tabs open; do not reload the app or press F5 for this targeted refresh. The agent should check the confirmed uploaded filename and the loader's actual choices if a warning remains.

Check the queue/job card to distinguish loading, running, completed and failed work. Open actual output previews or saved files. Cache and partial execution can reuse prior results; when the user expects a new image or clip, inspect whether its processing branch actually ran.

## Everyday expectations

- A saved workflow is an editable recipe. A generated media file is the output of one execution. Keep both when reproducibility matters.
- Saving through MCP does not replace an unsaved tab or live-edit the current Desktop canvas. Open the new revision to see it.
- Desktop and the backend may have separate lifecycles. Closing a window may leave the server running. Use the installation's documented stop action only when the user requests it and the queue is safe.
- If a request cannot run locally with the installed capabilities, state the missing component and propose an available local alternative. Read [setup orientation](LOCAL_SETUP.md) for that limited guidance.
