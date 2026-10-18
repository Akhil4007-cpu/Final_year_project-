const EARTH_RADIUS_M = 6371008.8;
const RAD = Math.PI / 180;

export function haversine(a, b) {
  const lat1 = a[0] * RAD;
  const lat2 = b[0] * RAD;
  const dLat = lat2 - lat1;
  const dLon = (b[1] - a[1]) * RAD;
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)));
}

export function cumulativeDistances(points) {
  const cumulative = new Array(points.length);
  cumulative[0] = 0;
  for (let i = 1; i < points.length; i += 1) {
    cumulative[i] = cumulative[i - 1] + haversine(points[i - 1], points[i]);
  }
  return cumulative;
}

export function nearestOnPolyline(point, points, cumulative) {
  if (!Array.isArray(points) || points.length < 2) {
    return { distanceM: Infinity, progressM: 0, index: 0 };
  }
  const lat0 = point[0] * RAD;
  const cosLat = Math.cos(lat0);
  const project = (latlon) => [
    (latlon[1] - point[1]) * RAD * EARTH_RADIUS_M * cosLat,
    (latlon[0] - point[0]) * RAD * EARTH_RADIUS_M,
  ];
  let best = { distanceM: Infinity, progressM: 0, index: 0 };
  for (let i = 0; i < points.length - 1; i += 1) {
    const a = project(points[i]);
    const b = project(points[i + 1]);
    const dx = b[0] - a[0];
    const dy = b[1] - a[1];
    const denominator = dx * dx + dy * dy;
    let t = 0;
    if (denominator > 1e-9) {
      t = Math.max(0, Math.min(1, -(a[0] * dx + a[1] * dy) / denominator));
    }
    const cx = a[0] + t * dx;
    const cy = a[1] + t * dy;
    const distance = Math.hypot(cx, cy);
    if (distance < best.distanceM) {
      const segmentLength = cumulative[i + 1] - cumulative[i];
      best = {
        distanceM: distance,
        progressM: cumulative[i] + t * segmentLength,
        index: i,
      };
    }
  }
  return best;
}

export function pointAtDistance(points, cumulative, distance) {
  if (!points.length) return null;
  if (distance <= 0) return points[0];
  const total = cumulative[cumulative.length - 1];
  if (distance >= total) return points[points.length - 1];
  let low = 0;
  let high = cumulative.length - 1;
  while (low + 1 < high) {
    const mid = Math.floor((low + high) / 2);
    if (cumulative[mid] <= distance) low = mid;
    else high = mid;
  }
  const segment = cumulative[high] - cumulative[low];
  const t = segment > 0 ? (distance - cumulative[low]) / segment : 0;
  return [
    points[low][0] + t * (points[high][0] - points[low][0]),
    points[low][1] + t * (points[high][1] - points[low][1]),
  ];
}

export function formatDistance(metres) {
  if (!Number.isFinite(metres)) return "—";
  const value = Math.max(0, metres);
  if (value < 1000) {
    return `${Math.round(value / 10) * 10} m`;
  }
  return `${(value / 1000).toFixed(value < 10000 ? 1 : 0)} km`;
}

export function formatDuration(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return "—";
  const totalMinutes = Math.round(seconds / 60);
  if (totalMinutes < 60) return `${Math.max(1, totalMinutes)} min`;
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return minutes ? `${hours} h ${String(minutes).padStart(2, "0")} min` : `${hours} h`;
}

export function formatTimeAgo(iso) {
  const then = Date.parse(iso);
  if (!Number.isFinite(then)) return "";
  const seconds = Math.max(0, (Date.now() - then) / 1000);
  if (seconds < 90) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  return `${days} d ago`;
}

export function clamp(value, low, high) {
  return Math.max(low, Math.min(high, value));
}
