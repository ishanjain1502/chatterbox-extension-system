# Talking Page MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a private, local-first Chrome reader that synthesizes selected English text or extracted article text through Chatterbox-Nano and plays it progressively in browser-level controls.

**Architecture:** A Manifest V3 Chrome extension owns extraction, the single active-session queue, popup/context-menu commands, and offscreen audio playback. A separately started FastAPI companion service owns the CPU-loaded Chatterbox-Nano model and the in-memory audio cache. A small provider client isolates the extension from the current loopback provider and a later hosted implementation.

**Tech Stack:** TypeScript, Vite, Manifest V3, Chrome Offscreen API, Web Audio/HTMLAudioElement, Vitest; Python 3.11, FastAPI, Uvicorn, Pydantic, Pytest, Chatterbox-Nano, Mozilla Readability.

**Spec:** `docs/superpowers/specs/2026-09-21-talking-page-design.md`

## Global Constraints

- Support English input only; reject requests above 10,000 English words without truncating.
- Use Chatterbox-Nano on CPU with its built-in default voice and one fixed tuned profile.
- Provide selected-text and main-article modes through the toolbar popup and context menu.
- Keep one browser-wide active session; a new read stops and clears the old one.
- Define a session as `tab ID + website name`; end it on refresh, navigation, tab close, replacement, or three elapsed hours.
- Retain session metadata only in Chrome session storage and generated WAV only in companion-service memory; write neither to disk.
- Bind the service to loopback only and require an installation-specific secret on every non-health request.
- Play audio through an MV3 offscreen document so it survives popup closure. Do not implement on-page controls or playback-speed controls.
- Retry each failed chunk exactly three times; then skip it and continue.
- Keep local and hosted selection out of the user-facing UI. The MVP only enables local mode.
- Target current Chrome on Windows; use Chrome 109+ because the offscreen audio API is required.

## Review Focus

- A 10,001-word selection must be rejected before any model request; Task 4 pins this boundary.
- A Read-page extraction that has no confident article must demand a selection rather than narrate navigation; Task 8 pins this fallback.
- A paused read whose offscreen document is recreated must resume cached audio without a second TTS call; Task 10 pins cache retrieval.
- A chunk that fails three times must be visible as skipped while the following chunk plays; Task 9 pins this queue behavior.
- Starting a read in another tab must clear the old service cache before synthesizing the new session; Task 9 pins this replacement behavior.

---

## File Structure

```text
README.md                                      user setup and manual validation guide
server/
  pyproject.toml                               Python dependencies and CLI entry point
  src/talking_page_server/
    config.py                                  loopback host, port, secret, provider configuration
    schemas.py                                 request/response types and API errors
    session_cache.py                           memory-only session/audio cache with expiry
    text_rules.py                              word counting and synthesis-safe text validation
    tts_engine.py                              Chatterbox-Nano adapter and testable engine protocol
    app.py                                     FastAPI routes, secret validation, error mapping
    main.py                                    manual `talking-page-server` process entry point
  tests/                                       Pytest unit and route tests
extension/
  package.json                                 TypeScript build/test scripts and dependencies
  vite.config.ts                               extension build configuration
  manifest.json                                MV3 permissions, worker, popup, offscreen resources
  src/shared/types.ts                          session, chunk, provider, and UI-state definitions
  src/shared/constants.ts                      fixed limits, profile and local provider endpoint
  src/shared/chunking.ts                       sentence/paragraph chunker and gap computation
  src/content/extract.ts                       selection and Readability article extraction
  src/background/local-provider.ts             authenticated loopback provider client
  src/background/session-manager.ts            global session state, retries, cancellation and cleanup
  src/background/service-worker.ts             context-menu, tab lifecycle, popup message coordination
  src/offscreen/offscreen.html                 hidden audio-document shell
  src/offscreen/audio-controller.ts            WAV playback and Media Session integration
  src/popup/popup.html                         compact browser-level controls and setup view
  src/popup/popup.ts                           popup state rendering and commands
  tests/                                       Vitest tests for pure code and mocked Chrome adapters
```

## Tasks

### Task 1: Establish the repository, toolchains, and documented manual setup

**Files:**
- Create: `server/pyproject.toml`
- Create: `extension/package.json`
- Create: `extension/tsconfig.json`
- Create: `extension/vite.config.ts`
- Create: `README.md`
- Create: `server/tests/conftest.py`
- Create: `extension/tests/setup.ts`

**Interfaces:**
- Consumes: the global constraints above.
- Produces: `talking-page-server` command, `npm run build`, `npm test`, and `pytest` commands used by every later task.

