# Chatterbox-Nano CPU Baseline

Date: pending manual run

Machine: pending

Python version: pending

Chatterbox package version: pending

## Measurements

| Metric | Value |
| --- | --- |
| Model load time (seconds) | pending |
| First 1,600-character chunk generation time (seconds) | pending |
| 2,000-word total generation time (seconds) | pending |
| Output audio duration (seconds) | pending |
| Real-time factor (generation / duration) | pending |
| Peak process memory (Windows Task Manager) | pending |

## Acceptance checklist

Run each item from the design spec after the local service and extension are paired on the target machine. Record one observed fact per row.

| Criterion | Result | Observation |
| --- | --- | --- |
| Companion service starts manually and reports healthy | pending | |
| Selected paragraph begins playback before full article synthesis | pending | |
| 2,000-word article plays sequentially with popup closed | pending | |
| Pause, resume, and stop work from browser media controls | pending | |
| Refresh, navigation, tab close, second-tab read, and 3-hour expiry clear session | pending | |
| Uncertain article extraction asks for a selection | pending | |
| Failed chunk retries three times then skips while later chunks continue | pending | |
| Over-limit request rejected at 10,000 words | pending | |
| No text/audio persists beyond the active session | pending | |
| README documents install, manual startup, CPU expectations, fixed speed, deferred work | pending | |

## Notes

Use `server/tests/fixtures/benchmark-article.txt` as the 2,000-word synthesis fixture. Do not invent timing values; replace every `pending` entry with measured results from the target Windows machine.
