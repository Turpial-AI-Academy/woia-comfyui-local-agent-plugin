# Audio and 3D using installed local capabilities

Load only for requested audio/spatial output or when a video requires sound. Neither modality is guaranteed by the plugin: first discover the available models, node types, input shapes and output exporters.

## Audio route

Determine whether the task is sound effects, ambience, music, speech, voice transformation, transcription or audio editing. These are different model capabilities. Discover local conditioning and decode/export nodes; do not route to a hosted speech/music API when a local component is absent.

For generation, define duration, audible events, start/end behavior and required channels/sample rate. For speech, identify exact text, language, pronunciation and permitted voice reference. A voice cloning capability does not imply permission to use a supplied person's voice; apply the user's actual task/rights context.

For editing, inspect the source audio before cutting, denoising, resampling or mixing. Match sample rate and channel layout deliberately. Avoid assuming mono and stereo are interchangeable. Time stretch and sample-rate conversion are different operations and must preserve the intended playback length.

For joint audiovisual models, verify that generated audio is decoded, trimmed and reaches the final container. For separate sound generation, align the track to the delivered video timing and maintain a clean source track for revisions.

Select lossless working audio when further processing is planned, then a compatible delivery format. Decode the resulting file; inspect duration, sample rate, channels, clipping, silence and timing. Listen when acoustic/semantic quality matters. Waveform/RMS checks alone cannot establish correct speech, intelligibility, music quality or synchronization with a visible action.

## Audio guidance for users

Ask for the sound's role instead of node settings: "quiet room ambience", "a short impact as the door closes", "spoken narration", or "no sound". If the graph supports sound descriptions, keep them separate from visual motion instructions where its prompt interface requires that. Do not promise exact words or lip sync from a model intended only for ambience.

Deliver the audible output or video track plus its workflow and any source/reference mapping. Mark listening NOT_RUN when the client cannot play it; do not conceal that behind technical PASS.

## 3D route

Identify the requested representation: mesh, textured mesh, point cloud, depth/normal map, radiance field, splats or a rendered turntable. An image that depicts a 3D object is not a 3D asset. Choose only representations the discovered local graph can produce.

For image-to-3D, inspect silhouette, occlusions, background, perspective and visible sides. For multiple-view routes, preserve view ordering and camera conventions; images with inconsistent identity or lighting can degrade reconstruction. For text-to-3D, establish object shape, material and intended viewing/usage constraints.

Read the nodes' coordinate system, scale/units, orientation, geometry and material/export assumptions. Keep geometry reconstruction, texture generation, rendering and delivery export as explicit stages where available. Do not add unavailable remeshing, rigging, UV, PBR or animation promises.

Choose an export compatible with the user's intended application, using the installed exporter. Preserve references and native intermediates when a conversion loses information. A renamed extension does not convert a representation.

## 3D validation

Open/parse the actual file with a compatible local viewer or library when available. Check expected geometry/material files, dimensions/bounds, normals/orientation, textures and representation-specific properties. Inspect multiple views or a turntable for incomplete surfaces, floating pieces, texture seams and distortions.

Topology/manifoldness, printability, rigging readiness, real-world scale and physical correctness require their own checks when the task needs them. A preview render or successful export alone does not establish those properties. Record unavailable checks as NOT_RUN.

## Related non-media tasks

ComfyUI can expose custom model and data operations beyond images, video, audio or 3D. When the user requests one, discover its schemas and use the same project/local execution/ownership/evidence rules. Do not claim an undiscovered node class or install a pack just because a guide mentions the capability.
