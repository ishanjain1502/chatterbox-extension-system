# Talking Page

Talking Page is a local, English-only Chrome reader. It turns selected text or an extracted article into speech using Chatterbox-Nano on this computer.

## Prerequisites

- Windows with current Google Chrome
- Python 3.11
- Internet access for the one-time Chatterbox model download

## Quick start (extension + server side by side)

### One-time setup

Use **CPython 3.11** from [python.org](https://www.python.org/downloads/release/python-3119/) or `winget install Python.Python.3.11`. Do not use the MSYS/Git Bash `python` shim.

From the project root in PowerShell:

```powershell
cd E:\Projects\talking-page

# Create the venv (if you have not already)
cd server
.\setup-venv.ps1
cd ..

# Or, if your venv is already at the project root:
.\.venv\Scripts\Activate.ps1
pip install -r server\requirements.txt
```

Pick one token and reuse it for both the server and the extension. It must be at least 32 characters. Store it in a `.env` file at the project root (see `.env.example`):

```powershell
copy .env.example .env
# Edit .env if you want your own token
```

Optional keys in `.env`:

```dotenv
# TALKING_PAGE_VOICE_SAMPLE=E:\path\to\your-voice.wav
```

### Terminal 1 — start the server

Keep this terminal open while you use the extension. The server reads `.env` automatically:

```powershell
cd E:\Projects\talking-page
.\.venv\Scripts\Activate.ps1
python server\talking_page_server.py
```

The first run downloads the Chatterbox-Nano model and can take several minutes. Wait until the process stays running without errors.

### Terminal 2 — verify the server (optional)

```powershell
curl http://127.0.0.1:8765/v1/health
```

Expected response: `{"status":"ready"}`

### Chrome — load the extension

1. Open `chrome://extensions`
2. Turn on **Developer mode** (top right)
3. Click **Load unpacked**
4. Select `E:\Projects\talking-page\extension`
5. Pin **Talking Page** from the extensions menu if you want quick access

Click the extension icon to open the popup. The pairing UI is still minimal in this MVP build; the server must already be running on `http://127.0.0.1:8765`.

### Day-to-day use

1. Start the server in a terminal (Terminal 1 above).
2. Use Chrome with the extension already loaded — you do not need to reload the extension each time unless you change extension files.

## Install the local service (details)

From `server`, `.\setup-venv.ps1` creates `server\.venv` with Python 3.11 and installs `requirements.txt`. If you prefer a root-level venv instead, activate it and run `pip install -r server\requirements.txt`.

## Run the server in Docker (optional)

Docker runs only the **Python TTS service**. You still load the Chrome extension on the host the same way as above; it continues to call `http://127.0.0.1:8765`.

Works on Linux, macOS, and Windows when [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or another Docker engine) is installed. The image uses **CPython 3.11** and **CPU** PyTorch, matching the default local server.

### One-time build

From the project root (with `.env` present — copy from `.env.example` if needed):

```bash
docker compose build
```

### Start the container

Compose loads variables from `.env`:

```bash
docker compose up
```

The first start downloads the Chatterbox model into a Docker volume (`talking-page-hf-cache`) and can take several minutes. When logs show the server is listening, check:

```bash
curl http://127.0.0.1:8765/v1/health
```

Run detached: `docker compose up -d`. Stop: `docker compose down` (the Hugging Face cache volume is kept).

### Custom voice in Docker

Mount a WAV into the container and point the server at the in-container path (over 5 seconds, clean English speech):

```yaml
# docker-compose.override.yml (gitignored locally if you prefer)
services:
  talking-page:
    environment:
      TALKING_PAGE_VOICE_SAMPLE: /voice/sample.wav
    volumes:
      - ./testVoices/your-voice.wav:/voice/sample.wav:ro
```

Or with plain Docker:

```bash
docker run --rm -p 127.0.0.1:8765:8765 \
  --env-file .env \
  -e TALKING_PAGE_HOST=0.0.0.0 \
  -v talking-page-hf-cache:/root/.cache/huggingface \
  talking-page
```

(`docker build -t talking-page .` first.)

Inside the container the service binds to `0.0.0.0`; publish it only on `127.0.0.1` on the host so it is not reachable from other machines on your network.

## Pair the extension

Open the extension popup and paste the `TALKING_PAGE_TOKEN` value from your `.env` file. The extension talks only to `http://127.0.0.1:8765`.

## Custom voice (optional)

You can use a custom English voice in two ways (extension upload wins over the env sample, then built-in Nano):

1. **Server env sample** — set `TALKING_PAGE_VOICE_SAMPLE` in `.env` to a local `.wav` file (longer than 5 seconds) before starting the server. If the path is set but missing or too short, the server refuses to start.
2. **Extension upload** — in the popup, choose a WAV file. It is sent to the local service in memory only (not saved to disk). Use **Use server default voice** to remove the upload and fall back to the env sample or built-in voice.

Only use voice samples you have the right to clone.

## Paralinguistic tagger (optional model)

The server can insert Chatterbox inline tags (`[chuckle]`, `[sigh]`, and similar) into each chunk before synthesis. A small gap-classifier model runs in-process when a weights file is present.

**Training data:** JSONL with one object per line:

```json
{"plain": "Hello world", "tagged": "Hello [sigh] world"}
```

Put your dataset at `server/data/paralinguistic_pairs.jsonl` (gitignored). A tiny fixture lives at `server/data/paralinguistic_pairs.fixture.jsonl` for smoke tests.

**Train** (from the project root with the venv active):

```powershell
python -m server.paralinguistic.train --data server/data/paralinguistic_pairs.jsonl --out server/models/paralinguistic_tagger.pt
```

**Tune in `.env`:** `TALKING_PAGE_TAG_CONFIDENCE_THRESHOLD` (default `0.65`) controls how often tags are inserted. Set `TALKING_PAGE_TAGGER_ENABLED=0` to disable. If the model file is missing, the server logs once and sends plain text to Chatterbox.

## Known MVP limits

- English only
- One custom voice at a time (builtin, env, or extension upload)
- One fixed narration speed
- One active browser-wide reading session
- No permanent reading history or audio storage
- Local service is started manually in a terminal
- No hosted provider yet

## Manual validation

1. Start the service and confirm `http://127.0.0.1:8765/v1/health` returns `{"status":"ready"}`.
2. Pair the extension with the same token as in your `.env` file (`TALKING_PAGE_TOKEN`).
3. Select a paragraph and start a read; confirm playback begins before later chunks finish generating.
4. Open an article page, choose **Read page**, then close the popup while audio continues.
5. Pause, resume, and stop from the popup buttons and from browser media controls.
6. Start a read in another tab and confirm the previous tab's session stops.
7. Refresh the source tab while audio is playing and confirm the session ends.
8. Paste or select more than 10,000 English words and confirm the request is rejected before synthesis.
9. Stop the local service and confirm the popup reports the service as unavailable.
10. To exercise skipped-chunk behavior, temporarily break synthesis for one chunk in a multi-chunk read and confirm later chunks still play.
