import argparse
import csv
import json
import os
import signal
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

from .analytics import Analytics
from .config import load_config
from .storage import EventStore, sync_batch


def main():
    parser = argparse.ArgumentParser(description='Single-camera anonymous edge analytics PoC')
    parser.add_argument('--config', required=True)
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('run')
    run.add_argument('--video', help='Local video path; otherwise read RTSP from EDGE_RTSP_URL')
    run.add_argument('--max-frames', type=int, default=0)
    replay = commands.add_parser('replay')
    replay.add_argument('path', help='JSONL with timestamp and normalized points')
    commands.add_parser('status')
    sync = commands.add_parser('sync')
    sync.add_argument('--watch', action='store_true', help='Retry with backoff; run separately from video process')
    report = commands.add_parser('report')
    report.add_argument('--output', required=True)
    args = parser.parse_args()
    config = load_config(args.config)
    store = EventStore(config['database'], config['queue_max_events'])
    stopped = False

    def stop(*_):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        if args.command == 'status':
            print(json.dumps(store.status()))
        elif args.command == 'sync':
            url = os.environ.get(config.get('cloud_url_env', 'EDGE_CLOUD_URL'), '')
            token = os.environ.get(config.get('cloud_token_env', 'EDGE_CLOUD_TOKEN'), '')
            if not url or not token:
                raise ValueError('Set cloud URL/token in the documented environment variables')
            delay = 1
            while not stopped:
                try:
                    count = sync_batch(store, url, token)
                    print(f'Acknowledged events: {count}', flush=True)
                    delay = 1 if count else 5
                except Exception:
                    # Do not log exceptions containing endpoint URLs or credentials.
                    if not args.watch:
                        raise RuntimeError('Cloud sync failed; queue preserved') from None
                    print('Cloud sync unavailable; queue preserved; retrying', flush=True)
                    delay = min(delay * 2, 60)
                if not args.watch:
                    break
                for _ in range(delay * 10):
                    if stopped:
                        break
                    time.sleep(0.1)
        elif args.command == 'report':
            rows = defaultdict(lambda: {'entries': 0, 'exits': 0, 'completed_zone_dwell_seconds': 0.0, 'completed_zone_dwell_sessions': 0})
            for event in store.all():
                hour = datetime.fromtimestamp(event['timestamp'], timezone.utc).strftime('%Y-%m-%dT%H:00:00Z')
                row = rows[(hour, event['camera_id'])]
                if event['type'] == 'person_entered': row['entries'] += 1
                if event['type'] == 'person_exited': row['exits'] += 1
                if event['type'] == 'dwell_time_completed' and not event['details']['censored']:
                    row['completed_zone_dwell_seconds'] += event['details']['duration_seconds']
                    row['completed_zone_dwell_sessions'] += 1
            with open(args.output, 'w', newline='') as output:
                writer = csv.DictWriter(output, fieldnames=['hour_utc', 'camera_id', 'entries', 'exits', 'completed_zone_dwell_seconds', 'completed_zone_dwell_sessions'])
                writer.writeheader()
                for (hour, camera), row in sorted(rows.items()):
                    writer.writerow({'hour_utc': hour, 'camera_id': camera, **row})
        else:
            engine = Analytics(config)
            if args.command == 'replay':
                with open(args.path) as source:
                    for line in source:
                        if stopped: break
                        record = json.loads(line)
                        store.add(engine.update(record['points'], record['timestamp']))
            else:
                # Suppress native FFmpeg/OpenCV URL logs before importing video libraries.
                os.environ['OPENCV_FFMPEG_LOGLEVEL'] = '-8'
                os.environ['OPENCV_LOG_LEVEL'] = 'SILENT'
                from .video import PersonDetector, frames
                source = args.video or os.environ.get('EDGE_RTSP_URL')
                if not source:
                    raise ValueError('Provide --video or set EDGE_RTSP_URL securely')
                if not args.video and not source.startswith(('rtsp://', 'rtsps://')):
                    raise ValueError('EDGE_RTSP_URL must be an RTSP URL')
                detector, count = PersonDetector(), 0
                iterator = frames(source, config['sample_fps'], config['max_width'], not bool(args.video))
                try:
                    for frame, timestamp in iterator:
                        if stopped: break
                        if frame is None:
                            store.add(engine.reset(timestamp))
                            continue
                        store.add(engine.update(detector.detect(frame), timestamp))
                        count += 1
                        if args.max_frames and count >= args.max_frames: break
                finally:
                    iterator.close()
                print(f'Analyzed frames: {count}')
            store.add(engine.reset(time.time()))
            print(json.dumps(store.status()))
    finally:
        store.close()


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError) as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(1)
