import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from edge_analytics.panel import Controller, PanelServer, Conflict
from edge_analytics.config import load_config


class PanelTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'config.local.json'
        self.config = json.loads((Path(__file__).resolve().parents[1] / 'config.example.json').read_text())
        self.controller = Controller(self.path)
        self.server = PanelServer(0, self.controller)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.controller.close()
        self.directory.cleanup()

    def request(self, path, value=None, token=True, origin=None, host=None):
        headers = {}
        if value is not None:
            headers = {'Content-Type':'application/json', 'Origin':origin or self.server.origin}
            if token: headers['X-Panel-Token'] = self.controller.token
        if host: headers['Host'] = host
        request = urllib.request.Request(self.server.origin + path, headers=headers,
                                         data=json.dumps(value).encode() if value is not None else None)
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    def test_save_reload_and_fixed_database(self):
        self.config['database']='/tmp/not-allowed.sqlite3'
        code, _ = self.request('/api/config', self.config)
        self.assertEqual(code, 200)
        self.assertEqual(load_config(self.path)['database'], str(self.path.parent / 'events.sqlite3'))
        code, body = self.request('/api/bootstrap')
        self.assertEqual(json.loads(body)['config']['camera_id'], self.config['camera_id'])

    def test_invalid_save_preserves_existing(self):
        self.controller.save(self.config)
        before = self.path.read_bytes()
        self.assertEqual(self.request('/api/config', {'line':None})[0], 400)
        self.assertEqual(self.path.read_bytes(), before)

    def test_browser_origin_token_and_host(self):
        self.assertEqual(self.request('/api/start', {}, token=False)[0], 403)
        self.assertEqual(self.request('/api/stop', {}, origin='https://other.example')[0], 403)
        self.assertEqual(self.request('/api/status', host='attacker.example')[0], 403)
        self.assertEqual(self.request('/api/config', self.config, origin='null')[0], 403)
        self.assertEqual(self.request('/../config.local.json')[0], 404)
        self.assertFalse(self.path.exists())

    def test_invalid_existing_file_can_be_recovered_without_overwrite(self):
        self.path.write_text('{invalid')
        code, body = self.request('/api/bootstrap')
        self.assertEqual(code, 200)
        self.assertIsNone(json.loads(body)['config'])
        self.assertTrue(json.loads(body)['warning'])
        self.assertEqual(self.path.read_text(), '{invalid')
        self.assertEqual(self.request('/api/config', self.config)[0], 200)

    def test_no_source_cannot_start(self):
        self.controller.save(self.config)
        with patch.dict(os.environ, {'EDGE_RTSP_URL': ''}):
            self.assertEqual(self.request('/api/start', {})[0], 400)
            state=json.loads(self.request('/api/status')[1])
            self.assertFalse(state['running'])
            self.assertFalse(state['source_configured'])

    def test_assets_served_with_panel_integration(self):
        code, body=self.request('/')
        self.assertEqual(code,200)
        self.assertIn(b'/panel.js',body)
        self.assertEqual(self.request('/app.js')[0],200)
        self.assertEqual(self.request('/panel.js')[0],200)

    def test_real_worker_frames_stop_and_save_guard(self):
        import cv2
        import numpy as np
        video = self.path.parent / 'test.avi'
        writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'MJPG'),10,(320,240))
        self.assertTrue(writer.isOpened())
        for _ in range(800):writer.write(np.zeros((240,320,3),dtype=np.uint8))
        writer.release()
        self.controller.video=str(video)
        self.controller.save(self.config)
        self.assertEqual(self.request('/api/start',{})[0],200)
        self.assertEqual(self.request('/api/start',{})[0],409)
        self.assertEqual(self.request('/api/config',self.config)[0],409)
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            state=json.loads(self.request('/api/status')[1])
            if state['processed_frames']>0:break
            time.sleep(.1)
        self.assertGreater(state['processed_frames'],0,state)
        self.assertEqual(self.request('/api/stop',{})[0],200)
        state=json.loads(self.request('/api/status')[1])
        self.assertFalse(state['running'])
        self.assertEqual(state['state'],'stopped')
        self.assertGreater(state['pending_events'],0)
        self.assertEqual(self.request('/api/stop',{})[0],200)
        self.assertEqual(self.request('/api/config',self.config)[0],200)


if __name__ == '__main__': unittest.main()
