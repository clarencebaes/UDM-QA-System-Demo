const KEY = "udm_receipt_reference_seen";

// Presentation only. Receipt access still requires the server-validated token.
export function referenceWasShown(token, storage = sessionStorage) {
  try { return Boolean(token) && storage.getItem(`${KEY}:${token}`) === "1"; }
  catch { return true; }
}

export function markReferenceShown(token, storage = sessionStorage) {
  try { if (token) storage.setItem(`${KEY}:${token}`, "1"); }
  catch { /* A storage restriction must not prevent receipt access. */ }
}
