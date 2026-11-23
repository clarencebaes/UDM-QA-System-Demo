/** Client-side checks matching backend/app/colleges.py.
 * Student numbers are opaque identifiers: the digit groups do not imply a
 * year or college. College is chosen separately from the configured list.
 */
const STUDENT_NUMBER_RE = /^[0-9]{2}-[0-9]{2}-[0-9]{3}$/;

export function normalizeStudentNumber(value) {
  // Preserve every digit and leading zero; do not guess or rewrite formats.
  return String(value ?? "").trim();
}

export function isValidStudentNumber(value) {
  return STUDENT_NUMBER_RE.test(normalizeStudentNumber(value));
}

export function isValidEmail(value) {
  const v = String(value || "").trim();
  return /^[^\s@]+@udm\.edu\.ph$/i.test(v);
}
