# Images: generation, editing and composition

Load for images and still-frame assets. All recipes are capability patterns; obtain concrete node names, sockets, model choices and parameter ranges from the connected server. Do not turn these patterns into assumed runnable graphs.

## Choose the route

| Intent | Preferred local pattern | Key check |
|---|---|---|
| New image from text | Compatible loaders -> text conditioning -> latent/noise -> sampling -> decode -> save | All model components and resolution agree |
| Variation from an image | Load/resize -> encode or image conditioning -> sampling/edit -> decode -> save | The graph actually consumes the reference |
| Instruction edit | Reference input(s) + model-specific edit conditioning -> edit sampling -> decode | Supported number/roles of references |
| Replace a region | Image + mask -> supported inpaint conditioning -> sample -> composite/save | Mask semantics and preserved outside region |
| Extend the frame | Pad image/canvas + new-region mask -> inpaint -> crop/save | Existing image aligns with padded coordinates |
| Preserve pose/depth/edges | Reference preprocessing -> compatible structural conditioning | Preprocessor and conditioning family match |
| Preserve subject/style | Supported reference adapter or edit/reference model | Identity/style roles and encoder compatibility |
| Enlarge/refine | Resize or installed upscale model; optional tiled refinement | Rescaling and generative detail are reported separately |
| Composite/retouch | Crop, transform, masks/alpha -> blend/composite -> save | Color/alpha and output dimensions are preserved |

## Construct or adapt a graph

Start with a working local image recipe and locate prompt, references, model selectors, seed, size, sampling controls and output nodes. Keep model defaults when there is no reason to change them. Steps, guidance/CFG, sampler, scheduler and denoise are model-specific; avoid a universal "best" preset.

For image-to-image, verify how the model receives the image: latent initialization, reference conditioning or explicit edit inputs. Denoise/strength only has the meaning defined by that path. A visually connected but bypassed input is not an actual reference.

Check batch dimensions and data flow. Some nodes process image batches, some lists, and some only one element. Confirm that saving covers every intended output and that filenames cannot overwrite existing assets.

## Masks, inpainting and outpainting

Inspect the source and mask visually. Match dimensions, coordinate system, crop, orientation and alpha channel. Verify whether the node derives a mask from alpha, inverts it, or expects white as the editable area. Mask conventions vary; do not infer them from how a PNG looks in a viewer.

Feather/dilate only as needed for a natural boundary and retain an unmodified source. Ensure the chosen inpaint route can supply known context, the masked region and the intended latent/noise mask. If the requested unmasked pixels must be exactly retained, explicitly composite the generated region back into the original and verify outside-mask differences.

For outpainting, establish the target aspect ratio, anchor position and padding before mask creation. Preserve coordinates when transferring a mask from the original image to the larger canvas. Review the seam, perspective and lighting across the new region.

The Desktop mask editor is a user-friendly way to supply a region; the MCP must use the actual resulting mask file/mapping. Do not claim to have painted a mask merely by describing one.

## Conditioning, LoRA and references

Apply compatible LoRA weights to the supported model/text-encoder path and record filename/provenance and strength. Read actual accepted ranges; a strength value is not universal across adapters. Preserve a clean base revision for comparison.

For ControlNet-like routes, discover the installed structural model and preprocessing method. Check expected dimensions, control strength and start/end timing. Show the preprocessed control image when it helps explain a failure.

Reference adapters may require their own vision encoder and projection model. Do not connect arbitrary image embeddings across families. Multiple references need clear ordering/roles and compatible count/size constraints.

## Upscale, restoration and exact assets

Decide whether the goal is display enlargement, recovered detail or creative refinement. Lanczos/bicubic resizing, neural super-resolution and diffusion refinement have different effects. Tiling can reduce peak memory but can introduce seams or inconsistent detail; verify overlap and decode behavior for the actual nodes.

For exact text, logos, UI assets, transparent backgrounds or precise geometry, combine generation with an available deterministic editing/compositing route when appropriate. Confirm alpha in the file itself; an apparent checkerboard may be baked pixels. Do not export JPEG when transparency is required.

Inspect color space, bit depth and format supported by the save node. Preserve high-value source assets; make delivery conversions as separate revisions rather than destructive replacements.

## Review and delivery

Decode each delivered image. Check dimensions, color/alpha mode, subject/action, composition, reference fidelity, masked boundaries, structural coherence, obvious defects and requested text. Inspect zoomed areas when local detail is the task. Do not mark exact text or identity preservation PASS from a thumbnail alone.

Deliver the media and editable workflow revision with prompt, seed, input mapping and meaningful generation/export parameters. A previous successful image can establish compatibility; a new image request still needs a new execution unless reuse is what the user asked for.
