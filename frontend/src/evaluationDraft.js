export const DRAFT_KEY = "udm_eval_draft_v1";

export function readDraft(storage = sessionStorage) {
  try {
    const draft = JSON.parse(storage.getItem(DRAFT_KEY) || "null");
    return draft?.version === 1 && Number.isInteger(draft.cycleId) && draft.identity
      && ["student_number", "institutional_email", "college"].every(key => typeof draft.identity[key] === "string")
      && ["regular", "irregular"].includes(draft.studentStatus)
      && Number.isInteger(draft.step) && draft.step >= 0 && draft.step < 30
      && draft.ratings && !Array.isArray(draft.ratings) && typeof draft.ratings === "object"
      && draft.comments && !Array.isArray(draft.comments) && typeof draft.comments === "object" ? draft : null;
  } catch { return null; }
}

export function saveDraft(draft, storage = sessionStorage) {
  try { storage.setItem(DRAFT_KEY, JSON.stringify({...draft, version: 1})); return true; }
  catch { return false; }
}

export function clearDraft(storage = sessionStorage) {
  storage.removeItem(DRAFT_KEY);
}
