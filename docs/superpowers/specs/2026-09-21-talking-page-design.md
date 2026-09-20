# Talking Page — MVP Design

**Status:** Approved design for implementation planning  
**Date:** 2026-09-21

## 1. Purpose

Talking Page is a private, offline-first Chrome reader for English webpage content. It replaces flat browser speech with locally synthesized, more engaging narration using Chatterbox-Nano and its built-in default voice.

The first release is for one Windows user. Its architecture must also permit a later hosted speech provider for distributed users without redesigning the Chrome extension.

## 2. MVP Goals

- Read either explicitly selected text or the main article extracted from the current page.
- Begin playback progressively; do not wait for an entire article to be synthesized.
- Keep playback controls in Chrome's browser-level extension UI, not as a floating page overlay.
- Run Chatterbox-Nano locally on CPU with no cloud API calls, usage tokens, or retained history.
- Preserve one active reading session temporarily, then clear it at the defined end of that session.

## 3. Scope and Explicit Non-Goals

### In scope

- English text only.
- Chatterbox-Nano, built-in default voice, and one fixed tuned delivery profile.
- Chrome Manifest V3 extension on current Chrome for Windows.
- Context-menu and toolbar-popup entry points.
- A separately installed and manually started local companion service.
- Selected-text and extracted-main-article modes.

### Not in scope

- Custom or cloned voices.
- Multiple delivery profiles.
- Playback-speed control.
- An automatic desktop/tray launcher.
- A user-facing local/hosted provider switch.
- Hosted synthesis, accounts, telemetry, analytics, or permanent reading history.
- Languages other than English.

## 4. Product Behavior

### Entry points

The right-click menu presents:

- **Read selection** when text is selected.
- **Read page** on a readable page.

The toolbar popup provides read-page access, playback state, and play/pause/stop controls. Standard browser media controls also provide play, pause, resume, and stop. Playback speed is fixed in the MVP.

### Reading modes

**Read selection** narrates precisely the selected text.

**Read page** extracts the primary article. If the extractor cannot identify the main content with adequate confidence, the extension asks the user to select text instead. It never falls back to narrating arbitrary visible DOM text.

### Maximum request size

A single read accepts at most **10,000 English words**. Requests above that limit are rejected with a clear message; content is never silently truncated.

## 5. Session Lifecycle

There is only one active session across the browser.

```text
sessionId = Chrome tab ID + website name
```

A session begins when a user starts a read. Starting a new read in any tab immediately stops, clears, and replaces the old session.

Session metadata includes text chunks, playback position, retry counts, and skipped-chunk details. The extension retains this metadata in Chrome's session-only storage so it can survive a Manifest V3 service-worker restart. The companion service retains generated audio chunks for the active session in its own process memory. No session data is written to disk.

A session ends and its data is cleared when:

- the tab refreshes;
- the tab navigates;
- the tab closes;
- a new read begins in any tab; or
- three hours elapse from session creation.

The three-hour limit is a hard elapsed-time limit, not an inactivity timeout.

## 6. Architecture

```text
Chrome extension (Manifest V3)                 Local companion service
─────────────────────────────────              ───────────────────────
content extraction                              Chatterbox-Nano model, CPU
service worker + read queue      ───────────▶   one-chunk synthesis
offscreen audio controller       ◀───────────   audio + diagnostics
toolbar popup / context menu                    health status
```

### Chrome extension

- **Content extraction:** obtains selected text or page article content.
- **Service worker:** handles context-menu/popup commands, enforces the global active-session rule, coordinates the queue, and stores session metadata in Chrome session-only storage.
- **Offscreen audio controller:** plays the current audio chunk, advances the queue, and integrates browser media controls. It allows playback to continue after the toolbar popup closes. It can be recreated without losing the session.
- **Toolbar popup:** displays current state and exposes browser-level play/pause/stop controls.

The offscreen document is an extension-owned static page created for the `AUDIO_PLAYBACK` purpose. Chrome's Offscreen API is specifically intended for DOM-dependent tasks such as audio playback in Manifest V3.

### Local companion service

