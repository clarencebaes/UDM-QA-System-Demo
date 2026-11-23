// Read-only export for local annotation. Current predictions are not gold labels.
// Student numbers and emails are deliberately not copied into the export.
export async function collectSurveyExport(fetchPage, snapshotAt = new Date().toISOString()) {
  const records = new Map();
  let expected = null;
  for (let page = 1; ; page++) {
    const result = await fetchPage({ page, page_size: 100, end_date: snapshotAt });
    if (expected === null) expected = result.total;
    if (result.total !== expected || result.page !== page) throw new Error("Survey data changed during export. Please retry.");
    for (const row of result.items) records.set(row.id, {
      id: String(row.id), text: row.comment, service_area: row.department, college: row.college,
      respondent: row.respondent_group || "", source: row.respondent_group ? `survey:${row.respondent_group}` : `survey-record:${row.id}`,
      current_sentiment: row.sentiment || "", current_aspect: row.aspect || "",
      current_polarity: row.polarity || "", is_constructive: Boolean(row.is_constructive), detected_language: row.detected_language || "undetermined",
      current_aspects: row.aspects || (row.aspect && row.aspect !== "N/A" ? [row.aspect] : []), aspect_version: row.aspect_version || "legacy",
      proposed_sentiment: "", proposed_aspect: "", annotation_notes: "", approved: "no",
    });
    if (page * 100 >= expected) break;
    if (!result.items.length) throw new Error("Export stopped before all comments were read. Please retry.");
  }
  if (records.size !== expected) throw new Error("Export has duplicate or missing records. Please retry.");
  return { snapshot_at: snapshotAt, total: expected, labels_are_provisional: true, records: [...records.values()] };
}
