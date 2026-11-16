"""Normalized foot-point tracking and finite-line/zone analytics; no identity matching."""
import math
import uuid
from dataclasses import dataclass, field


@dataclass
class Track:
    point: tuple
    last_seen: float
    side: int = 0
    stable_point: tuple | None = None
    zones: dict = field(default_factory=dict)


class Analytics:
    def __init__(self, config):
        self.config = config
        self.tracks = {}
        self.last_time = None
        self.last_snapshot = None
        self.session = uuid.uuid4().hex
        self.next_id = 0

    def event(self, kind, timestamp, **details):
        return {'event_id': str(uuid.uuid4()), 'type': kind, 'timestamp': timestamp,
                **{key: self.config[key] for key in ('organization_id', 'location_id', 'node_id', 'camera_id')},
                'details': details}

    def _expire(self, timestamp):
        events = []
        for track_id, track in list(self.tracks.items()):
            if timestamp - track.last_seen > self.config['track_timeout']:
                for zone_id, entered in track.zones.items():
                    events.append(self.event('dwell_time_completed', track.last_seen, track_id=track_id,
                                             zone_id=zone_id, duration_seconds=track.last_seen - entered,
                                             completion='track_lost', censored=True))
                del self.tracks[track_id]
        return events

    def update(self, points, timestamp):
        if not math.isfinite(timestamp) or (self.last_time is not None and timestamp < self.last_time):
            raise ValueError('Timestamps must be finite and nondecreasing')
        for point in points:
            if len(point) != 2 or not all(math.isfinite(v) and 0 <= v <= 1 for v in point):
                raise ValueError('Points must be normalized')
        self.last_time = timestamp
        events = self._expire(timestamp)
        pairs = sorted((math.dist(track.point, point), track_id, index)
                       for track_id, track in self.tracks.items() for index, point in enumerate(points))
        used_tracks, used_points, assignments = set(), set(), []
        for distance, track_id, index in pairs:
            if distance <= self.config['track_distance'] and track_id not in used_tracks and index not in used_points:
                used_tracks.add(track_id)
                used_points.add(index)
                assignments.append((track_id, points[index]))
        for index, point in enumerate(points):
            if index not in used_points:
                self.next_id += 1
                track_id = f'{self.session}-{self.next_id}'
                self.tracks[track_id] = Track(tuple(point), timestamp)
                assignments.append((track_id, point))
        a, b = self.config['line']['start'], self.config['line']['end']
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        observed_zones = {zone['id']: 0 for zone in self.config.get('zones', [])}
        for track_id, point in assignments:
            track = self.tracks[track_id]
            distance = (dx * (point[1] - a[1]) - dy * (point[0] - a[0])) / length
            side = 1 if distance > self.config['line']['margin'] else -1 if distance < -self.config['line']['margin'] else 0
            if side:
                if track.side and side != track.side:
                    old = track.stable_point
                    # Intersect the actual motion segment with the finite counting line.
                    old_cross = dx * (old[1] - a[1]) - dy * (old[0] - a[0])
                    new_cross = distance * length
                    ratio = old_cross / (old_cross - new_cross)
                    hit = (old[0] + ratio * (point[0] - old[0]), old[1] + ratio * (point[1] - old[1]))
                    projection = ((hit[0] - a[0]) * dx + (hit[1] - a[1]) * dy) / length**2
                    if 0 <= projection <= 1:
                        kind = 'person_entered' if side == self.config['line']['enter_side'] else 'person_exited'
                        events.append(self.event(kind, timestamp, track_id=track_id))
                track.side, track.stable_point = side, tuple(point)
            for zone in self.config.get('zones', []):
                zone_id = zone['id']
                x1, y1, x2, y2 = zone['rect']
                inside = x1 <= point[0] <= x2 and y1 <= point[1] <= y2
                if inside:
                    observed_zones[zone_id] += 1
                if inside and zone_id not in track.zones:
                    track.zones[zone_id] = timestamp
                    events.append(self.event('zone_crossed', timestamp, track_id=track_id, zone_id=zone_id, direction='entered'))
                elif not inside and zone_id in track.zones:
                    entered = track.zones.pop(zone_id)
                    events.append(self.event('zone_crossed', timestamp, track_id=track_id, zone_id=zone_id, direction='exited'))
                    events.append(self.event('dwell_time_completed', timestamp, track_id=track_id, zone_id=zone_id,
                                             duration_seconds=timestamp - entered, completion='zone_exit', censored=False))
            track.point, track.last_seen = tuple(point), timestamp
        if self.last_snapshot is None or timestamp - self.last_snapshot >= self.config['occupancy_interval']:
            events.append(self.event('occupancy_snapshot', timestamp, visible_persons=len(points),
                                     zones=observed_zones, scope='camera_visible_only'))
            self.last_snapshot = timestamp
        return events

    def reset(self, timestamp):
        """Disconnect/shutdown ends tracks; partial dwell is explicitly censored."""
        events = []
        for track_id, track in self.tracks.items():
            for zone_id, entered in track.zones.items():
                events.append(self.event('dwell_time_completed', track.last_seen, track_id=track_id, zone_id=zone_id,
                                         duration_seconds=track.last_seen - entered, completion='stream_ended', censored=True))
        self.tracks.clear()
        self.last_snapshot = None
        return events
