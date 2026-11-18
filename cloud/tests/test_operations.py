import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from cloud_api import accounts, operations
from cloud_api.app import create_app
from cloud_api.database import Database

ROOT=Path(__file__).resolve().parents[2]


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'cloud.sqlite3'
        self.db=Database(self.path);accounts.initialize(self.db);operations.initialize(self.db)
        accounts.create_owner(self.db,operations.SYSTEM_ORG,'admin@example.com','test-admin-password','admin')
        accounts.create_owner(self.db,operations.SYSTEM_ORG,'tech@example.com','test-technician-password','technician')
        accounts.create_owner(self.db,'a','owner@example.com','test-owner-password')
        self.db.provision('a','site','node',['cam'],'test-node')
        self.db.provision('b','private-site','private-node',['private-cam'],'test-node-b')
        self.client=TestClient(create_app(self.path),base_url='https://testserver')
        self.headers={'Origin':'https://testserver'}
        self.query='?organization_id=a&location_id=site&node_id=node&camera_id=cam'
        self.login('admin@example.com','test-admin-password')

    def tearDown(self):self.client.close();self.temp.cleanup()

    def login(self,email,password):
        self.client.cookies.clear()
        result=self.client.post('/auth/login',headers=self.headers,json={'email':email,'password':password})
        self.assertEqual(result.status_code,204,result.text)

    def post(self,path,value):return self.client.post(path,headers=self.headers,json=value)

    def config(self):
        value=json.loads((ROOT/'edge/config.example.json').read_text())
        value.update(organization_id='a',location_id='site',node_id='node',camera_id='cam')
        return value

    def test_installer_uses_utf8_on_windows(self):
        original_read_text = Path.read_text

        def windows_read_text(path, encoding=None, errors=None):
            return original_read_text(path, encoding=encoding or 'cp1252', errors=errors)

        with patch.object(Path, 'read_text', windows_read_text):
            page = self.client.get('/installer/' + self.query)
            context = self.client.get('/v1/installations/context' + self.query)
        self.assertEqual(page.status_code, 200)
        self.assertIn('/admin-assets/installer.js', page.text)
        self.assertIn('Kalibr', page.text)
        self.assertEqual(context.status_code, 200)

    def test_create_registry_and_scope_technician(self):
        self.assertEqual(self.post('/v1/admin/businesses',{'id':'restaurant','name':'Restoranti'}).status_code,200)
        self.assertEqual(self.post('/v1/admin/locations',{'organization_id':'restaurant','id':'durres','name':'Durrës'}).status_code,200)
        self.assertEqual(self.post('/v1/admin/nodes',{'organization_id':'restaurant','location_id':'durres','id':'pc'}).status_code,200)
        self.assertEqual(self.post('/v1/admin/cameras',{'organization_id':'restaurant','location_id':'durres','node_id':'pc','id':'door'}).status_code,200)
        self.assertEqual(self.post('/v1/admin/assignments',{'email':'tech@example.com','organization_id':'a','location_id':'site'}).status_code,200)
        self.login('tech@example.com','test-technician-password')
        overview=self.client.get('/v1/operations').json()
        self.assertEqual([b['id'] for b in overview['businesses']],['a'])
        self.assertEqual([c['id'] for c in overview['cameras']],['cam'])
        self.assertEqual(overview['audit'],[])
        self.assertEqual(self.client.get('/v1/installations/context'+self.query).status_code,200)
        self.assertEqual(self.client.get('/v1/installations/context?organization_id=b&location_id=private-site&node_id=private-node&camera_id=private-cam').status_code,403)
        self.assertEqual(self.post('/v1/admin/businesses',{'id':'x','name':'x'}).status_code,403)

    def test_owner_cannot_admin_and_post_requires_origin(self):
        self.assertEqual(self.client.post('/v1/admin/businesses',json={'id':'x','name':'x'}).status_code,403)
        self.login('owner@example.com','test-owner-password')
        self.assertEqual(self.client.get('/v1/operations').status_code,403)
        self.assertEqual(self.client.get('/installer/').status_code,403)
        self.assertEqual(self.client.get('/v1/installations/context'+self.query).status_code,403)
        self.assertEqual(self.post('/v1/admin/accounts',{'role':'technician','email':'new@example.com','password':'good-test-password'}).status_code,403)

    def test_account_creation_audit_redacts_password(self):
        password='a-new-test-password'
        response=self.post('/v1/admin/accounts',{'role':'technician','email':'new@example.com','password':password})
        self.assertEqual(response.status_code,200,response.text)
        self.assertNotIn(password,self.client.get('/v1/operations').text)
        self.assertEqual(self.post('/v1/admin/accounts',{'role':'admin','email':'bad@example.com','password':password}).status_code,422)
        invalid=self.post('/v1/admin/accounts',{'role':'owner','email':'bad@example.com','password':'short','organization_id':'a'})
        self.assertNotIn('short',invalid.text)

    def test_calibration_versions_identity_activation_and_proof(self):
        config=self.config()
        first=self.post('/v1/installations/calibrations'+self.query,{'config':config,'expected_version':0,'status':'draft'})
        self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(first.json()['version'],1)
        self.assertEqual(self.post('/v1/admin/activate'+self.query,{'version':1}).status_code,409)
        self.assertEqual(self.post('/v1/installations/calibrations'+self.query,{'config':config,'expected_version':0}).status_code,409)
        forged=dict(config,organization_id='b')
        self.assertEqual(self.post('/v1/installations/calibrations'+self.query,{'config':forged,'expected_version':1}).status_code,422)
        config['calibration']={'schema_version':1,'source':{'kind':'image','width':640,'height':360},'fixed_view_confirmed':True,'role_samples':[],
          'capabilities':{'uniform_classifier_active':False,'table_service_active':False},'review':{'status':'manual_review'}}
        second=self.post('/v1/installations/calibrations'+self.query,{'config':config,'expected_version':1,'status':'manual_review'})
        self.assertEqual(second.status_code,200,second.text)
        self.assertEqual(self.post('/v1/admin/activate'+self.query,{'version':2}).status_code,200)
        output=self.client.get('/v1/installations/config'+self.query)
        self.assertEqual(output.status_code,200)
        downloaded=output.json()
        self.assertEqual(downloaded['deployment']['configuration_sha256'],operations.digest(downloaded))
        camera=self.client.get('/v1/operations').json()['cameras'][0]
        self.assertIsNone(camera['applied_version'])
        with tempfile.TemporaryDirectory() as temp:
            import sys
            sys.path.insert(0,str(ROOT/'edge'))
            from edge_analytics.config import load_config
            from edge_analytics.heartbeat import configuration_proof
            file=Path(temp)/'config.json';file.write_text(json.dumps(downloaded))
            load_config(file)
            self.assertEqual(configuration_proof(file),(2,second.json()['sha256']))
        node_headers={'Authorization':'Bearer test-node'}
        heartbeat={'schema_version':1,'cameras':[{'camera_id':'cam','state':'processing','last_frame_at':time.time(),'applied_version':2,'configuration_sha256':second.json()['sha256']}]}
        self.assertEqual(self.client.post('/v1/heartbeat',json=heartbeat,headers=node_headers).status_code,200)
        rows=self.client.get('/v1/operations').json()
        node=next(n for n in rows['nodes'] if n['organization_id']=='a')
        camera=next(c for c in rows['cameras'] if c['organization_id']=='a')
        self.assertTrue(node['online']);self.assertEqual(camera['camera_status'],'processing');self.assertEqual(camera['applied_version'],2)
        heartbeat['cameras'][0]['configuration_sha256']='0'*64
        self.client.post('/v1/heartbeat',json=heartbeat,headers=node_headers)
        camera=next(c for c in self.client.get('/v1/operations').json()['cameras'] if c['organization_id']=='a')
        self.assertIsNone(camera['applied_version'])

    def test_unknown_offline_and_event_signal_are_separate(self):
        data=self.client.get('/v1/operations').json()
        self.assertTrue(all(n['online'] is None for n in data['nodes']))
        self.assertTrue(all(c['camera_status']=='unknown' for c in data['cameras']))
        headers={'Authorization':'Bearer test-node'}
        self.assertEqual(self.client.post('/v1/heartbeat',headers=headers,json={'schema_version':1,'cameras':[{'camera_id':'private-cam','state':'unknown'}]}).status_code,403)
        self.assertEqual(self.client.post('/v1/heartbeat',headers=headers,json={'schema_version':1,'cameras':[{'camera_id':'cam','state':'processing'}]}).status_code,422)
        self.client.post('/v1/heartbeat',headers=headers,json={'schema_version':1,'cameras':[{'camera_id':'cam','state':'processing','last_frame_at':time.time()-1000}]})
        data=self.client.get('/v1/operations').json();camera=next(c for c in data['cameras'] if c['organization_id']=='a')
        self.assertEqual(camera['camera_status'],'stale_frames');self.assertEqual(camera['event_count'],0)
        db=self.db.connect()
        try:
            with db:db.execute('UPDATE node_health SET received_at=0');db.execute('UPDATE camera_health SET received_at=0')
        finally:db.close()
        data=self.client.get('/v1/operations').json();self.assertFalse(next(n for n in data['nodes'] if n['organization_id']=='a')['online'])
        self.assertEqual(next(c for c in data['cameras'] if c['organization_id']=='a')['camera_status'],'stale')

    def test_credential_download_is_admin_only_and_not_echoed_in_audit(self):
        response=self.post('/v1/admin/node-credential',{'organization_id':'a','location_id':'site','node_id':'node'})
        self.assertEqual(response.status_code,200)
        token=response.text.strip()
        self.assertEqual(self.db.authenticate(token)['node_id'],'node')
        self.assertNotIn(token,self.client.get('/v1/operations').text)
        self.assertIn('attachment',response.headers['content-disposition'])
        self.assertEqual(response.headers['cache-control'],'no-store')
        self.post('/v1/admin/assignments',{'email':'tech@example.com','organization_id':'a','location_id':'site'})
        self.login('tech@example.com','test-technician-password')
        self.assertEqual(self.post('/v1/admin/node-credential',{'organization_id':'a','location_id':'site','node_id':'node'}).status_code,403)

    def test_unassign_removes_installer_access(self):
        assignment={'email':'tech@example.com','organization_id':'a','location_id':'site'}
        self.post('/v1/admin/assignments',assignment)
        self.assertEqual(self.post('/v1/admin/unassign',assignment).status_code,200)
        self.login('tech@example.com','test-technician-password')
        self.assertEqual(self.client.get('/v1/installations/context'+self.query).status_code,403)
        self.assertEqual(self.client.get('/v1/operations').json()['cameras'],[])

    def test_installer_assets_match_standalone_and_are_packaged(self):
        for name in ['index.html','styles.css','app.js','calibration.js']:
            self.assertEqual((ROOT/'edge/calibration'/name).read_bytes(),(ROOT/'cloud/cloud_api/installer'/name).read_bytes())
            if name!='index.html':self.assertEqual(self.client.get('/installer/'+name).status_code,200)
        self.assertEqual(self.client.get('/installer/').status_code,200)


if __name__=='__main__':unittest.main()
