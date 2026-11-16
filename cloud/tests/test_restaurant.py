from pathlib import Path
import tempfile
import unittest
import uuid
from fastapi.testclient import TestClient
from cloud_api.app import create_app
from cloud_api.database import Database


class RestaurantTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=Database(Path(self.temp.name)/'cloud.sqlite3')
        self.db.provision('a','site','node',['camera'],'test-node')
        self.db.provision('a',None,None,[],'test-reader','reader')
        self.db.provision('b','other-site','other-node',['other-camera'],'test-other-node')
        self.client=TestClient(create_app(self.db.path))
        self.headers={'Authorization':'Bearer test-reader'}

    def tearDown(self):self.client.close();self.temp.cleanup()

    def event(self,kind,details,**extra):
        return dict(event_id=str(uuid.uuid4()),type=kind,timestamp=1700000000.,organization_id='a',location_id='site',node_id='node',camera_id='camera',details=details,**extra)

    def get(self,query=''):
        return self.client.get('/v1/metrics/zones?start=1699999900&end=1700003600'+query,headers=self.headers)

    def test_zone_sessions_snapshots_and_capability_labels(self):
        events=[]
        for seconds in [120.,300.]:events.append(self.event('dwell_time_completed',{'track_id':'x','zone_id':'Zone1','duration_seconds':seconds,'completion':'zone_exit','censored':False}))
        events.append(self.event('dwell_time_completed',{'track_id':'x','zone_id':'Zone1','duration_seconds':99.,'completion':'track_lost','censored':True}))
        events.append(self.event('occupancy_snapshot',{'visible_persons':5,'zones':{'Zone1':4,'Zone2':2},'scope':'camera_visible_only'}))
        response=self.client.post('/v1/events',json={'schema_version':1,'events':events},headers={'Authorization':'Bearer test-node'})
        self.assertEqual(response.status_code,200,response.text)
        result=self.get().json();rows={row['zone_id']:row for row in result['rows']}
        self.assertEqual(rows['Zone1']['completed_sessions'],2)
        self.assertEqual(rows['Zone1']['observed_dwell_seconds'],420.)
        self.assertEqual(rows['Zone1']['interrupted_sessions'],1)
        self.assertEqual(rows['Zone1']['peak_visible_persons'],4)
        self.assertEqual(rows['Zone2']['completed_sessions'],0)
        self.assertEqual(rows['Zone2']['peak_visible_persons'],2)
        self.assertEqual(result['measurement'],'observed_person_tracks')
        self.assertFalse(any(result['capabilities'].values()))

    def test_scope_filters_and_no_false_zero_sessions(self):
        event=self.event('zone_crossed',{'track_id':'x','zone_id':'Zone1','direction':'entered'})
        self.db.ingest(self.db.authenticate('test-node'),[event])
        foreign=dict(event,event_id=str(uuid.uuid4()),organization_id='b',location_id='other-site',node_id='other-node',camera_id='other-camera',details={'track_id':'y','zone_id':'private-zone','direction':'entered'})
        self.db.ingest(self.db.authenticate('test-other-node'),[foreign])
        self.assertEqual([r['zone_id'] for r in self.get().json()['rows']],['Zone1'])
        self.assertEqual(self.get('&camera_id=unknown').json()['rows'],[])
        self.assertEqual(self.get('&node_id=other-node').json()['rows'],[])
        self.assertEqual(self.get('&location_id=other-site').json()['rows'],[])
        row=self.get().json()['rows'][0]
        self.assertEqual(row['completed_sessions'],0)
        self.assertIsNone(row['peak_visible_persons'])

    def test_auth_and_range_validation(self):
        self.assertEqual(self.client.get('/v1/metrics/zones?start=0&end=10').status_code,401)
        self.assertEqual(self.client.get('/v1/metrics/zones?start=0&end=10',headers={'Authorization':'Bearer test-node'}).status_code,403)
        self.assertEqual(self.client.get('/v1/metrics/zones?start=0&end=99999999',headers=self.headers).status_code,422)
        self.assertEqual(self.client.get('/v1/metrics/zones?start=10&end=1',headers=self.headers).status_code,422)


if __name__=='__main__':unittest.main()
