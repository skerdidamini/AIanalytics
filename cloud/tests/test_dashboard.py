import json
from pathlib import Path
import tempfile
import unittest
from fastapi.testclient import TestClient
from cloud_api.app import create_app
from cloud_api.database import Database
from cloud_api import accounts


class OwnerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'cloud.sqlite3'
        self.database=Database(self.path)
        accounts.initialize(self.database)
        accounts.create_owner(self.database,'org-a','owner@example.com','test-owner-password-123')
        self.database.provision('org-a','site-a','node-a',['camera-a'],'test-node')
        self.database.provision('org-b','site-b','node-b',['camera-b'],'test-other')
        self.client=TestClient(create_app(self.path),base_url='https://testserver')
        self.origin={'Origin':'https://testserver'}

    def tearDown(self):self.client.close();self.temp.cleanup()

    def login(self,password='test-owner-password-123',headers=None):
        return self.client.post('/auth/login',headers=headers or self.origin,json={'email':'owner@example.com','password':password})

    def test_cookie_login_profile_and_logout(self):
        response=self.login()
        self.assertEqual(response.status_code,204,response.text)
        cookie=response.headers['set-cookie']
        self.assertIn('HttpOnly',cookie);self.assertIn('Secure',cookie);self.assertIn('SameSite=strict',cookie)
        self.assertEqual(self.client.get('/v1/me').json()['organization_id'],'org-a')
        self.assertEqual(self.client.get('/auth/login').status_code,405)
        token=self.client.cookies.get('owner_session')
        self.assertNotIn(token,response.text)
        self.assertEqual(self.client.post('/auth/logout',headers=self.origin).status_code,204)
        self.assertEqual(self.client.get('/v1/me').status_code,401)
        self.assertIsNone(accounts.authenticate(self.database,token))

    def test_inventory_is_scoped_and_session_cannot_ingest(self):
        self.login()
        inventory=self.client.get('/v1/inventory').json()
        self.assertEqual(inventory['locations'],['site-a'])
        self.assertEqual(inventory['cameras'],[{'location_id':'site-a','node_id':'node-a','id':'camera-a'}])
        self.assertEqual(self.client.post('/v1/events',json={}).status_code,403)
        self.assertEqual(self.client.get('/v1/metrics/hourly?start=0&end=100&location_id=site-b').json()['rows'],[])

    def test_origin_checks_and_bad_password(self):
        self.assertEqual(self.login(headers={'Origin':'https://other.example'}).status_code,403)
        self.assertEqual(self.client.post('/auth/login',json={}).status_code,403)
        self.assertEqual(self.login('wrong').status_code,401)
        self.assertEqual(self.client.get('/v1/me').status_code,401)
        self.login()
        self.assertEqual(self.client.post('/auth/logout',headers={'Origin':'https://other.example'}).status_code,403)
        self.assertEqual(self.client.get('/v1/me').status_code,200)

    def test_attempt_limit(self):
        for _ in range(5):self.assertEqual(self.login('wrong').status_code,401)
        self.assertEqual(self.login().status_code,429)

    def test_expired_session(self):
        self.login()
        connection=self.database.connect()
        try:
            with connection:connection.execute('UPDATE sessions SET expires=0')
        finally:connection.close()
        self.assertEqual(self.client.get('/v1/me').status_code,401)

    def test_public_home_and_shared_login(self):
        home=self.client.get('/')
        self.assertIn('href="/login"',home.text)
        self.assertIn('Analizë video me përpunim lokal',home.text)
        for asset in ('styles.css','scripts.js','i18n.js'):
            self.assertEqual(self.client.get('/'+asset).status_code,200)
        for page in ('login','panel'):
            self.assertIn('id="login-form"',self.client.get('/'+page).text)
        public=Path(__file__).resolve().parents[1]/'cloud_api/public'
        root=Path(__file__).resolve().parents[2]
        for asset in ('index.html','styles.css','scripts.js','i18n.js'):
            self.assertEqual((public/asset).read_bytes(),(root/asset).read_bytes())

    def test_dashboard_assets_and_no_password_storage(self):
        response=self.client.get('/')
        self.assertEqual(response.status_code,200)
        self.assertIn("frame-ancestors 'none'",response.headers['content-security-policy'])
        self.assertEqual(self.client.get('/dashboard/app.js').status_code,200)
        self.assertEqual(self.client.get('/dashboard/not-allowed').status_code,404)
        self.assertNotIn('localStorage',self.client.get('/dashboard/app.js').text)
        connection=self.database.connect()
        try:owner=connection.execute('SELECT salt,password_hash FROM owners').fetchone()
        finally:connection.close()
        self.assertNotIn('test-owner-password-123',tuple(owner))


if __name__=='__main__':unittest.main()