- [ ] **Step 1: Write dependency manifests with only the required runtime and test packages**

`server/pyproject.toml` must set `requires-python = ">=3.11,<3.12"`, declare `fastapi`, `uvicorn[standard]`, `pydantic`, `chatterbox-tts`, and `torch`, declare `pytest` and `httpx` in a test extra, and expose `talking-page-server = "talking_page_server.main:main"`.

`extension/package.json` must define these scripts:

```json
{
  "scripts": {
    "build": "vite build",
    "test": "vitest run",
    "test:watch": "vitest"
  }
}
```

Use only `@mozilla/readability`, `vite`, `typescript`, `vitest`, and `jsdom` as JavaScript dependencies. Build the extension as static bundled code; do not load remote JavaScript.

- [ ] **Step 2: Write the README acceptance checklist before implementation**

Include exact headings: `Prerequisites`, `Install the local service`, `Start the local service`, `Load the extension`, `Pair the extension`, `Known MVP limits`, and `Manual validation`.

Under `Known MVP limits`, state exactly: English only; one built-in Chatterbox-Nano voice; fixed speed; no permanent history; manually started service; no custom voice; no hosted provider.

- [ ] **Step 3: Create empty test harnesses and prove commands execute**

Create these sentinel tests:

```python
def test_server_test_harness_runs() -> None:
    assert True
```

```ts
import { expect, test } from "vitest";

test("extension test harness runs", () => {
  expect(true).toBe(true);
});
```

- [ ] **Step 4: Run the harnesses**

Run: `python -m pytest server/tests -q`

Expected: one passing server test.

Run: `npm --prefix extension test`

Expected: one passing extension test.

Run: `npm --prefix extension run build`

Expected: a distributable static extension directory is generated without TypeScript errors.

- [ ] **Step 5: Commit the setup baseline**

```bash
git add README.md server extension
git commit -m "chore: scaffold Talking Page services and extension"
```

### Task 2: Implement the local service configuration and secret boundary

**Files:**
- Create: `server/src/talking_page_server/config.py`
- Create: `server/src/talking_page_server/schemas.py`
- Create: `server/tests/test_config.py`
- Modify: `server/pyproject.toml`
- Modify: `README.md`

**Interfaces:**
- Consumes: `TALKING_PAGE_TOKEN`, `TALKING_PAGE_HOST`, and `TALKING_PAGE_PORT` environment variables.
- Produces: `ServerSettings`, `HealthResponse`, `SynthesisRequest`, `ServiceError`, and `require_service_token()` for Tasks 3, 5, and 6.

- [ ] **Step 1: Write failing tests for safe defaults and secret validation**

```python
from talking_page_server.config import ServerSettings

def test_defaults_bind_only_to_loopback(monkeypatch) -> None:
    monkeypatch.setenv("TALKING_PAGE_TOKEN", "a" * 32)
    settings = ServerSettings.from_environment()
    assert settings.host == "127.0.0.1"
    assert settings.port == 8765

def test_missing_token_is_rejected(monkeypatch) -> None:
    monkeypatch.delenv("TALKING_PAGE_TOKEN", raising=False)
    with pytest.raises(ValueError, match="TALKING_PAGE_TOKEN"):
        ServerSettings.from_environment()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest server/tests/test_config.py -q`

Expected: FAIL because `talking_page_server.config` does not exist.

- [ ] **Step 3: Implement the configuration and request models**

Implement these exact data shapes:

```python
@dataclass(frozen=True)
class ServerSettings:
    host: str
    port: int
    token: str
    session_ttl_seconds: int = 10_800

class SynthesisRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=256)
    chunk_index: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=2_000)
    profile: Literal["engaging"] = "engaging"
```

`from_environment()` must allow only `127.0.0.1` and `localhost`, reject a token shorter than 32 characters, and reject a port outside 1024–65535. Normalize `localhost` to `127.0.0.1` before Uvicorn starts.

- [ ] **Step 4: Add a pairing instruction to the README**

Document that the user generates a 32-or-more-character token, starts the service with `TALKING_PAGE_TOKEN`, and pastes the same token into the extension's one-time local pairing field. State that this is not a hosted-provider setting.

- [ ] **Step 5: Run configuration tests**

Run: `python -m pytest server/tests/test_config.py -q`

Expected: PASS.

- [ ] **Step 6: Commit configuration boundaries**

```bash
git add server README.md
git commit -m "feat: add local service configuration and pairing token"
```

### Task 3: Build the memory-only service session cache

