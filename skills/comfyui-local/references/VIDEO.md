# Video: motion, continuity and export

Load for animation, generated video, video edits, image-to-video or a timed audiovisual output. Discover the model's supported size, frame-grid, duration, conditioning and audio behavior before graph construction.

## Select the route

- **Text-to-video:** define one coherent shot from the brief and generate through a supported local video pipeline.
- **Image-to-video:** inspect the starting image, fit it to the model's input geometry, connect the confirmed input mapping, and describe motion/camera/sound. Preserve an untouched original.
- **Video-to-video:** inspect source timing and frames; identify whether the installed graph offers editing, latent resampling, per-frame transforms or model-specific temporal conditioning. These routes have different continuity guarantees.
- **First/last frame, multiple references or continuation:** use only controls discovered in the local node schema. Maintain reference roles, temporal boundaries and model-specific frame-length constraints.
- **Motion/style adapters:** confirm model family, supported placement and temporal settings. An image LoRA or adapter is not automatically a video adapter.

For unsupported routes, report the missing local capability. Do not convert an edit request into an unrelated new video without explaining the changed behavior.

## Plan the shot

Separate subject action, camera movement, environmental movement and sound. Specify which elements should remain stable. For image-to-video, start with modest motion when fidelity is the priority; a strong action can conflict with preserving the supplied pose.

Use a [shot plan](../assets/shot-plan.template.md) when multiple clips or synchronized events matter. Keep character, object, environment, palette and lighting anchors consistent across shots. Seeds alone do not guarantee cross-shot continuity; use supported references and review the generated clips.

## Timing and native dimensions

Read the model's frame-length rule instead of assuming `seconds * FPS` is accepted. Generate an allowed native length; if needed, trim to the requested delivery duration using available deterministic nodes or tools. Record both generated and delivered lengths.

Check frame rate as a rational value, frame count and playback time. Frame interpolation changes frame count/cadence; simply changing FPS can change duration. Video speed changes must retime audio too. Do not label a frame-rate conversion as newly generated motion detail.

Fit/crop the input deliberately. Avoid stretching a subject to fill a new aspect ratio. Distinguish native generation resolution from resize, crop, super-resolution or delivery resolution; name upscaled exports accurately.

## Video and audio data flow

Verify the graph's frame-batch/video types, decoding route and export interface. Some models generate an audiovisual latent; others generate frames only. An audio prompt or an audio VAE node does not prove an audible track reaches the exported file.

When attaching sound, establish whether it is joint generation, separate local generation, a supplied recording or an existing licensed track. Preserve sample rate, channel layout, start time, trim and end time. Avoid repeated lossy encode/decode stages when raw frames and audio can be assembled once.

Sound requirements may include ambience, effects, speech, music, silence or synchronization. Inspect and listen to the actual output when available. Track existence/RMS is technical evidence only; it does not prove intelligibility, musical quality, correct words or synchronization with a visible event.

## Export

Select a format appropriate to the use and available local exporter. Check container/codec compatibility, color space, pixel format, bit depth, codec settings, audio codec and whether the result is playable by the intended viewer. Do not infer codec details from the extension.

Use a lossless or high-quality intermediate when further editing is planned, then a separate delivery export. Keep unique filenames. Do not apply universal CRF, bitrate, FPS or dimensions to every installation; choose them from the request, graph and compatibility requirements.

For exact duration, verify decoded frames and audio timestamp range, including any codec priming/trailing samples handled by the decoder. Report measured mismatch and its significance rather than rounding away an error.

## Execution and review

Video runs can be long and consume substantial memory. Estimate from relevant actual runs where available and keep one owned run at a time unless an established compatible batch is intended. A tool wait returning PENDING is not an execution timeout; observe the same job.

Review start, middle, end and task-relevant intervals, then full playback when quality acceptance requires it. Check visible motion, subject stability, flicker, deformation, scene consistency, camera behavior, abrupt cuts, reference fidelity and audio/video alignment. A contact sheet is sampled visual review, not full-video review.

For long work, preserve progress and identifiers. Before retrying a failed run, confirm it reached a terminal failure and classify the error. Do not resubmit because a polling connection dropped.

Deliver the clip, its editable graph, source image/video mapping, prompt, seed, native and delivery timing/resolution, and scoped quality observations. Any unperformed listening or full playback remains NOT_RUN.
