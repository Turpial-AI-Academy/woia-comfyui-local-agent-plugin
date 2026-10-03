# Creative direction and prompts

Load for ideation, an unclear visual goal, prompt development or coordinated image/video style. The goal is a controllable brief, not a form the user must complete.

## Translate the request

Find the subject, action, setting, medium, mood, intended use, aspect ratio and constraints that affect the output. For edits, separate the part that must change from the elements that should remain. For video, identify one main action, camera behavior, duration and desired sound. For 3D, identify object form, viewpoint, material and target representation.

Inspect supplied references before proposing decisions. Note identity, composition, pose, lighting, texture, brand constraints and which reference controls which property. A color reference and an identity reference serve different purposes; record their roles rather than treating every input as interchangeable.

Offer distinct concepts when the user asks for ideas: vary a meaningful dimension such as composition, visual treatment or narrative beat. Give each idea a short outcome description and explain why the connected local workflow can realize it. Do not fill a response with sampler details.

If the user asks for a finished asset and context is sufficient, select a reversible creative direction and execute it. When the unresolved choice materially changes usefulness, ask a focused preference question before expensive runs.

## Build a prompt suited to the model

Use the selected model's documented prompt style. A useful structure is:

> Subject and action; environment; framing and composition; lighting and color; materials/style; constraints.

Put the main subject and requested action early. Use concrete relations: "the glass stands left of the plate", "the camera moves slowly toward the doorway", or "keep the label's printed text unchanged". Avoid contradictory lighting, simultaneous incompatible camera moves, or excessive stylistic modifiers.

Use a negative prompt only if the installed workflow has supported negative conditioning. Do not create universal lists of "bad quality" tokens or claim that they apply equally to every model. Prompt weighting syntax, token limits, multilingual handling and image-reference instructions depend on the text encoder/model; verify unfamiliar syntax.

For a masked edit, describe the desired replacement and nearby context while preserving the unmasked subject. For an instruction editing model, specify the change and preservation explicitly. For image-to-video, prioritize what moves, what stays stable and how the camera behaves; do not redundantly redescribe the entire visible image.

## Composition, style and consistency

- Choose framing that fits the use: space for a title, a clean product silhouette, a full body pose or a close detail. Reserve typography and logos for an exact overlay/edit route when generation cannot reliably satisfy exact text.
- Keep a concise style anchor across variants: medium, palette, lighting, lens/framing if supported, and reference role. Change one creative dimension at a time when comparison matters.
- Distinguish references, structural conditioning and text. A fixed seed does not guarantee subject identity across different prompts, resolutions, models or workflows.
- For a recurring subject, reuse approved reference assets and compatible identity conditioning when available. Review actual consistency rather than promising it from a recipe.
- Explain native generation size separately from final crop, upscale or export size. A larger file does not prove newly generated detail.

## Video and sound direction

Keep short shots physically coherent. Specify a single dominant action and clear temporal progression. Separate subject motion, environmental motion and camera motion; acknowledge that exact frame-by-frame choreography may exceed the installed model's control.

Describe sound independently: ambience, effects, speech or music, its timing and whether it is generated jointly or supplied as a separate track. Silence is a valid explicit choice. Do not promise lip sync, exact speech, a particular voice or music generation unless the discovered local graph supports it.

For multiple shots, use the [shot plan](../assets/shot-plan.template.md) and establish a shared continuity reference. Generate/validate individual shots before assembly, with transitions and audio handles where the available tools support them.

## Iteration

Inspect the result and relate defects to the brief. Refine the prompt for semantic mismatches; use a mask or edit route for local defects; change reference/conditioning for structure; adjust workflow controls for sampling/artifacts. Avoid random parameter churn.

Reuse a seed for a controlled comparison and change it when exploring a new composition. Preserve the strongest accepted revision. Give the user the result plus an understandable reason for the next edit, not an unexplained list of settings.
