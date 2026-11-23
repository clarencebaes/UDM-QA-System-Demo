// Historical aspect-wide oracle retained for compatibility fixtures.
// Production views now use the service-area API in backend/app/services/alerts.py.
const OPEN_STATUSES = new Set(["new", "acknowledged", "in-progress"]);

function timestamp(value) {
  const stamp = value || "";
  // MySQL timestamps are UTC, including values serialized without an offset.
  return Date.parse(/(?:Z|[+-]\d{2}:\d{2})$/.test(stamp) ? stamp : `${stamp}Z`);
}

export function buildInterventionView(rows, aspects, thresholds, alerts, now = Date.now()) {
  const definitions = new Map(aspects.map((aspect) => [aspect.name, aspect]));
  const rules = new Map(thresholds.map((threshold) => [threshold.aspect_code, threshold]));
  const openAlerts = new Map();
  for (const alert of alerts) {
    if (OPEN_STATUSES.has(alert.status) && !openAlerts.has(alert.aspect_code)) {
      openAlerts.set(alert.aspect_code, alert);
    }
  }

  const grouped = new Map();
  for (const row of rows) {
    const aspect = definitions.get(row.aspect);
    const threshold = rules.get(aspect?.code);
    const alert = openAlerts.get(aspect?.code);
    if (!threshold || !alert || !["negative", "constructive"].includes(row.sentiment)) continue;
    if (row.sentiment === "constructive" && !threshold.include_constructive) continue;
    const created = timestamp(row.created_at);
    if (!Number.isFinite(created) || created < now - threshold.window_days * 86400000) continue;

    let group = grouped.get(aspect.code);
    if (!group) {
      group = { aspect: aspect.name, aspect_code: aspect.code, alert_id: alert.id,
        negative: 0, constructive: 0, min_count: threshold.min_count,
        window_days: threshold.window_days, areas: new Map(), feedback: [] };
      grouped.set(aspect.code, group);
    }
    group[row.sentiment] += 1;
    group.feedback.push(row);
    const area = row.department || "Unknown";
    const pair = group.areas.get(area) || { service_area: area, negative: 0, constructive: 0 };
    pair[row.sentiment] += 1;
    group.areas.set(area, pair);
  }

  const summaries = [];
  const pairs = [];
  const feedback = [];
  for (const group of grouped.values()) {
    const count = group.negative + group.constructive;
    if (count < group.min_count) continue;
    const summary = { aspect: group.aspect, aspect_code: group.aspect_code,
      alert_id: group.alert_id, negative: group.negative, constructive: group.constructive,
      count, min_count: group.min_count, window_days: group.window_days,
      area_count: group.areas.size, level: count >= group.min_count * 2 ? "high" : "medium" };
    summaries.push(summary);
    feedback.push(...group.feedback);
    for (const pair of group.areas.values()) {
      pairs.push({ ...summary, ...pair, count: pair.negative + pair.constructive,
        aspect_count: count });
    }
  }
  summaries.sort((a, b) => b.count - a.count || a.aspect.localeCompare(b.aspect));
  pairs.sort((a, b) => b.aspect_count - a.aspect_count || b.count - a.count ||
    a.aspect.localeCompare(b.aspect) || a.service_area.localeCompare(b.service_area));
  // Preserve the API's newest-first ordering for the Dashboard preview.
  const included = new Set(feedback);
  return { aspects: summaries, pairs, feedback: rows.filter((row) => included.has(row)) };
}
