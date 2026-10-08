# Custom Voice (Option C)

**Goal:** Builtin Nano voice by default, optional `TALKING_PAGE_VOICE_SAMPLE` at server start, optional extension WAV upload.

**Precedence per read session:** session-specific upload → `extension-default` upload slot → env sample → builtin `conds.pt`.

**Server:** Mutex around voice prepare + generate; in-memory uploads only; cache keyed by voice fingerprint; env path fails startup if invalid.

**Extension:** Setup panel file picker uploads to `extension-default`; clear restores server default chain.
