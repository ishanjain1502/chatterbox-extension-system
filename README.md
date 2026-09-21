# Talking Page

Talking Page is a local, English-only Chrome reader. It turns selected text or an extracted article into speech using Chatterbox-Nano on this computer.

## Prerequisites

- Windows with current Google Chrome
- Python 3.11
- Internet access for the one-time Chatterbox model download

## Install the local service

Use **CPython 3.11** from [python.org](https://www.python.org/downloads/release/python-3119/) or `winget install Python.Python.3.11`. Do not use the MSYS/Git Bash `python` shim; it is not the same runtime and does not ship with `pip`.

From `server`, create the virtual environment and install dependencies:

```powershell
cd server
.\setup-venv.ps1
```

On Git Bash after installing CPython 3.11:

```bash
cd server
./setup-venv.sh
```

Activate the environment before starting the service:

```powershell
.\server\.venv\Scripts\Activate.ps1
```

## Start the local service

Set a private token of at least 32 characters in `TALKING_PAGE_TOKEN`, then start the server from a terminal. The MVP keeps the service separate from Chrome; an automatic launcher is deferred.

## Load the extension

Open `chrome://extensions`, enable Developer mode, choose **Load unpacked**, and select the `extension` folder.

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

1. Start the service and confirm its health endpoint returns `ready`.
2. Pair the extension and read a selected paragraph.
3. Read an article page, then close the popup while audio continues.
4. Pause, resume, and stop with browser media controls.
5. Start a read in another tab and confirm the old one stops.
6. Refresh the source tab and confirm its session ends.
7. Confirm text over 10,000 words is rejected.