**Files:**
- Create: `server/src/talking_page_server/session_cache.py`
- Create: `server/tests/test_session_cache.py`

**Interfaces:**
- Consumes: `ServerSettings.session_ttl_seconds` from Task 2.
- Produces: `SessionAudioCache.put(session_id, chunk_index, wav, duration_ms)`, `get(session_id, chunk_index)`, `clear(session_id)`, and `purge_expired(now)` for Tasks 5 and 6.

- [ ] **Step 1: Write failing cache tests**

```python
def test_cache_returns_audio_for_active_session() -> None:
    cache = SessionAudioCache(ttl_seconds=10)
    cache.put("12-example.com", 0, b"wav", 1200, now=100)
    assert cache.get("12-example.com", 0, now=105).wav == b"wav"

def test_cache_expires_audio_without_writing_files() -> None:
    cache = SessionAudioCache(ttl_seconds=10)
    cache.put("12-example.com", 0, b"wav", 1200, now=100)
    assert cache.get("12-example.com", 0, now=111) is None

def test_clear_removes_every_chunk_for_session() -> None:
    cache = SessionAudioCache(ttl_seconds=10)
    cache.put("12-example.com", 0, b"one", 100, now=100)
    cache.put("12-example.com", 1, b"two", 100, now=100)
    cache.clear("12-example.com")
    assert cache.get("12-example.com", 0, now=100) is None
    assert cache.get("12-example.com", 1, now=100) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest server/tests/test_session_cache.py -q`

Expected: FAIL because `SessionAudioCache` does not exist.

- [ ] **Step 3: Implement a dictionary-backed cache with injected clock values**

Use a private dictionary keyed by session ID then chunk index. Store immutable `CachedAudio(wav: bytes, duration_ms: int, created_at: float)`. `get()` must call `purge_expired(now)` before lookup. Do not import filesystem, SQLite, or cache-service packages.

- [ ] **Step 4: Run the cache tests**

Run: `python -m pytest server/tests/test_session_cache.py -q`

Expected: PASS.

- [ ] **Step 5: Commit cache behavior**

```bash
git add server/src/talking_page_server/session_cache.py server/tests/test_session_cache.py
git commit -m "feat: add expiring in-memory audio cache"
```

### Task 4: Implement service-side input validation and deterministic delivery preparation

**Files:**
- Create: `server/src/talking_page_server/text_rules.py`
- Create: `server/tests/test_text_rules.py`

**Interfaces:**
- Consumes: raw English chunk text from Task 6.
- Produces: `count_words(text) -> int`, `validate_total_word_count(text) -> None`, `validate_chunk_text(text) -> str`, and `prepare_for_narration(text) -> str` for Task 5.

- [ ] **Step 1: Write failing tests for word counting and text preservation**

```python
def test_count_words_handles_punctuation() -> None:
    assert count_words("Hello, world! This is three.") == 5

def test_10001_words_are_rejected() -> None:
    text = "word " * 10_001
    with pytest.raises(ValueError, match="10,000"):
        validate_total_word_count(text)

def test_prepare_preserves_words_and_normalizes_space() -> None:
    assert prepare_for_narration("A  heading\n\nwith   space.") == "A heading. With space."
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest server/tests/test_text_rules.py -q`

Expected: FAIL because `text_rules` does not exist.

- [ ] **Step 3: Implement minimal deterministic normalization**

Treat a contiguous run of letters, digits, or internal apostrophes as a word. Collapse whitespace. Convert a paragraph boundary into `. ` only when the preceding non-space character is not `.`, `!`, `?`, `:`, or `;`. Do not add emotion tags, change word order, or call an LLM. Keep a 2,000-character service-chunk cap and raise a value error when exceeded.

- [ ] **Step 4: Run the validation tests**

Run: `python -m pytest server/tests/test_text_rules.py -q`

Expected: PASS.

- [ ] **Step 5: Commit deterministic text rules**

```bash
git add server/src/talking_page_server/text_rules.py server/tests/test_text_rules.py
git commit -m "feat: add deterministic text validation rules"
```

### Task 5: Add the Chatterbox-Nano engine adapter with a fake-engine seam

**Files:**
- Create: `server/src/talking_page_server/tts_engine.py`
- Create: `server/tests/test_tts_engine.py`

**Interfaces:**
- Consumes: prepared text from Task 4.
- Produces: `SpeechEngine.health() -> EngineStatus` and `SpeechEngine.synthesize(text: str) -> GeneratedAudio` for Task 6.

- [ ] **Step 1: Write failing tests using a fake model factory**

