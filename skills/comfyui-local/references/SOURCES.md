# Primary sources and version boundaries

Load for unfamiliar node behavior, licensing or a version-sensitive command. Prefer the installed tool schemas and source matching the connected version. Upstream live documentation can describe newer or hosted functionality; that does not add a local capability.

| Source | Use |
|---|---|
| [ComfyUI official documentation](https://docs.comfy.org/) | Concepts, interface, local examples, tutorials and troubleshooting |
| [Documentation index](https://docs.comfy.org/llms.txt) | Find the exact current primary page for a node, modality or interface feature |
| [Official MCP v0.10.0](https://github.com/Comfy-Org/comfy-mcp/tree/v0.10.0) | The pinned official server, tool definitions and upstream notices |
| [Official MCP source](https://github.com/Comfy-Org/comfy-mcp/blob/v0.10.0/src/comfy_mcp/server.py) | Exact tools, argument semantics, asynchronous waits and output handling |
| [Official CLI v1.22.0](https://github.com/Comfy-Org/comfy-cli/tree/v1.22.0) | The pinned command/schema engine and project/workflow behavior |
| [CLI workflow implementation](https://github.com/Comfy-Org/comfy-cli/blob/v1.22.0/comfy_cli/command/workflow.py) | Visual workflow storage, slots and serialization behavior |
| [ComfyUI source](https://github.com/Comfy-Org/ComfyUI) | Server routes and native nodes; select the installed revision before relying on code |
| [MCP Python SDK v2.0.0](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.0.0) | Runtime protocol/server compatibility |
| [Agent Plugins specification](https://agent-plugins.org/specification) | Portable package/runtime separation |
| [Agent Skills specification](https://agentskills.io/specification) | Skill structure and progressive loading |

The plugin's code and instructions are MIT. External runtime packages retain their own terms: official MCP **AGPL-3.0-or-later or its commercial alternative**, CLI **GPL-3.0-only**, and MCP SDK **MIT**. The free upstream license route is used without purchasing commercial rights. Preserve the packaged third-party notices and lockfile provenance.

Model and asset licenses are separate. A template may combine components under different terms. Verify current model/asset terms when public, commercial or redistribution use depends on them; neither this plugin nor the existence of a local output confers those rights.

Do not copy an entire upstream manual into the skill. Link and consult the focused primary page when it improves a concrete decision. Where source access is unavailable, state the limit and use verified installed behavior rather than inventing an undocumented contract.