- Is manually launched from a terminal in the MVP.
- Loads Chatterbox-Nano once at startup and keeps it in memory.
- Binds only to loopback; it never listens on a LAN interface.
- Synthesizes a short English chunk with the default voice and tuned profile.
- Retains generated WAV chunks in process memory under their session ID, so the extension can request a cached chunk after its offscreen audio controller is recreated.
- Returns WAV audio and limited diagnostics.
- Exposes health state: `ready`, `model-loading`, or `unavailable`.

### Provider boundary

The extension depends on this provider contract rather than on Chatterbox internals:

```text
synthesize(sessionId, chunk, profile) -> audio + duration + diagnostics
getCachedAudio(sessionId, chunkIndex) -> audio
clearSession(sessionId) -> cleared
health() -> ready | model-loading | unavailable
```

The MVP routes this contract to the local service only. A future private configuration value may choose `local` or `hosted`; it is not shown in the extension UI. A hosted implementation must preserve this contract and undergo separate consent, authentication, and privacy design before activation.

## 7. Security and Privacy

- Local mode sends text only between the extension and loopback service.
- The service accepts requests only from the installed extension, protected with an installation-specific local secret.
- The service remains inaccessible from the network.
- Text metadata remains in Chrome session-only storage and generated audio remains in companion-service process memory for the active session only.
- The MVP has no database, accounts, telemetry, analytics, permanent audio cache, or reading history.
- Hosted mode is disabled and requires an explicit future privacy/consent implementation before page content may leave the device.

## 8. Text and Prosody Pipeline

1. Extract selected text exactly, or extract the primary article.
2. Normalize whitespace and preserve headings, paragraphs, lists, and quotes.
3. Normalize only unambiguous spoken forms; do not rewrite the meaning of prose.
4. Count English words and reject input above 10,000 words.
5. Split text on paragraph and sentence boundaries into short synthesis chunks. A sentence is never split. The chunk-size target is established by the CPU benchmark.
6. Queue chunks sequentially for Chatterbox-Nano.

Prosody is deterministic and free of LLM/API token usage. The single profile uses:

- short silence after headings and paragraphs;
- consistent gaps between list items;
- normal punctuation pacing;
- structural emphasis only where it is unambiguous; and
- no theatrical emotion tags in factual prose.

The companion service returns WAV per chunk. WAV avoids an additional encoder dependency and plays natively in Chrome. It caches generated chunks for the active session in memory, so pause/resume does not regenerate completed audio even if Chrome recreates the offscreen audio controller after a period of silence. Playback starts as soon as the first chunk is ready; synthesis continues ahead of playback where CPU capacity permits.

## 9. Failure Handling

The popup represents one clear state at a time:

`local service unavailable` → `model loading` → `extracting` → `generating` → `playing` → `paused` → `complete` or `complete with skipped chunks`.

| Condition | Required behavior |
| --- | --- |
| Local service is not running | Show the README setup/start instruction; retain no stale session. |
| Model is loading | Show a waiting state and keep the pending read. |
| Article extraction is uncertain | Ask the user to select exact text. |
| Input exceeds 10,000 words | Reject before synthesis; do not truncate. |
| A chunk generation fails | Retry that chunk up to three times. |
| Three retries fail | Mark the chunk skipped, record it in session status, and continue. |
| A new read starts | Stop the old session immediately and reclaim its memory. |

## 10. Validation and Acceptance Criteria

The MVP is ready for personal use only when all of the following are demonstrated:

1. The companion service can be started manually and reports healthy.
2. A selected paragraph begins playback without waiting for a complete article.
3. A 2,000-word article plays sequentially with no popup dependency.
4. Pause, resume, and stop work from the extension/browser media controls.
5. Refresh, navigation, tab close, a second-tab read, and three-hour expiry clear the prior session.
6. Main-article extraction rejects uncertain pages and asks for a selection.
7. A failed chunk retries three times, then is skipped while later chunks continue.
8. An over-limit request is rejected at the 10,000-word boundary.
9. No text/audio persists beyond the active session.
10. The README documents separate installation, manual terminal startup, CPU-first expectations, the fixed playback speed, and deferred launcher/custom-voice/hosted-mode work.

## 11. Deferred Follow-Ups

- Custom/default selectable voices and consented voice cloning.
- More reader profiles and playback-speed configuration.
- Desktop/tray launcher and single-installer workflow.
- Hosted speech provider using the same provider contract.
- Hosted-provider authentication, user consent, retention policy, and operational observability.
- Additional languages and language-specific voice models.
