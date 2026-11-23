// The API supplies applicability metadata; the fallback also protects a rolling
// deployment while a browser is still talking to the previous API release.
const LABORATORY_COLLEGES = ["CCS", "CHS", "CAS", "CCJ", "CED"];

export function isServiceAreaApplicable(area, college) {
  if (area.code !== "laboratory") return true;
  const allowed = area.applicable_colleges ?? LABORATORY_COLLEGES;
  return allowed.includes(String(college || "").trim().toUpperCase());
}
