import json
import sqlite3
import time
import urllib.request
from urllib.parse import urlsplit


class EventStore:
    def __init__(self, path, capacity=100000):
        self.db = sqlite3.connect(path)
        self.capacity = capacity
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, payload TEXT NOT NULL, synced INTEGER NOT NULL DEFAULT 0)')
        self.db.commit()

    def add(self, events):
        # Fail visibly rather than silently discard unsent business events.
        pending = self.db.execute('SELECT count(*) FROM events WHERE synced=0').fetchone()[0]
        if pending + len(events) > self.capacity:
            raise RuntimeError('Unsent event queue is full; restore sync or increase capacity')
        with self.db:
            self.db.executemany('INSERT OR IGNORE INTO events(id,payload) VALUES (?,?)',
                                [(event['event_id'], json.dumps(event, allow_nan=False)) for event in events])

    def pending(self, limit=100):
        return [json.loads(row[0]) for row in self.db.execute('SELECT payload FROM events WHERE synced=0 ORDER BY rowid LIMIT ?', (limit,))]

    def acknowledge(self, ids):
        with self.db:
            self.db.executemany('UPDATE events SET synced=1 WHERE id=?', [(value,) for value in ids])

    def status(self):
        return dict(self.db.execute('SELECT CASE synced WHEN 0 THEN "pending" ELSE "synced" END, count(*) FROM events GROUP BY synced'))

    def all(self):
        return (json.loads(row[0]) for row in self.db.execute('SELECT payload FROM events ORDER BY rowid'))

    def close(self):
        self.db.close()


def sync_batch(store, url, token):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError('Cloud API must use HTTPS without URL credentials or fragments')
    if not token:
        raise ValueError('Cloud token is required')
    events = store.pending()
    if not events:
        return 0
    request = urllib.request.Request(url, data=json.dumps({'schema_version': 1, 'events': events}).encode(),
                                     headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}, method='POST')
    # TLS verification and normal proxy behavior remain enabled.
    with urllib.request.urlopen(request, timeout=15) as response:
        body = json.loads(response.read(1024 * 1024))
    ids = body.get('accepted_event_ids')
    sent = {event['event_id'] for event in events}
    if not isinstance(ids, list) or not all(isinstance(value, str) and value in sent for value in ids):
        raise ValueError('Cloud returned invalid acknowledgement; queue preserved')
    store.acknowledge(ids)
    return len(set(ids))
