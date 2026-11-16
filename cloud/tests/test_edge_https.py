"""Real HTTPS compatibility check using an explicitly trusted temporary test certificate."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'edge'))
from edge_analytics.analytics import Analytics
from edge_analytics.config import load_config
from edge_analytics.storage import EventStore, sync_batch


class HttpsIntegrationTests(unittest.TestCase):
    def test_actual_edge_sync_retry_and_csv_over_verified_https(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)
            cert,key=directory/'test.pem',directory/'test.key'
            subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1',
                            '-keyout',str(key),'-out',str(cert),'-subj','/CN=localhost',
                            '-addext','subjectAltName=IP:127.0.0.1,DNS:localhost',
                            '-addext','basicConstraints=critical,CA:TRUE'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            cloud=directory/'cloud.sqlite3'
            node_token,reader_token=directory/'node.token',directory/'reader.token'
            for command,output,extra in [('provision-node',node_token,['--location','pilot-location','--node','edge-001','--camera','entrance-001']),('provision-reader',reader_token,[])]:
                result=subprocess.run([sys.executable,'-m','cloud_api.cli','--database',str(cloud),command,
                                       '--organization','pilot-organization','--token-file',str(output),*extra],capture_output=True,text=True,check=True)
                self.assertNotIn(output.read_text().strip(),result.stdout+result.stderr)
                self.assertEqual(output.stat().st_mode & 0o777,0o600)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            base=f'https://127.0.0.1:{port}'
            process=subprocess.Popen([sys.executable,'-m','cloud_api.cli','--database',str(cloud),'serve','--port',str(port),
                                      '--ssl-certfile',str(cert),'--ssl-keyfile',str(key)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            store=None
            try:
                # Trust only this test's certificate for this test context; TLS and hostname checks stay enabled.
                with patch.dict(os.environ,{'SSL_CERT_FILE':str(cert)}):
                    for _ in range(100):
                        try:
                            with urllib.request.urlopen(base+'/healthz',timeout=1) as response:self.assertEqual(response.status,200)
                            break
                        except OSError:time.sleep(.1)
                    else:self.fail('HTTPS API did not start')
                    config=load_config(ROOT/'edge/config.example.json')
                    engine=Analytics(config)
                    events=[]
                    for index,y in enumerate([.35,.45,.55,.65,.75,.85,.95]):events.extend(engine.update([[.5,y]],1700000000+index*.2))
                    store=EventStore(directory/'edge.sqlite3')
                    store.add(events)
                    token=node_token.read_text().strip()
                    # Simulate cloud commit with a lost acknowledgement, leaving the local queue pending.
                    request=urllib.request.Request(base+'/v1/events',data=json.dumps({'schema_version':1,'events':events}).encode(),
                                                   headers={'Authorization':f'Bearer {token}','Content-Type':'application/json'})
                    with urllib.request.urlopen(request) as response:self.assertEqual(response.status,200)
                    accepted=sync_batch(store,base+'/v1/events',token)
                    self.assertEqual(accepted,len(events))
                    self.assertEqual(store.pending(),[])
                    self.assertEqual(sync_batch(store,base+'/v1/events',token),0)
                    auth={'Authorization':'Bearer '+reader_token.read_text().strip()}
                    query='?start=1699999900&end=1700003600'
                    with urllib.request.urlopen(urllib.request.Request(base+'/v1/metrics/hourly'+query,headers=auth)) as response:
                        row=json.load(response)['rows'][0]
                    self.assertEqual(row['entries'],1)
                    self.assertEqual(row['exits'],0)
                    self.assertEqual(row['completed_zone_dwell_sessions'],1)
                    with urllib.request.urlopen(urllib.request.Request(base+'/v1/reports/hourly.csv'+query,headers=auth)) as response:
                        self.assertIn('entrance-001',response.read().decode())
            finally:
                if store:store.close()
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait()


if __name__=='__main__':unittest.main()
