import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
import uuid

from fastapi.testclient import TestClient
from cloud_api.app import create_app, MAX_BODY
from cloud_api.database import Database


def event(kind='person_entered', **updates):
    value={'event_id':str(uuid.uuid4()),'type':kind,'timestamp':1700000000.0,
           'organization_id':'org-a','location_id':'site-a','node_id':'node-a','camera_id':'camera-a','details':{'track_id':'local-1'}}
    value.update(updates)
    return value


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'cloud.sqlite3'
        self.db=Database(self.path)
        self.db.provision('org-a','site-a','node-a',['camera-a'],'node-test-a')
        self.db.provision('org-b','site-b','node-b',['camera-b'],'node-test-b')
        self.db.provision('org-a',None,None,[],'reader-test-a','reader')
        self.db.provision('org-b',None,None,[],'reader-test-b','reader')
        self.client=TestClient(create_app(self.path))
        self.headers={'Authorization':'Bearer node-test-a'}
        self.reader={'Authorization':'Bearer reader-test-a'}

    def tearDown(self):
        self.client.close();self.temp.cleanup()

    def post(self,events,headers=None):
        return self.client.post('/v1/events',json={'schema_version':1,'events':events},headers=headers or self.headers)

    def rows(self,headers=None):
        return self.client.get('/v1/metrics/hourly?start=1699999900&end=1700003600',headers=headers or self.reader)

    def test_ingest_retry_and_exact_ack(self):
        e=event()
        for _ in range(2):
            response=self.post([e,e])
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['accepted_event_ids'],[e['event_id']])
        rows=self.rows().json()['rows']
        self.assertEqual(rows[0]['entries'],1)
        self.assertEqual(rows[0]['exits'],0)

    def test_concurrent_duplicate_deliveries(self):
        from concurrent.futures import ThreadPoolExecutor
        value=event()
        identity=self.db.authenticate('node-test-a')
        with ThreadPoolExecutor(max_workers=4) as executor:
            results=list(executor.map(lambda _:self.db.ingest(identity,[value]),range(8)))
        self.assertTrue(all(result==[value['event_id']] for result in results))
        self.assertEqual(self.rows().json()['rows'][0]['entries'],1)

    def test_credential_roles_and_missing_auth(self):
        self.assertEqual(self.client.post('/v1/events',json={}).status_code,401)
        self.assertEqual(self.post([event()],self.reader).status_code,403)
        self.assertEqual(self.rows(self.headers).status_code,403)
        self.assertEqual(self.client.get('/v1/metrics/hourly?start=0&end=10').status_code,401)

    def test_cross_tenant_and_camera_rejected_atomically(self):
        for changes in [{'organization_id':'org-b'},{'location_id':'site-b'},{'node_id':'node-b'},{'camera_id':'unregistered'}]:
            self.assertEqual(self.post([event(),event(**changes)]).status_code,403)
        self.assertEqual(self.rows().json()['rows'],[])

    def test_tenant_read_isolation(self):
        self.post([event()])
        response=self.rows({'Authorization':'Bearer reader-test-b'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['rows'],[])

    def test_conflicting_retry_rolls_back_new_events(self):
        e=event();self.post([e])
        changed=dict(e,type='person_exited')
        self.assertEqual(self.post([event(),changed]).status_code,409)
        self.assertEqual(self.rows().json()['rows'][0]['entries'],1)

    def test_schema_future_and_body_limits(self):
        candidates=[event(timestamp=float(time.time()+1000)),event(event_id='not-uuid'),event(type='video'),
                    event(details={'track_id':'x','image':'not-allowed'}),event(timestamp=True)]
        for e in candidates:self.assertEqual(self.post([e]).status_code,422)
        self.assertEqual(self.post([]).status_code,422)
        self.assertEqual(self.post([event() for _ in range(101)]).status_code,422)
        self.assertEqual(self.client.post('/v1/events',headers=self.headers,json={'schema_version':True,'events':[event()]}).status_code,422)
        self.assertEqual(self.client.post('/v1/events',headers={**self.headers,'Content-Type':'application/json'},content=b'x'*(MAX_BODY+1)).status_code,413)
        self.assertEqual(self.client.post('/v1/events',headers={**self.headers,'Content-Type':'text/plain'},content='{}').status_code,415)
        response=self.client.post('/v1/events',headers={**self.headers,'Content-Type':'application/json'},content=b'{"secret":"do-not-echo"}')
        self.assertNotIn('do-not-echo',response.text)

    def test_dwell_censoring_and_visible_peak(self):
        complete=event('dwell_time_completed',details={'track_id':'x','zone_id':'z','duration_seconds':12.,'censored':False,'completion':'zone_exit'})
        censored=event('dwell_time_completed',details={'track_id':'y','zone_id':'z','duration_seconds':99.,'censored':True,'completion':'track_lost'})
        snapshot=event('occupancy_snapshot',details={'visible_persons':3,'zones':{'z':2},'scope':'camera_visible_only'})
        self.assertEqual(self.post([complete,censored,snapshot]).status_code,200)
        row=self.rows().json()['rows'][0]
        self.assertEqual(row['completed_zone_dwell_sessions'],1)
        self.assertEqual(row['completed_zone_dwell_seconds'],12.)
        self.assertEqual(row['peak_visible_persons'],3)
        complete['details']['censored']=True
        self.assertEqual(self.post([complete]).status_code,422)

    def test_exclusive_end_and_max_range(self):
        e=event();self.post([e])
        result=self.client.get('/v1/metrics/hourly?start=1699999900&end=1700000000',headers=self.reader)
        self.assertEqual(result.json()['rows'],[])
        self.assertEqual(self.client.get('/v1/metrics/hourly?start=0&end=99999999',headers=self.reader).status_code,422)

    def test_persistence_and_revocation(self):
        self.post([event()])
        other=TestClient(create_app(self.path))
        try:self.assertEqual(other.get('/v1/metrics/hourly?start=1699999900&end=1700003600',headers=self.reader).json()['rows'][0]['entries'],1)
        finally:other.close()
        connection=self.db.connect()
        try:
            with connection:connection.execute('UPDATE credentials SET revoked=1 WHERE role="ingest"')
        finally:connection.close()
        self.assertEqual(self.post([event()]).status_code,401)

    def test_csv_and_health(self):
        self.post([event()])
        response=self.client.get('/v1/reports/hourly.csv?start=1699999900&end=1700003600',headers=self.reader)
        self.assertEqual(response.status_code,200)
        self.assertIn('camera-a',response.text)
        self.assertTrue(response.headers['content-type'].startswith('text/csv'))
        self.assertEqual(self.client.get('/healthz').json(),{'status':'ok'})


if __name__=='__main__':unittest.main()
