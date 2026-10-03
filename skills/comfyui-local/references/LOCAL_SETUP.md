# Local setup orientation

Load when the user asks about setup or a required connection/runtime is absent. The main capability is using an existing local ComfyUI. This guide identifies the next prerequisite; it does not authorize installation, updates, downloads or server lifecycle effects automatically.

## Requirements

- An existing local ComfyUI workspace and a reachable HTTP loopback endpoint with an explicit port for tool operations.
- A compatible existing Python interpreter plus uv for the plugin's explicit runtime preparation.
- The plugin's prepared isolated environment, private configuration under `PLUGIN_DATA`, and both stdio MCP servers loaded by the client.
- Compatible installed nodes and models for the requested modality.

The portable package carries code and dependency locks under `plugin-resources`. Its environment is separate from ComfyUI's Python. ComfyUI and its models are not bundled. The maintenance repository's Node, pnpm, mise and Docker are not consumer requirements.

## Prepare only when requested

Follow the packaged [runtime preparation tool](../../../plugin-resources/runtime/prepare_runtime.py). Select the existing interpreter, workspace, loopback endpoint and intended profile. Preparation is an explicit dependency-install boundary; startup later validates the prepared environment and fails clearly without downloading or repairing it.

Use an explicit `http://<loopback-host>:<port>` endpoint, such as `http://127.0.0.1:8188` when that is the existing server. This version rejects HTTPS and URLs without a port: the pinned CLI cannot retain those choices consistently. Do not silently substitute another endpoint to clear a rejection.

The packaged tool accepts this invocation; each angle-bracket value is a discovered local value, not a literal default path:

~~~text
<existing-python> <plugin-root>/plugin-resources/runtime/prepare_runtime.py --data-dir <plugin-data> --python <existing-python> --workspace <existing-ComfyUI-core> --server-url <loopback-url>
~~~

Quote paths when the shell requires it. `--data-dir` may be omitted when the client has set `PLUGIN_DATA`. `--user-id <ComfyUI-user-id>` is optional for an explicit profile; omitting it selects the default only where that profile is valid. Python must already exist and be version 3.10 through 3.14. Run `--help` without other arguments to inspect this contract without preparing anything.

Do not repurpose ComfyUI's Python environment, modify persistent PATH or profiles, change the CLI's global default workspace, rewrite ComfyUI configuration, or change model directories to connect this plugin. Configuration values are private runtime data, not portable defaults.

The official CLI keeps some state in its own per-user location, including configuration/job records. The plugin does not claim that all upstream state is isolated in `PLUGIN_DATA`.

## Orient the user by the failure

| Missing prerequisite | Explain | Next step |
|---|---|---|
| ComfyUI not installed | The plugin operates an existing application | Point to official local installation guidance; install only under a setup request |
| Server stopped | The project files are available, inference is not | Use its known start procedure only when requested |
| MCP runtime absent | The plugin is installed but executable dependencies are not prepared | Prepare through the packaged tool explicitly |
| Tools not loaded | Configuration exists but the client runtime has not loaded it | Reload/restart the client runtime; confirm actual tool inventory |
| Required node/model absent | This specific workflow cannot run now | Name the missing compatible component and offer a usable local alternative |
| Profile unresolved | Saving could target the wrong user | Resolve the intended profile before writes |

If the user requests acquisition/configuration, review current primary source, license, compatibility, storage requirements, exact artifact and recovery before effects. A download link in a workflow note is not sufficient provenance or authorization. Avoid purchasing services or enabling hosted nodes for a local task.

Starting/stopping and installing/updating are separate from creating a visual workflow. Preserve an occupied model, existing environments and another task's jobs. A stopped server is not a reason to launch a second model server for convenience.

## Primary guidance

Use the [official ComfyUI documentation](https://docs.comfy.org/) for local installation and version-matched troubleshooting. Use [runtime sources](SOURCES.md) for the pinned MCP/CLI contracts. Do not send the user through multiple competing installation paths for a simple missing prerequisite.
