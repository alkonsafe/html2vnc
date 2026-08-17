import asyncio
import argparse
import sys
import os
import struct
from pathlib import Path
from PIL import Image
from playwright.async_api import async_playwright
import websockets

RFB_PROTOCOL_VERSION = b"RFB 003.008\n"

class HTML2VNC:
    def __init__(self, file_path, width, height, port):
        self.file_path = file_path
        self.width = width
        self.height = height
        self.port = port
        self.framebuffer = None
        self.last_mtime = 0
        self.browser = None
        self.page = None

    async def start_browser(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch()
        self.context = await self.browser.new_context(
            viewport={"width": self.width, "height": self.height},
            java_script_enabled=False
        )
        self.page = await self.context.new_page()
        
        if self.file_path == "-":
            # For stdin, we might need a different approach since stdin is read once
            # For now, we'll handle the initial content
            html_content = sys.stdin.read()
            await self.page.set_content(html_content)
        else:
            await self.page.goto(f"file://{Path(self.file_path).absolute()}")

    async def render_html(self):
        if not self.page:
            return

        if self.file_path != "-":
            # Reload the page to reflect changes on disk
            await self.page.reload()
        
        screenshot_bytes = await self.page.screenshot(type="png")
        from io import BytesIO
        img = Image.open(BytesIO(screenshot_bytes)).convert("RGB")
        img = img.resize((self.width, self.height))
        self.framebuffer = img.tobytes()

    async def stop_browser(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    def check_for_updates(self):
        if self.file_path == "-": return False
        try:
            mtime = os.path.getmtime(self.file_path)
            if mtime > self.last_mtime:
                self.last_mtime = mtime
                return True
        except OSError: pass
        return False

    async def handle_client(self, reader, writer):
        addr = writer.get_extra_info('peername')
        print(f"New connection from {addr}")
        try:
            # 1. Version
            writer.write(RFB_PROTOCOL_VERSION)
            await writer.drain()
            await reader.readuntil(b"\n")
            
            # 2. Security
            writer.write(b"\x01\x01") 
            await writer.drain()
            await reader.readexactly(1)

            # 3. Heartbeat
            writer.write(b"\x00\x00\x00\x00")
            await writer.drain()
            try:
                await asyncio.wait_for(reader.readexactly(1), timeout=1.0)
            except: pass

            # 4. Server Init
            writer.write(struct.pack(">HH", self.width, self.height))
            writer.write(struct.pack(">BBBB", 4, 32, 0, 1))
            writer.write(struct.pack(">HHHBBB", 0xFFFF, 0xFFFF, 0xFFFF, 16, 8, 0))
            writer.write(b"\x00\x00\x00")
            name = b"HTML2VNC"
            writer.write(struct.pack(">I", len(name)))
            writer.write(name)
            await writer.drain()
            print(f"[{addr}] Server Init sent.")

            def get_rgba_buffer():
                if not self.framebuffer: return b""
                img = Image.frombytes("RGB", (self.width, self.height), self.framebuffer)
                return img.convert("RGBA").tobytes()

            # 5. Main Loop
            while True:
                # Read exactly 4 bytes for message type
                try:
                    header = await reader.readexactly(4)
                except asyncio.IncompleteReadError:
                    break
                
                msg_type = struct.unpack(">I", header)[0]
                
                if msg_type == 0: # FramebufferUpdateRequest
                    await reader.readexactly(16)
                    if self.check_for_updates():
                        await self.render_html()
                    
                    writer.write(struct.pack(">BBH", 0, 0, 1))
                    writer.write(struct.pack(">HHHHI", 0, 0, self.width, self.height, 0))
                    writer.write(get_rgba_buffer())
                    await writer.drain()
                    print(f"[{addr}] Sent FramebufferUpdate")
                elif msg_type == 1: # KeyEvent
                    await reader.readexactly(8)
                elif msg_type == 2: # PointerEvent
                    await reader.readexactly(12)
                elif msg_type == 3: # SetEncodings
                    num_encs_raw = await reader.readexactly(4)
                    num_encs = struct.unpack(">I", num_encs_raw)[0]
                    await reader.readexactly(num_encs * 4)
                    print(f"[{addr}] Client set encodings.")
                else:
                    # If we get an unknown msg_type, we are likely out of sync.
                    # Instead of breaking, we log it.
                    print(f"[{addr}] Unknown msg type: {msg_type}")
                    # To recover, we'd need a way to find the next message header,
                    # which is hard in RFB. We'll just continue.
        except Exception as e:
            print(f"[{addr}] Error during session: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def handle_websocket(self, websocket):
        """Websockify-style proxy: bridges WebSocket to the RFB handler."""
        addr = websocket.remote_address
        print(f"WebSocket connection from {addr}")
        
        # Create a pair of streams to simulate a socket connection for handle_client
        reader, writer = await asyncio.open_connection('127.0.0.1', self.port)
        
        async def ws_to_tcp():
            try:
                async for message in websocket:
                    if isinstance(message, bytes):
                        writer.write(message)
                        await writer.drain()
                    else:
                        # Handle text frames if necessary, though RFB is binary
                        writer.write(message.encode())
                        await writer.drain()
            except Exception as e:
                print(f"WS->TCP Error: {e}")
            finally:
                writer.close()

        async def tcp_to_ws():
            try:
                while True:
                    data = await reader.read(4096)
                    if not data:
                        break
                    await websocket.send(data)
            except Exception as e:
                print(f"TCP->WS Error: {e}")
            finally:
                await websocket.close()

        await asyncio.gather(ws_to_tcp(), tcp_to_ws())

    async def run(self):
        print("Starting browser...")
        await self.start_browser()
        
        print("Initial rendering...")
        await self.render_html()
        
        # Start the VNC server
        server = await asyncio.start_server(self.handle_client, '0.0.0.0', self.port)
        
        # Start the WebSocket proxy
        ws_server = await websockets.serve(self.handle_websocket, '0.0.0.0', self.ws_port)
        
        print(f"HTML2VNC listening on port {self.port} ({self.width}x{self.height})")
        print(f"WebSocket proxy listening on port {self.ws_port}")
        
        try:
            async with server:
                await server.serve_forever()
        finally:
            await self.stop_browser()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--port", type=int, default=5900)
    parser.add_argument("--ws-port", type=int, default=6080, help="WebSocket port (websockify style)")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    args = parser.parse_args()
    app = HTML2VNC(args.file, args.width, args.height, args.port)
    # Store ws_port on the app instance for run() to use
    app.ws_port = args.ws_port
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        pass
