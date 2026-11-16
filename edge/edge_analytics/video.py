"""CPU baseline detector. Replace after accuracy/performance evaluation on pilot footage."""
import os
import time


def frames(source, sample_fps, max_width, live):
    import cv2
    while True:
        capture = cv2.VideoCapture()
        capture.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)
        capture.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10000)
        opened = capture.open(source, cv2.CAP_FFMPEG,
                               [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10000])
        if not opened:
            capture.release()
            if not live:
                raise RuntimeError('Cannot open local video')
            print('Camera unavailable; retrying in 5 seconds', flush=True)
            yield None, time.time()
            time.sleep(5)
            continue
        fps = capture.get(cv2.CAP_PROP_FPS)
        if not live and not fps > 0:
            capture.release()
            raise RuntimeError('Video has no usable FPS for event timing')
        origin, index, next_sample = time.time(), 0, 0.0
        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                timestamp = time.time() if live else origin + index / fps
                index += 1
                if timestamp + 1e-6 < next_sample:
                    continue
                next_sample = timestamp + 1 / sample_fps
                height, width = frame.shape[:2]
                if width > max_width:
                    frame = cv2.resize(frame, (int(max_width), max(1, int(height * max_width / width))))
                yield frame, timestamp
        finally:
            capture.release()
        if not live:
            return
        print('Camera disconnected; reconnecting', flush=True)
        yield None, time.time()
        time.sleep(5)


class PersonDetector:
    def __init__(self):
        import cv2
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def detect(self, frame):
        import cv2
        height, width = frame.shape[:2]
        if width < 64 or height < 128:
            return []
        boxes, weights = self.hog.detectMultiScale(frame, winStride=(8, 8), padding=(8, 8), scale=1.05)
        boxes = [list(map(int, box)) for box in boxes]
        scores = [float(weight) for weight in weights]
        indices = cv2.dnn.NMSBoxes(boxes, scores, 0.0, 0.4)
        return [((boxes[int(i)][0] + boxes[int(i)][2] / 2) / width,
                 min(1.0, (boxes[int(i)][1] + boxes[int(i)][3]) / height)) for i in indices]
