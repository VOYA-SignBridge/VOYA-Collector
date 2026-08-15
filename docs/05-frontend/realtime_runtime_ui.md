# Realtime Runtime UI Notes

This note records where to adjust the realtime recognition UI so future changes are easy to find.

## Main File

- `frontend/src/components/realtime/RealtimeRuntime.tsx`
- This file owns the webcam lifecycle, MediaPipe Hands overlay, prediction smoothing, fullscreen toggle, and the runtime control panel.

## What To Edit

- `drawOverlay()` and `drawHandSkeleton()` control the hand skeleton rendering.
- The bottom overlay card in the video stage controls the predicted word, confidence, and no-hand message.
- The fullscreen button and `handleToggleFullscreen()` control browser fullscreen mode.
- The model/language selectors in the right panel are the place to change runtime model selection behavior.
- The no-hand gate is handled by `handCountRef`, `sequenceEpochRef`, and the `onResults()` callback.
- The performance HUD uses `fps` and `lastInferenceMs` state.

## Useful Props And Settings

- `mirrorPreview` is controlled by `VITE_MIRROR_PREVIEW`.
- `autoStart` is the prop that starts the camera automatically on mount.
- `debounceMs` is the inference debounce interval passed into the realtime scheduler.

## Related References

- `frontend/src/components/CaptureCamera.tsx` and `frontend/src/components/FullscreenCaptureModal.tsx` show the older fullscreen camera pattern.
- `frontend/src/pages/RealtimeRecognitionPage.tsx` is only a thin page wrapper around the runtime component.
