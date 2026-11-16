import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from edge_analytics.analytics import Analytics
from edge_analytics.config import load_config
from edge_analytics.storage import EventStore, sync_batch


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(Path(__file__).parents[1] / 'config.example.json')
        self.config['track_distance'] = 0.5
        self.engine = Analytics(self.config)

    def kinds(self, points, time):
        return [event['type'] for event in self.engine.update(points, time)]

    def test_direction_jitter_and_return(self):
        self.kinds([(0.5, 0.4)], 0)
        self.assertNotIn('person_entered', self.kinds([(0.5, 0.501)], 0.2))
        self.assertIn('person_entered', self.kinds([(0.5, 0.6)], 0.4))
        self.assertNotIn('person_entered', self.kinds([(0.5, 0.7)], 0.6))
        self.assertIn('person_exited', self.kinds([(0.5, 0.4)], 0.8))

    def test_finite_line(self):
        self.kinds([(0.01, 0.4)], 0)
        self.assertNotIn('person_entered', self.kinds([(0.01, 0.6)], 1))

    def test_expired_track_does_not_cross(self):
        self.kinds([(0.5, 0.4)], 0)
        self.assertNotIn('person_entered', self.kinds([(0.5, 0.6)], 10))

    def test_dwell_and_lost_censoring(self):
        self.kinds([(0.5, 0.8)], 0)
        events = self.engine.update([(0.5, 0.95)], 1)
        dwell = next(e for e in events if e['type'] == 'dwell_time_completed')
        self.assertEqual(dwell['details']['duration_seconds'], 1)
        self.assertFalse(dwell['details']['censored'])
        self.engine.update([(0.5, 0.8)], 2)
        self.engine.update([(0.5, 0.8)], 3)
        events = self.engine.update([], 6)
        dwell = next(e for e in events if e['type'] == 'dwell_time_completed')
        self.assertEqual(dwell['details']['duration_seconds'], 1)
        self.assertTrue(dwell['details']['censored'])

    def test_no_cross_camera_identity_or_restart_identity(self):
        a = self.engine.update([(0.5, 0.5)], 0)[0]['details']['track_id']
        b = Analytics(self.config).update([(0.5, 0.5)], 0)[0]['details']['track_id']
        self.assertNotEqual(a, b)

    def test_invalid_time_and_points(self):
        self.engine.update([], 10)
        with self.assertRaises(ValueError): self.engine.update([], 9)
        with self.assertRaises(ValueError): self.engine.update([(2, 0)], 11)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = str(Path(self.directory.name) / 'events.sqlite3')
        self.store = EventStore(self.path, 2)
        self.event = {'event_id': 'one', 'type': 'person_entered', 'timestamp': 1, 'details': {}}
        self.store.add([self.event])

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def test_restart_and_deduplication(self):
        self.store.add([self.event])
        self.store.close()
        self.store = EventStore(self.path)
        self.assertEqual(len(self.store.pending()), 1)

    def test_capacity_is_atomic(self):
        with self.assertRaises(RuntimeError):
            self.store.add([dict(self.event, event_id='two'), dict(self.event, event_id='three')])
        self.assertEqual(len(self.store.pending()), 1)

    @patch('edge_analytics.storage.urllib.request.urlopen')
    def test_partial_ack_and_invalid_ack(self, request):
        self.store.add([dict(self.event, event_id='two')])
        request.return_value.__enter__.return_value.read.return_value = b'{"accepted_event_ids":["one"]}'
        self.assertEqual(sync_batch(self.store, 'https://example.com/events', 'test'), 1)
        self.assertEqual(self.store.pending()[0]['event_id'], 'two')
        request.return_value.__enter__.return_value.read.return_value = b'{"accepted_event_ids":["unknown"]}'
        with self.assertRaises(ValueError): sync_batch(self.store, 'https://example.com/events', 'test')
        self.assertEqual(len(self.store.pending()), 1)

    @patch('edge_analytics.storage.urllib.request.urlopen', side_effect=OSError('offline'))
    def test_network_failure_keeps_queue(self, _):
        with self.assertRaises(OSError): sync_batch(self.store, 'https://example.com/events', 'test')
        self.assertEqual(len(self.store.pending()), 1)

    def test_http_rejected_before_network(self):
        with self.assertRaises(ValueError): sync_batch(self.store, 'http://example.com', 'test')


if __name__ == '__main__': unittest.main()
