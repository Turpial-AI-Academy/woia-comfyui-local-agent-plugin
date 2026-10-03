# Runtime dependency notices

The plugin's original launcher, companion and instructions are MIT licensed.
The following unmodified external programs retain their own licenses. They are
acquired only during explicit runtime preparation; their source code and binary
packages are not vendored into the plugin ZIP.

| Program | Exact version | License | Source |
| --- | --- | --- | --- |
| Comfy MCP | 0.10.0 | AGPL-3.0-or-later OR a separate commercial license | [Official source tag](https://github.com/Comfy-Org/comfy-mcp/tree/v0.10.0), [PyPI artifact](https://pypi.org/project/comfy-mcp/0.10.0/) |
| Comfy CLI | 1.22.0 | GPL-3.0-only | [Official source tag](https://github.com/Comfy-Org/comfy-cli/tree/v1.22.0), [PyPI artifact](https://pypi.org/project/comfy-cli/1.22.0/) |
| MCP Python SDK | 2.0.0 | MIT | [Official source](https://github.com/modelcontextprotocol/python-sdk), [PyPI artifact](https://pypi.org/project/mcp/2.0.0/) |

Use the free open-source license option for the MCP. This plugin does not
purchase or accept a commercial license. Review the full terms shipped in each
installed distribution's `licenses` directory before redistribution or hosting.
Comfy MCP's upstream NOTICE identifies Comfy Org and explains that its CLI
dependency runs as a separate process. This plugin also starts the official MCP
as a separate, unmodified Python module process.

`uv.lock` records every selected transitive distribution's version, artifact URL
and SHA-256. Those dependencies retain their own licenses; the installed wheel
metadata and license files are authoritative. Locking packages does not relicense
them as MIT. The CLI retains its own per-user state; this plugin does not claim
to isolate all upstream configuration in `PLUGIN_DATA`.

No model weights are bundled. Model and generated-asset rights must be checked
separately for the user's intended use.
