# HTML2VNC

A headless HTML/CSS renderer that streams a static frame to a VNC server.

## Features
- Renders static HTML/CSS using headless Chromium (Playwright).
- Zero JavaScript support: JS is disabled at the engine level.
- Implements the RFB 3.8 protocol from scratch.
- Supports dynamic re-rendering when the source HTML file changes on disk.
- Minimalist, high-performance binary stream.

## Tech Stack
- Python 3.11+
- Playwright (Chromium)
- Pillow (Image processing)
- Asyncio (TCP/RFB Server)

## Installation
```bash
pip install playwright pillow
playwright install chromium
```

## Usage
```bash
python3 src/main.py --file index.html --port 5900 --width 1280 --height 720
```

### CLI Flags
- `--file`: Path to the HTML file to render (or `-` for stdin).
- `--port`: Port to listen on for VNC connections (default: 5900).
- `--width`: Framebuffer width in pixels (default: 1280).
- `--height`: Framebuffer height in pixels (default: 720).
