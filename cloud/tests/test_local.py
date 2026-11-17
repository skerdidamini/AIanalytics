from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from fastapi.testclient import TestClient
from cloud_api import accounts
from cloud_api.app import create_app
from cloud_api.database import Database
from cloud_api.local import ensure_owner, seed_demo


class LocalTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.database=Database(Path(self.directory.name)/'demo.sqlite3')
        accounts.initialize(self.database)

    def tearDown(self):self.directory.cleanup()

    def test_first_setup_and_existing_account(self):
        answers=iter(['Test business','owner@example.com'])
        passwords=iter(['local-test-password-123','local-test-password-123'])
        organization=ensure_owner(self.database,True,lambda _:next(answers),lambda _:next(passwords))
        self.assertEqual(organization,'Test business')
        self.assertEqual(ensure_owner(self.database,True,lambda _:self.fail('Should not prompt twice')),organization)
        token=accounts.login(self.database,'owner@example.com','local-test-password-123','test')
        self.assertIsNotNone(token)

    def test_administrator_does_not_replace_owner_setup(self):
        from cloud_api.operations import SYSTEM_ORG
        accounts.create_owner(self.database,SYSTEM_ORG,'admin@example.com','admin-test-password','admin')
        answers=iter(['real-business','owner@example.com']);passwords=iter(['owner-test-password','owner-test-password'])
        organization=ensure_owner(self.database,False,lambda _:next(answers),lambda _:next(passwords))
        self.assertEqual(organization,'real-business')

    def test_demo_seed_is_idempotent_and_time_bounded(self):
        now=datetime(2026,11,16,12,30,tzinfo=timezone.utc)
        count=seed_demo(self.database,'demo',now)
        self.assertGreater(count,0)
        seed_demo(self.database,'demo',now)
        rows=self.database.hourly('demo',0,now.timestamp()+1)
        before=sum(row['entries'] for row in rows)
        seed_demo(self.database,'demo',now)
        self.assertEqual(sum(row['entries'] for row in self.database.hourly('demo',0,now.timestamp()+1)),before)
        db=self.database.connect()
        try:
            self.assertEqual(db.execute('SELECT count(*) FROM events').fetchone()[0],count)
            self.assertLessEqual(db.execute('SELECT max(timestamp) FROM events').fetchone()[0],now.timestamp())
        finally:db.close()

    def test_demo_marker_from_server_and_real_database_is_empty(self):
        accounts.create_owner(self.database,'demo','owner@example.com','local-test-password-123')
        with TestClient(create_app(self.database.path,demo=True),base_url='https://testserver') as client:
            client.post('/auth/login',headers={'Origin':'https://testserver'},json={'email':'owner@example.com','password':'local-test-password-123'})
            self.assertTrue(client.get('/v1/me').json()['demo'])
        real=Database(Path(self.directory.name)/'local.sqlite3')
        accounts.initialize(real)
        accounts.create_owner(real,'real','owner@example.com','real-test-password-123')
        with TestClient(create_app(real.path),base_url='https://testserver') as client:
            client.post('/auth/login',headers={'Origin':'https://testserver'},json={'email':'owner@example.com','password':'real-test-password-123'})
            self.assertFalse(client.get('/v1/me').json()['demo'])
            self.assertEqual(client.get('/v1/metrics/hourly?start=0&end=100').json()['rows'],[])


if __name__=='__main__':unittest.main()
