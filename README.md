# HTML2VNC

A headless HTML/CSS renderer that streams a to a VNC server.

## Features
- Renders HTML/CSS using headless Chromium (Playwright).
- Implements the RFB 3.8 protocol from scratch.
- Supports dynamic re-rendering when the source HTML file changes on disk.
- Proactive frame updates: Automatically pushes frame changes to clients.
- Built-in WebSocket proxy for compatibility with web-based VNC clients (like noVNC).
- Minimalist, high-performance binary stream.

## Tech Stack
- Python 3.11+
- Playwright (Chromium)
- Pillow (Image processing)
- Websockets
- Asyncio (TCP/RFB Server)

## Installation
```bash
pip install playwright pillow websockets
playwright install chromium
```

## Usage
```bash
python3 src/main.py --file index.html --port 5900 --ws-port 6080 --width 1280 --height 720
```

### CLI Flags
- `--file`: Path to the HTML file to render (or `-` for stdin).
- `--port`: Port to listen on for VNC connections (default: 5900).
- `--ws-port`: Port to listen on for WebSocket connections (default: 6080).
- `--width`: Framebuffer width in pixels (default: 1280).
- `--height`: Framebuffer height in pixels (default: 720).
- `--no-proactive`: Disable proactive frame updates (defaults to enabled).
- `--send-all-frames`: Send all frames regardless of visual change (requires proactive enabled).


### TODO:
- `Add JavaScript Support`
- `Allow clients to interact with the page`
