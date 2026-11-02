# Video continuity

A video handoff must distinguish an editable project from the last render. Ask for missing editor state only when required for the next action. Use relative paths; keep stable asset IDs in a project manifest if filenames change.

Keep the following in the `video` object or link to maintained project files:

- Brief: audience, platform, intended length, aspect ratio, delivery language, approved reference and brand rules. Never apply one video's style globally without approval.
- Timeline: editor/tool and version, editable project/EDL path, latest approved timeline revision, sequence name, exact timebase (e.g. `30000/1001`), drop-frame/non-drop-frame timecode when applicable. Store edit points as integer frames or rational times, with units; never silently round 29.97 fps to 30.
- Media: source/proxy relationship, audio sample rate, color space/HDR, fonts/LUTs/music licenses, resource paths and fingerprints. Record missing dependencies. Do not include license keys.
- Generation: exact approved prompts, negative prompts, model/version and available seed/settings, reference asset IDs, selected take. If a provider does not expose a seed, record unknown; deterministic recreation is not guaranteed.
- Review: timestamp/frame-specific feedback, user-approved take/version, superseded alternatives and why they failed, remaining issues. “Rendered”, “played back”, and “approved by user” are different states.
- Delivery: output path, codec, resolution, rational fps, audio format, subtitles/burn-in, loudness target if specified. Preserve the command/settings as data; validate before rerunning.
- Checkpoint: last successful render, interrupted work, exact next step (e.g. replace the clip at frames 360–479), observed validation and remaining human review.

Example `video` value (illustrative, not a user's preference):

```json
{
  "timeline": {"editor": "FFmpeg + EDL", "project": "edit/edl.json", "revision": "cut-v03", "fps": "30000/1001", "time_unit": "frames"},
  "review": {"approved": "cut-v02 per supplied review note", "pending": "Check revised music ducking at frames 360-479"},
  "delivery": {"resolution": "1080x1920", "codec": "h264", "audio_sample_rate": 48000},
  "evidence": "reviews/review-v03.md"
}
```

Do not auto-transcribe every video or index all media to resume a task. Read a specific transcript/timeline segment if needed; only perform new transcription or generation within the user's scope and available resources.