```python
def test_engine_loads_nano_on_cpu_once() -> None:
    factory = FakeNanoFactory()
    engine = ChatterboxNanoEngine(factory=factory)
    engine.load()
    engine.load()
    assert factory.calls == [("cpu", True)]

def test_engine_returns_wav_bytes_and_duration() -> None:
    engine = ChatterboxNanoEngine(factory=FakeNanoFactory())
    engine.load()
    audio = engine.synthesize("A short sentence.")
    assert audio.wav[:4] == b"RIFF"
    assert audio.duration_ms > 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest server/tests/test_tts_engine.py -q`

Expected: FAIL because `ChatterboxNanoEngine` does not exist.

- [ ] **Step 3: Implement the adapter without importing Chatterbox at module import time**

Define:

```python
class SpeechEngine(Protocol):
    def load(self) -> None: ...
    def health(self) -> Literal["ready", "model-loading", "unavailable"]: ...
    def synthesize(self, text: str) -> GeneratedAudio: ...
```

`ChatterboxNanoEngine.load()` must lazily import `ChatterboxTurboTTS`, invoke `from_pretrained(device="cpu", nano=True)`, and retain that one model instance. `synthesize()` must generate with no reference voice path and serialize the returned waveform as a mono WAV byte stream. Calculate duration from frames and sample rate. Convert model exceptions into a typed `SpeechSynthesisError` without exposing tracebacks over HTTP.

- [ ] **Step 4: Run engine tests**

Run: `python -m pytest server/tests/test_tts_engine.py -q`

Expected: PASS without downloading model weights because the factory is fake.

- [ ] **Step 5: Commit engine adapter**

```bash
git add server/src/talking_page_server/tts_engine.py server/tests/test_tts_engine.py
git commit -m "feat: add CPU Chatterbox Nano engine adapter"
```

### Task 6: Expose authenticated local HTTP routes

**Files:**
- Create: `server/src/talking_page_server/app.py`
- Create: `server/src/talking_page_server/main.py`
- Create: `server/tests/test_app.py`

**Interfaces:**
- Consumes: `ServerSettings`, `SynthesisRequest`, `SessionAudioCache`, and `SpeechEngine` from Tasks 2–5.
- Produces:
  - `GET /v1/health` → `{ "status": "ready" | "model-loading" | "unavailable" }`
  - `POST /v1/sessions/{session_id}/chunks/{chunk_index}` with `X-Talking-Page-Token` → `audio/wav`
  - `GET /v1/sessions/{session_id}/chunks/{chunk_index}` with token → cached `audio/wav`
  - `DELETE /v1/sessions/{session_id}` with token → HTTP 204.

- [ ] **Step 1: Write failing route tests with fake engine and cache**

```python
def test_health_needs_no_secret(client) -> None:
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}

def test_synthesis_rejects_missing_secret(client) -> None:
    response = client.post("/v1/sessions/12-example/chunks/0", json={"text": "Hello."})
    assert response.status_code == 401

def test_synthesis_caches_wav(client, token_header) -> None:
    response = client.post(
        "/v1/sessions/12-example/chunks/0",
        headers=token_header,
        json={"text": "Hello.", "profile": "engaging"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/wav")
    cached = client.get("/v1/sessions/12-example/chunks/0", headers=token_header)
    assert cached.content == response.content
```

- [ ] **Step 2: Run route tests to verify they fail**

Run: `python -m pytest server/tests/test_app.py -q`

Expected: FAIL because `create_app` does not exist.

- [ ] **Step 3: Implement routes and explicit HTTP error mapping**

`create_app(settings, engine, cache)` must use dependency injection for tests. Health returns no secret. Every session route requires an exact `X-Talking-Page-Token` match using constant-time comparison. Synthesis stores successful bytes in `SessionAudioCache`, sends `X-Talking-Page-Duration-Ms`, and returns 503 for model-loading/unavailable, 422 for invalid content, and 502 for synthesis failure. A cache miss returns 404. Delete clears the cache and returns 204.

Do not enable CORS. The extension's explicit loopback host permission permits its own request, while ordinary webpages cannot read a loopback response or complete a custom-token preflight. Pass loopback host/port from `ServerSettings` to Uvicorn in `main()`.

- [ ] **Step 4: Run route tests**

Run: `python -m pytest server/tests/test_app.py -q`

Expected: PASS.

- [ ] **Step 5: Run the complete server suite**

Run: `python -m pytest server/tests -q`

Expected: PASS.

- [ ] **Step 6: Commit service API**

