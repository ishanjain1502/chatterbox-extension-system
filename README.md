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

Pick one token and reuse it for both the server and the extension. It must be at least 32 characters:

```powershell
$env:TALKING_PAGE_TOKEN = "talking-page-local-dev-token-32chars-min"
```

### Terminal 1 — start the server

Keep this terminal open while you use the extension:

```powershell
cd E:\Projects\talking-page
.\.venv\Scripts\Activate.ps1
$env:TALKING_PAGE_TOKEN = "talking-page-local-dev-token-32chars-min"
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

## Pair the extension

Open the extension popup and paste the same local token used to start the service. The extension talks only to `http://127.0.0.1:8765`.

## Known MVP limits

- English only
- Built-in Chatterbox-Nano voice only
- One fixed narration speed
- One active browser-wide reading session
- No permanent reading history or audio storage
- Local service is started manually in a terminal
- No custom voice or hosted provider yet

## Manual validation

1. Start the service and confirm `http://127.0.0.1:8765/v1/health` returns `{"status":"ready"}`.
2. Pair the extension with the same `TALKING_PAGE_TOKEN` used by the service.
3. Select a paragraph and start a read; confirm playback begins before later chunks finish generating.
4. Open an article page, choose **Read page**, then close the popup while audio continues.
5. Pause, resume, and stop from the popup buttons and from browser media controls.
6. Start a read in another tab and confirm the previous tab's session stops.
7. Refresh the source tab while audio is playing and confirm the session ends.
8. Paste or select more than 10,000 English words and confirm the request is rejected before synthesis.
9. Stop the local service and confirm the popup reports the service as unavailable.
10. To exercise skipped-chunk behavior, temporarily break synthesis for one chunk in a multi-chunk read and confirm later chunks still play.
