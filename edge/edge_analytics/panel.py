"""Loopback-only installer panel; one managed worker, no LAN-facing admin API."""
import argparse
import hmac
import json
import os
from pathlib import Path
import secrets
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from .config import load_config


class Conflict(Exception):
    pass


class Controller:
    def __init__(self, config_path, video=None):
        self.path = Path(config_path).resolve()
        self.video = str(Path(video).resolve()) if video else None
        self.lock = threading.RLock()
        self.process = None
        self.last_exit = None
        self.health_dir = tempfile.TemporaryDirectory(prefix='ai-camera-health-')
        self.health = Path(self.health_dir.name) / 'worker.json'
        self.token = secrets.token_urlsafe(32)

    def _running(self):
        if self.process is not None and self.process.poll() is not None:
            self.last_exit = self.process.returncode
            self.process = None
        return self.process is not None

    def config(self):
        with self.lock:
            if not self.path.exists():
                return None
            return json.loads(self.path.read_text())

    def save(self, value):
        with self.lock:
            if self._running():
                raise Conflict('Ndalo analizën përpara se të ndryshosh konfigurimin.')
            if not isinstance(value, dict):
                raise ValueError('Konfigurimi duhet të jetë objekt JSON.')
            # Panel-managed files cannot direct the worker to arbitrary database paths.
            candidate = dict(value, database='events.sqlite3')
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', dir=self.path.parent, suffix='.json', delete=False) as output:
                    temporary = Path(output.name)
                    json.dump(candidate, output, allow_nan=False, indent=2)
                    output.flush()
                    os.fsync(output.fileno())
                load_config(temporary)
                os.replace(temporary, self.path)
            finally:
                if temporary and temporary.exists():
                    temporary.unlink()
            return candidate

    def start(self):
        with self.lock:
            if self._running():
                raise Conflict('Analiza është tashmë në punë.')
            config = load_config(self.path)
            expected = (self.path.parent / 'events.sqlite3').resolve()
            if Path(config['database']) != expected:
                raise ValueError('Ruaj konfigurimin nga paneli përpara nisjes.')
            if self.video:
                if not Path(self.video).is_file():
                    raise ValueError('Videoja e provës nuk ekziston.')
            elif not os.environ.get('EDGE_RTSP_URL', '').startswith(('rtsp://', 'rtsps://')):
                raise ValueError('Adresa e kamerës nuk është konfiguruar në pajisje (EDGE_RTSP_URL).')
            self.health.unlink(missing_ok=True)
            command = [sys.executable, '-m', 'edge_analytics.cli', '--config', str(self.path), 'run', '--health-file', str(self.health)]
            if self.video:
                command.extend(['--video', self.video])
            # Do not expose native logs or credential-bearing URLs to the browser.
            self.process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.last_exit = None

    def stop(self):
        with self.lock:
            if self._running():
                self.process.terminate()
                try:
                    self.process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
                self.last_exit = self.process.returncode
                self.process = None

    def status(self):
        with self.lock:
            running = self._running()
            try:
                health = json.loads(self.health.read_text())
            except (OSError, ValueError):
                health = {}
            updated = health.get('updated_at', 0)
            fresh = time.time() - updated < 15
            state = health.get('state') if running and fresh else ('starting' if running else 'stopped')
            if running and not fresh and updated:
                state = 'unresponsive'
            pending = None
            database = self.path.parent / 'events.sqlite3'
            if database.is_file():
                try:
                    connection = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=1)
                    try:
                        pending = connection.execute('SELECT count(*) FROM events WHERE synced=0').fetchone()[0]
                    finally:
                        connection.close()
                except sqlite3.Error:
                    pass
            return {'running': running, 'state': state, 'last_exit': self.last_exit,
                    'source_configured': bool(self.video or os.environ.get('EDGE_RTSP_URL', '').startswith(('rtsp://', 'rtsps://'))),
                    'source_type': 'video' if self.video else 'camera',
                    'processed_frames': health.get('processed_frames', 0),
                    'last_frame_at': health.get('last_frame_at'), 'pending_events': pending,
                    'saved': self.path.is_file()}

    def close(self):
        self.stop()
        self.health_dir.cleanup()


def asset_directory():
    development = Path(__file__).resolve().parents[1] / 'calibration'
    if development.is_dir():
        return development
    return Path(sys.prefix) / 'share' / 'ai-camera-edge' / 'calibration'


class PanelServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port, controller):
        super().__init__(('127.0.0.1', port), Handler)
        self.controller = controller
        self.origin = f'http://127.0.0.1:{self.server_port}'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, code, payload, content_type='application/json'):
        data = json.dumps(payload, allow_nan=False).encode() if content_type == 'application/json' else payload
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(data)

    def trusted_host(self):
        return self.headers.get('Host') == urlsplit(self.server.origin).netloc

    def do_GET(self):
        if not self.trusted_host():
            return self.reply(403, {'error': 'Host i palejuar.'})
        path = urlsplit(self.path).path
        if path == '/api/bootstrap':
            warning = None
            try:
                value = self.server.controller.config()
                if value is not None:
                    load_config(self.server.controller.path)
            except (OSError, ValueError, TypeError, KeyError):
                value = None
                warning = 'Konfigurimi ekzistues është i pavlefshëm. Importo një skedar të saktë ose plotëso fushat para ruajtjes.'
            return self.reply(200, {'token': self.server.controller.token, 'config': value, 'warning': warning})
        if path == '/api/status':
            return self.reply(200, self.server.controller.status())
        assets = {'/': ('index.html', 'text/html; charset=utf-8'), '/styles.css': ('styles.css', 'text/css; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/calibration.js': ('calibration.js', 'text/javascript; charset=utf-8'), '/panel.js': ('panel.js', 'text/javascript; charset=utf-8')}
        if path not in assets:
            return self.reply(404, {'error': 'Nuk u gjet.'})
        name, content_type = assets[path]
        data = (asset_directory() / name).read_bytes()
        if path == '/':
            data = data.replace(b'href="../../index.html"', b'href="/"')
            data = data.replace(b'</head>', b'<script src="/panel.js" defer></script></head>')
            data = data.replace('Paneli nuk ndryshon kamerën dhe nuk nis analizën.'.encode(), 'Shkarkimi i JSON-it nuk nis analizën. Përdor kontrollet e pajisjes sipër.'.encode())
        return self.reply(200, data, content_type)

    def do_POST(self):
        if not self.trusted_host() or self.headers.get('Origin') != self.server.origin:
            return self.reply(403, {'error': 'Origjinë e palejuar.'})
        if not hmac.compare_digest(self.headers.get('X-Panel-Token', ''), self.server.controller.token):
            return self.reply(403, {'error': 'Sesioni nuk është i vlefshëm. Rifresko panelin.'})
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.reply(415, {'error': 'Kërkohet application/json.'})
        try:
            size = int(self.headers.get('Content-Length', '-1'))
            if size < 0 or size > 1024 * 1024:
                return self.reply(413, {'error': 'Kërkesa është tepër e madhe.'})
            value = json.loads(self.rfile.read(size))
            path = urlsplit(self.path).path
            if path == '/api/config':
                self.server.controller.save(value)
            elif path == '/api/start':
                self.server.controller.start()
            elif path == '/api/stop':
                self.server.controller.stop()
            else:
                return self.reply(404, {'error': 'Nuk u gjet.'})
            self.reply(200, self.server.controller.status())
        except Conflict as error:
            self.reply(409, {'error': str(error)})
        except (ValueError, KeyError, TypeError, OSError):
            self.reply(400, {'error': 'Konfigurimi ose burimi i videos nuk është i vlefshëm. Kontrollo fushat dhe konfigurimin e pajisjes.'})


def main():
    parser = argparse.ArgumentParser(description='Local edge calibration and process control')
    parser.add_argument('--config', required=True, help='Managed configuration file (database fixed alongside it)')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--video', help='Optional local test video; otherwise use EDGE_RTSP_URL from environment')
    args = parser.parse_args()
    controller = Controller(args.config, args.video)
    server = PanelServer(args.port, controller)
    # A second server cannot manage the same worker/database directory.
    lock_file = None
    try:
        if os.name != 'posix':
            raise RuntimeError('Local process-control panel currently requires Linux/macOS.')
        import fcntl
        controller.path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = (controller.path.parent / '.panel.lock').open('a')
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another panel is already managing this directory.') from None
        def shutdown(*_):
            threading.Thread(target=server.shutdown, daemon=True).start()
        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)
        print(f'Paneli lokal: {server.origin}', flush=True)
        server.serve_forever()
    finally:
        server.server_close()
        controller.close()
        if lock_file:
            lock_file.close()


if __name__ == '__main__':
    main()