```bash
git add server
git commit -m "feat: expose authenticated local speech API"
```

### Task 7: Create the extension manifest, shared types, and local pairing store

**Files:**
- Create: `extension/manifest.json`
- Create: `extension/src/shared/types.ts`
- Create: `extension/src/shared/constants.ts`
- Create: `extension/src/background/pairing-store.ts`
- Create: `extension/tests/pairing-store.test.ts`

**Interfaces:**
- Consumes: service endpoint contract from Task 6.
- Produces: `ProviderSettings`, `ReadMode`, `ReaderSession`, `ChunkStatus`, and `PairingStore.get()/save()` for Tasks 8–11.

- [ ] **Step 1: Write failing pairing-store tests with mocked Chrome storage**

```ts
test("stores only the local endpoint and token", async () => {
  const store = new PairingStore(fakeChromeStorage);
  await store.save({ endpoint: "http://127.0.0.1:8765", token: "a".repeat(32) });
  await expect(store.get()).resolves.toEqual({
    endpoint: "http://127.0.0.1:8765",
    token: "a".repeat(32),
  });
});

test("rejects a non-loopback endpoint", async () => {
  const store = new PairingStore(fakeChromeStorage);
  await expect(store.save({ endpoint: "https://example.com", token: "a".repeat(32) })).rejects.toThrow("loopback");
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix extension test -- pairing-store.test.ts`

Expected: FAIL because `PairingStore` does not exist.

- [ ] **Step 3: Implement manifest and shared contracts**

The MV3 manifest must declare `activeTab`, `contextMenus`, `storage`, and `offscreen`; declare host access only for `http://127.0.0.1:8765/*`; set the service worker as a module; register the popup; and expose the static offscreen page. Do not request broad page host permissions: use `activeTab` and `chrome.scripting` only after a user action.

Define these exact types:

```ts
export type ReadMode = "selection" | "page";
export type SessionPhase = "extracting" | "generating" | "playing" | "paused" | "complete" | "failed";
export type ChunkStatus = "pending" | "generating" | "ready" | "playing" | "skipped" | "complete";
export interface ProviderSettings { endpoint: string; token: string; }
export interface ReaderSession { id: string; tabId: number; websiteName: string; startedAt: number; phase: SessionPhase; chunks: ReaderChunk[]; }
export interface ReaderChunk { index: number; text: string; gapAfterMs: number; attempts: number; status: ChunkStatus; durationMs?: number; }
```

`PairingStore` uses `chrome.storage.local`, validates a `http://127.0.0.1` endpoint and a token length of at least 32, and never stores a provider mode switch.

- [ ] **Step 4: Run pairing tests and extension build**

Run: `npm --prefix extension test -- pairing-store.test.ts`

Expected: PASS.

Run: `npm --prefix extension run build`

Expected: PASS with a Manifest V3 extension artifact.

- [ ] **Step 5: Commit extension foundation**

```bash
git add extension
git commit -m "feat: add extension manifest and local pairing storage"
```

### Task 8: Implement safe text extraction and deterministic extension chunking

**Files:**
- Create: `extension/src/content/extract.ts`
- Create: `extension/src/shared/chunking.ts`
- Create: `extension/tests/extract.test.ts`
- Create: `extension/tests/chunking.test.ts`

**Interfaces:**
- Consumes: `ReadMode` and constants from Task 7.
- Produces: `extractSelection(document)`, `extractArticle(document)`, `chunkText(text)`, and `wordCount(text)` for Task 9.

- [ ] **Step 1: Write failing extraction and chunking tests**

```ts
test("uses exactly selected text", () => {
  const document = dom("<p>Ignored</p>", "Chosen text");
  expect(extractSelection(document)).toEqual({ ok: true, text: "Chosen text" });
});

test("does not use body text when article extraction is uncertain", () => {
  const document = dom("<nav>Home Products</nav><div>Random page chrome</div>");
  expect(extractArticle(document)).toEqual({ ok: false, reason: "select-text" });
});

test("never splits a sentence and assigns heading gaps", () => {
  const chunks = chunkText("Heading\n\nOne short sentence. A second sentence.");
  expect(chunks.map((chunk) => chunk.text)).toEqual(["Heading.", "One short sentence. A second sentence."]);
  expect(chunks[0].gapAfterMs).toBeGreaterThan(chunks[1].gapAfterMs);
});

test("rejects one sentence above the service chunk limit", () => {
  expect(() => chunkText("a".repeat(2_001) + ".")).toThrow("single sentence");
});

test("rejects 10001 words", () => {
  expect(() => chunkText("word ".repeat(10_001))).toThrow("10,000");
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix extension test -- extract.test.ts chunking.test.ts`

