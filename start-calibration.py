"""Serve the local calibration UI with standard Python only; no media uploads."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from urllib.parse import urlsplit
import webbrowser


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if urlsplit(self.path).path not in ('/','/index.html','/app.js','/calibration.js','/styles.css'):
            self.send_error(404);return
        super().do_GET()

    def end_headers(self):
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        super().end_headers()

    def log_message(self,*_):pass


def main():
    parser=argparse.ArgumentParser(description='Open local camera calibration')
    parser.add_argument('--port',type=int,default=8766)
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parent/'edge/calibration'
    try:server=ThreadingHTTPServer(('127.0.0.1',args.port),partial(Handler,directory=str(root)))
    except OSError:raise SystemExit('Port is busy. Close the old calibration window or use --port 8767.') from None
    url=f'http://127.0.0.1:{server.server_port}'
    print(f'Camera calibration on this PC: {url}\nKeep this window open. Ctrl+C stops the local server.\nImages and videos remain in the browser; this server has no upload API.',flush=True)
    if not args.no_browser:threading.Timer(.3,lambda:webbrowser.open(url)).start()
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
