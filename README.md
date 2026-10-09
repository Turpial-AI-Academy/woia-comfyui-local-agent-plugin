# woia-comfyui-local

Shared WOIA v0.5.6 ComfyUI Local provider for Software, Marketing and Ads.


- Primary skill: $comfyui-local
- Includes the portable MCP/runtime resources from the source plugin.
- Authoring profile: thin
- Activation is evidence-triggered; plugin presence, GPU presence or local models alone never activate it.

Generic certification/release tooling lives in woia-ecosystem.
## Maintenance

Edit only this canonical repository. Keep `plugin.json`, `package.json` and `dev.woia/manifest.json` versions aligned. From the canonical WOIA Ecosystem repository, run `mise run plugin:certify-thin --repo <absolute-plugin-repository>`, then use its release preparation/publication tasks. Install and update consumers from immutable published artifacts; keep Project personalization in overlays.