Expected: FAIL because extraction and chunking modules do not exist.

- [ ] **Step 3: Implement extraction and chunking**

`extractSelection()` trims `window.getSelection()?.toString()` and fails for empty output. `extractArticle()` clones the document and runs `Readability`; it succeeds only if resulting text is non-empty and at least 200 characters, otherwise returns `{ ok: false, reason: "select-text" }`. It does not return raw HTML.

`chunkText()` enforces the 10,000-word limit, treats blank-line-separated single-line text ending without punctuation as headings, and splits remaining blocks only at sentence terminators. Start with `MAX_CHUNK_CHARS = 1_600`; preserve a whole sentence when it exceeds that target only if it remains at or below the service's 2,000-character hard limit. Reject a single sentence above 2,000 characters with a clear selection-shortening message. Set heading gap to 750 ms, paragraph gap to 450 ms, list-item gap to 250 ms, and sentence-only gap to 120 ms.

- [ ] **Step 4: Run extraction and chunking tests**

Run: `npm --prefix extension test -- extract.test.ts chunking.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit content pipeline**

```bash
git add extension/src/content extension/src/shared extension/tests
git commit -m "feat: add page extraction and narration chunking"
```

### Task 9: Implement the authenticated provider client and active-session queue

**Files:**
- Create: `extension/src/background/local-provider.ts`
- Create: `extension/src/background/session-manager.ts`
- Create: `extension/tests/local-provider.test.ts`
- Create: `extension/tests/session-manager.test.ts`

**Interfaces:**
- Consumes: `ProviderSettings`, `ReaderSession`, chunks, and pairing data from Tasks 7–8; HTTP routes from Task 6.
- Produces: `LocalProvider.health()`, `synthesize()`, `getCachedAudio()`, `clearSession()`, and `SessionManager.start()/stop()/next()` for Tasks 10–11.

- [ ] **Step 1: Write failing provider and session-manager tests**

```ts
test("sends the pairing token and returns WAV bytes", async () => {
  const fetch = fakeFetch.wav(800);
  const provider = new LocalProvider({ endpoint: "http://127.0.0.1:8765", token: "a".repeat(32) }, fetch);
  const result = await provider.synthesize("12-example", 0, "Hello.");
  expect(fetch.lastHeaders["X-Talking-Page-Token"]).toBe("a".repeat(32));
  expect(result.durationMs).toBe(800);
});

test("retries exactly three times and skips a failed chunk", async () => {
  const manager = new SessionManager(alwaysFailingProvider, fakeAudioController, fakeSessionStore);
  await manager.start(makeSession(["First.", "Second."]));
  expect(alwaysFailingProvider.calls).toBe(3);
  expect(manager.currentSession()?.chunks[0].status).toBe("skipped");
  expect(manager.currentSession()?.chunks[1].status).toBe("ready");
});

