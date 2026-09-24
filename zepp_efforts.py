"""Rolling efforts from Zepp currentDistance (centimetres, delta seconds).
Only derived aggregate times leave the local bridge database.
"""
from bisect import bisect_left, bisect_right
import math

DISTANCES = {'1 km': 1000, '1 mile': 1609, '5 km': 5000, '10 km': 10000, 'Half': 21098}
TIMES = {f'{minutes} min': minutes * 60 for minutes in (5, 10, 20, 30, 60, 90, 120)}


def furthest(points, seconds):
    """Largest distance in a complete elapsed-time window, including stops."""
    if len(points) < 2 or points[-1][0] - points[0][0] < seconds:
        return None
    ts, ds = zip(*points)
    def at(t):
        i = bisect_left(ts, t)
        if ts[i] == t:
            return ds[i]
        return ds[i-1] + (t-ts[i-1]) / (ts[i]-ts[i-1]) * (ds[i]-ds[i-1])
    starts = set(ts) | {t-seconds for t in ts}
    return max(at(t+seconds)-at(t) for t in starts
               if ts[0] <= t <= ts[-1]-seconds)


def time_efforts(detail, workout):
    segments = distance_segments(detail.get('currentDistance', ''),
                                 workout['distance_meters'], workout['elapsed_seconds'])
    result = {}
    for label, seconds in TIMES.items():
        values = [v for segment in segments if (v := furthest(segment, seconds)) is not None]
        if values and max(values) > 0:
            result[label] = max(values)
    return result


def distance_segments(encoded, total_m, elapsed):
    points = []
    t = 0.0
    previous = -1.0
    for record in encoded.split(';'):
        if not record:
            continue
        dt, cm = map(float, record.split(','))
        d = cm / 100
        if not all(math.isfinite(v) for v in (dt, d)) or dt < 0 or d < 0 or d < previous:
            raise ValueError('Invalid Zepp distance timeline')
        t += dt
        previous = d
        # Zepp may append a final record after the workout end; do not use it.
        if t > elapsed:
            continue
        if points and t == points[-1][0]:
            points[-1] = (t, d)  # timestamps have one-second resolution
        else:
            points.append((t, d))
    if not points or abs(previous-total_m) > max(2, total_m*.005):
        raise ValueError('Distance timeline does not match workout total')
    if abs(t-elapsed) > 30 or points[0][0] > 15:
        raise ValueError('Time coverage does not match workout')
    segments, segment = [], []
    for point in points:
        if segment and point[0]-segment[-1][0] > 15:
            segments.append(segment)
            segment = []  # never interpolate across a long missing interval/pause
        segment.append(point)
    if segment:
        segments.append(segment)
    return segments


def fastest(points, target):
    """Exact minimum for the piecewise-linear recorded distance curve.

    Check starts and finishes at all distance knots. Plateaus use latest
    departure / earliest arrival, while pauses inside an effort count as time.
    """
    if len(points) < 2 or points[-1][1]-points[0][1] < target:
        return None
    ts, ds = zip(*points)
    def at(d, departure):
        i = bisect_right(ds, d)-1 if departure else bisect_left(ds, d)
        if ds[i] == d:
            return ts[i]
        if departure:
            i += 1
        return ts[i-1]+(d-ds[i-1])/(ds[i]-ds[i-1])*(ts[i]-ts[i-1])
    candidates = set(ds) | {d-target for d in ds}
    values = [at(d+target, False)-at(d, True) for d in candidates
              if ds[0] <= d <= ds[-1]-target]
    return min(values) if values else None


def efforts(detail, workout):
    elapsed = workout['elapsed_seconds']
    segments = distance_segments(detail.get('currentDistance', ''), workout['distance_meters'], elapsed)
    result = {}
    for label, target in DISTANCES.items():
        values = [v for segment in segments if (v := fastest(segment, target)) is not None]
        if values:
            result[label] = min(values)
    return result
