import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from edge_analytics.heartbeat import configuration_proof, send_heartbeat
import hashlib


class HeartbeatTests(unittest.TestCase):
    def setUp(self):
        self.config={'organization_id':'org','location_id':'loc','node_id':'node','camera_id':'cam'}

    def test_configuration_hash_confirms_exact_file_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'config.json';value={**self.config,'sample_fps':5}
            digest=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            value['deployment']={'calibration_version':3,'configuration_sha256':digest};path.write_text(json.dumps(value))
            self.assertEqual(configuration_proof(path),(3,digest))
            value['sample_fps']=6;path.write_text(json.dumps(value))
            self.assertEqual(configuration_proof(path),(None,None))

    @patch('edge_analytics.heartbeat.urllib.request.urlopen')
    def test_missing_stale_or_wrong_camera_file_cannot_claim_processing(self,open):
        open.return_value.__enter__.return_value.read.return_value=b'{"received_at":1}'
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'health.json'
            for value in [None,{'updated_at':0,'identity':self.config,'state':'processing','last_frame_at':time.time()},
                          {'updated_at':time.time(),'identity':dict(self.config,camera_id='wrong'),'state':'processing','last_frame_at':time.time()}]:
                if value is not None:path.write_text(json.dumps(value))
                send_heartbeat(self.config,'https://api.example/v1/events','test-token',path)
                camera=json.loads(open.call_args[0][0].data)['cameras'][0]
                self.assertEqual(camera['state'],'unknown');self.assertIsNone(camera['last_frame_at'])

    @patch('edge_analytics.heartbeat.urllib.request.urlopen')
    def test_fresh_worker_health_sent_only_for_matching_identity(self,open):
        open.return_value.__enter__.return_value.read.return_value=b'{"received_at":1}'
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'health.json';path.write_text(json.dumps({'identity':self.config,'updated_at':time.time(),'state':'processing','last_frame_at':time.time(),'applied_version':2,'configuration_sha256':'a'*64}))
            send_heartbeat(self.config,'https://api.example/v1/events','test-token',path)
            request=open.call_args[0][0]
            self.assertEqual(request.full_url,'https://api.example/v1/heartbeat')
            self.assertEqual(json.loads(request.data)['cameras'][0]['applied_version'],2)
        with self.assertRaises(ValueError):send_heartbeat(self.config,'http://api.example/v1/events','test-token')


if __name__=='__main__':unittest.main()