test("new session clears the old provider cache before starting", async () => {
  const manager = new SessionManager(readyProvider, fakeAudioController, fakeSessionStore);
  await manager.start(makeSession(["Old."], "1-old"));
  await manager.start(makeSession(["New."], "2-new"));
  expect(readyProvider.cleared).toContain("1-old");
  expect(manager.currentSession()?.id).toBe("2-new");
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix extension test -- local-provider.test.ts session-manager.test.ts`

Expected: FAIL because provider and session manager modules do not exist.

- [ ] **Step 3: Implement provider and queue semantics**

`LocalProvider` uses `fetch`, adds `X-Talking-Page-Token`, rejects non-WAV responses, parses `X-Talking-Page-Duration-Ms`, and maps 401, 404, 422, 502, and 503 into named errors. `SessionManager` stores only `ReaderSession` metadata in `chrome.storage.session`; it never stores WAV bytes there. It must:

- clear any prior provider session before replacing it;
- send one chunk at a time;
- retry one failed chunk exactly three times;
- set a three-failure chunk to `skipped` and immediately process the next;
- call the audio-controller interface after each ready chunk;
- schedule a hard expiry at `startedAt + 10_800_000` milliseconds; and
- clear provider cache and session storage in `stop()`.

- [ ] **Step 4: Run provider and queue tests**

Run: `npm --prefix extension test -- local-provider.test.ts session-manager.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit provider and queue**

```bash
git add extension/src/background extension/tests
git commit -m "feat: add local provider and single-session queue"
```

### Task 10: Implement persistent offscreen audio playback and media controls

**Files:**
- Create: `extension/src/offscreen/offscreen.html`
- Create: `extension/src/offscreen/audio-controller.ts`
- Create: `extension/tests/audio-controller.test.ts`
- Modify: `extension/manifest.json`

**Interfaces:**
- Consumes: `ReaderChunk`, `LocalProvider.getCachedAudio()`, and session messages from Task 9.
- Produces: `AudioController.enqueue()`, `play()`, `pause()`, `stop()`, and runtime messages `audio-ended`, `audio-paused`, and `audio-error` for Task 11.

- [ ] **Step 1: Write failing playback tests with fake audio elements**

```ts
test("plays queued WAV chunks in order and observes their gaps", async () => {
  const audio = new FakeAudioElement();
  const controller = new AudioController(audio, fakeMediaSession);
  await controller.enqueue({ bytes: wavBytes("one"), gapAfterMs: 250, chunkIndex: 0 });
  await controller.enqueue({ bytes: wavBytes("two"), gapAfterMs: 0, chunkIndex: 1 });
  audio.finish();
  await timers.advanceByTimeAsync(250);
  expect(audio.playedSources).toHaveLength(2);
});

test("recreates current playback from cached bytes after an offscreen restart", async () => {
  const controller = new AudioController(new FakeAudioElement(), fakeMediaSession);
  await controller.restore({ bytes: wavBytes("cached"), currentTime: 1.2, chunkIndex: 3 });
  expect(controller.currentChunkIndex()).toBe(3);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix extension test -- audio-controller.test.ts`

Expected: FAIL because `AudioController` does not exist.

- [ ] **Step 3: Implement offscreen playback**

Create the offscreen document only through `chrome.offscreen.createDocument()` with reason `AUDIO_PLAYBACK`. The controller creates object URLs from WAV `ArrayBuffer` values, revokes URLs after end/stop, applies configured silence gaps, and reports events through `chrome.runtime.sendMessage`.

Set Media Session handlers for `play`, `pause`, and `stop`. Do not register seek, next-track, previous-track, or playback-rate handlers. On an offscreen restart, the service worker asks `LocalProvider.getCachedAudio()` for the current chunk and passes saved chunk index/current time into `restore()`.

- [ ] **Step 4: Run audio tests and build**

Run: `npm --prefix extension test -- audio-controller.test.ts`

Expected: PASS.

Run: `npm --prefix extension run build`

Expected: PASS.

- [ ] **Step 5: Commit audio controller**

```bash
git add extension/src/offscreen extension/manifest.json extension/tests
git commit -m "feat: add offscreen audio playback controls"
```

### Task 11: Wire Chrome commands, popup states, lifecycle cleanup, and documentation

**Files:**
- Create: `extension/src/background/service-worker.ts`
- Create: `extension/src/popup/popup.html`
- Create: `extension/src/popup/popup.ts`
- Create: `extension/tests/service-worker.test.ts`
- Modify: `README.md`

**Interfaces:**
- Consumes: extraction functions from Task 8, `SessionManager` from Task 9, and audio events from Task 10.
- Produces: a manually loadable extension with all MVP commands and visible state.

- [ ] **Step 1: Write failing service-worker lifecycle tests**

```ts
test("selection command requests selection extraction from the active tab", async () => {
  const worker = createWorkerHarness();
  await worker.onContextMenu({ menuItemId: "read-selection", selectionText: "Selected words" }, { id: 8, url: "https://example.com/a" });
  expect(worker.manager.startedWith?.tabId).toBe(8);
  expect(worker.manager.startedWith?.chunks[0].text).toBe("Selected words");
});

test("navigation stops the tab session", async () => {
  const worker = createWorkerHarness();
  await worker.manager.start(makeSession(["One."], "8-example", 8));
  await worker.onTabUpdated(8, { status: "loading" });
  expect(worker.manager.currentSession()).toBeNull();
});

test("page extraction failure asks for selection", async () => {
  const worker = createWorkerHarness({ articleResult: { ok: false, reason: "select-text" } });
  await worker.onContextMenu({ menuItemId: "read-page" }, { id: 8, url: "https://example.com/a" });
  expect(worker.popupState.message).toContain("select text");
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm --prefix extension test -- service-worker.test.ts`

Expected: FAIL because service worker wiring does not exist.

- [ ] **Step 3: Implement browser integration and compact popup**

Create `read-selection` and `read-page` context-menu items on install. Show `read-selection` only in selection contexts and `read-page` only in page contexts. Use `chrome.scripting.executeScript` after the user command to invoke extraction in the active tab. Derive website name from `new URL(tab.url).hostname`; form session IDs as `${tab.id}-${hostname}`.

Listen for `tabs.onUpdated` status `loading` and `tabs.onRemoved`; stop only the matching active session. Relay audio-controller messages into session state. The popup shows the exact states specified in the design: local service unavailable, model loading, extracting, generating, playing, paused, complete, and complete with skipped chunks.

When pairing is absent, show endpoint/token fields and a `Pair local service` action. After pairing, the popup has only state plus play/pause/stop; it has no provider selector, voice selector, or speed control.

- [ ] **Step 4: Expand README manual validation steps**

Add exact manual checks for: starting the service; pairing; selected text; article page; popup closure during playback; media play/pause/stop; replacing a read in another tab; refreshing while playing; 10,001-word rejection; service unavailable; and a failed chunk skip using the service's test fake engine mode.

- [ ] **Step 5: Run extension tests and builds**

Run: `npm --prefix extension test`

Expected: PASS.

Run: `npm --prefix extension run build`

Expected: PASS.

- [ ] **Step 6: Commit end-to-end browser wiring**

```bash
git add extension README.md
git commit -m "feat: wire reader commands and browser controls"
```

### Task 12: Run real local benchmark and acceptance validation

**Files:**
- Create: `docs/benchmarks/2026-09-21-nano-cpu-baseline.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: completed local service and built extension from Tasks 1–11.
- Produces: recorded CPU baseline and a verified personal-use MVP.

- [ ] **Step 1: Add a benchmark fixture with known word count**

Create `server/tests/fixtures/benchmark-article.txt` containing 2,000 English words, headings, ordinary paragraphs, and a list. Include no copyrighted article text; use original fixture prose.

- [ ] **Step 2: Run the real model benchmark on the target machine**

Start the service with the actual Chatterbox-Nano model and record:

```text
machine CPU name
Python version
Chatterbox package version
model load time in seconds
first 1,600-character chunk generation time in seconds
2,000-word total generation time in seconds
output audio duration in seconds
real-time factor = generation time / output duration
peak process memory reported by Windows Task Manager
```

Write the measured values and date to `docs/benchmarks/2026-09-21-nano-cpu-baseline.md`. Do not invent values.

- [ ] **Step 3: Execute each acceptance criterion manually**

Use the checklist in spec section 10. For each item, write `pass` or `fail` and one observed fact in the benchmark document. A failed item must remain marked `fail`; do not claim MVP completion.

- [ ] **Step 4: Update the README with verified limits**

Add the benchmark real-time factor and first-audio timing only if Step 2 recorded them. Keep fixed speed, manual service startup, English-only, and no permanent history in the limits section.

- [ ] **Step 5: Run final automated checks**

Run: `python -m pytest server/tests -q`

Expected: PASS.

Run: `npm --prefix extension test`

Expected: PASS.

Run: `npm --prefix extension run build`

Expected: PASS.

- [ ] **Step 6: Commit benchmark and verification record**

```bash
git add docs/benchmarks README.md server/tests/fixtures
git commit -m "docs: record local Nano benchmark"
```

## Self-Review

### Spec coverage

| Design requirement | Plan task |
| --- | --- |
| Local CPU Nano and built-in voice | Tasks 1, 5, 12 |
| Selection and article modes | Tasks 8 and 11 |
| Popup, context menu, browser controls | Tasks 7, 10, 11 |
| One active session and defined expiry | Tasks 3, 9, 11 |
| Session-only retention | Tasks 3, 6, 9, 10 |
| Local/hosted provider boundary | Tasks 6, 7, 9 |
| Loopback and secret protection | Tasks 2 and 6 |
| Deterministic prosody and chunking | Tasks 4 and 8 |
| Three retries then skip | Task 9 |
| 10,000-word limit | Tasks 4 and 8 |
| README/deferred work and validation | Tasks 1, 11, 12 |

No spec requirement is unassigned.

### Interface consistency

- The service uses `session_id` and `chunk_index` in request paths, cache keys, and extension provider calls.
- The fixed `engaging` profile is the sole accepted profile in service schemas and extension constants.
- `ReaderSession` retains metadata only; WAV bytes flow through `LocalProvider` into `AudioController` and remain cached only in the service.
- `clearSession()` is invoked both when replacing and ending a session.

### Placeholder scan

This plan contains no unassigned implementation steps, unknown file paths, or deferred behavior inside the MVP tasks. Deferred product work is isolated in the approved design spec and excluded from the plan.
