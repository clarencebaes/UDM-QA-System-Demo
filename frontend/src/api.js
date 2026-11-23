import { fetchText } from "./http";
import { createEvaluationConfigCache } from "./evaluationConfigCache";
import { createReadCache, readKey } from "./readCache";
const readCache=createReadCache();

// Base URL for API calls.
// - Local dev: "/api" (Vite proxies to the backend on :8000).
// - Production (frontend on Cloudflare Pages, backend on Render):
//   Vite env var VITE_API_URL to the backend origin, e.g.
//   VITE_API_URL=https://example.invalid/api
// The backend must also list this site's origin in CORS_ORIGINS.
const API = import.meta.env.VITE_API_URL || "/api";

export function getToken() {
  return localStorage.getItem("udm_qa_token") || "";
}

export function setSession(token, profile) {
  if(token!==getToken()||JSON.stringify(profile||{})!==localStorage.getItem("udm_qa_profile"))readCache.clear();
  localStorage.setItem("udm_qa_token", token);
  localStorage.setItem("udm_qa_profile", JSON.stringify(profile || {}));
}

export function clearSession() {
  readCache.clear();
  localStorage.removeItem("udm_qa_token");
  localStorage.removeItem("udm_qa_profile");
}

export function getProfile() {
  try {
    return JSON.parse(localStorage.getItem("udm_qa_profile") || "{}");
  } catch {
    return {};
  }
}

async function fetchRequest(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const { response: res, text } = await fetchText(`${API}${path}`, { ...options, headers });
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }
  if (!res.ok) {
    if(res.status===401||res.status===403)readCache.clear();
    const detail = data?.detail;
    const msg = typeof detail === "string" ? detail : detail?.[0]?.msg || res.statusText;
    throw new Error(msg || "Request failed");
  }
  return data;
}

function request(path,options={}){
  const method=(options.method||"GET").toUpperCase();
  if(method!=="GET"){
    readCache.clear();evaluationConfigCache.clear();
    return fetchRequest(path,options).finally(()=>{readCache.clear();evaluationConfigCache.clear();});
  }
  const cacheable=method==="GET"&&!options.signal&&(path.startsWith("/qa/")||["/departments","/aspects","/colleges"].includes(path));
  // Always validate account access and check live survey availability on the server.
  if(!cacheable||path==="/qa/me")return fetchRequest(path,options);
  return readCache.read(readKey(path,getToken()),()=>fetchRequest(path,options));
}
if(typeof window!=="undefined")window.addEventListener("storage",()=>readCache.clear());

const evaluationConfigCache = createEvaluationConfigCache(() => request("/evaluation-config"));

export const api = {
  request,
  invalidateReads:()=>readCache.clear(),
  submitSurvey: (body) => request("/submissions", { method: "POST", body: JSON.stringify(body) }),
  receipt: (token) => request("/receipt", { method: "POST", body: JSON.stringify({token}) }),
  concern: (body) => request("/concerns", { method: "POST", body: JSON.stringify(body) }),
  logout: () => request("/auth/logout", {method: "POST"}),
  evaluationConfig: (force = false) => evaluationConfigCache.load(force),
  health: () => request("/health"),
  departments: () => request("/departments"),
  aspects: () => request("/aspects"),
  colleges: () => request("/colleges"),
  addCollege: (college) =>
    request("/colleges", { method: "POST", body: JSON.stringify(college) }),
  deleteCollege: (code) =>
    request(`/colleges/${encodeURIComponent(code)}`, { method: "DELETE" }),
  submitFeedback: (body) =>
    request("/feedback", { method: "POST", body: JSON.stringify(body) }),
  submitFeedbackBatch: (items) =>
    request("/feedback/batch", { method: "POST", body: JSON.stringify({ items }) }),
  login: (body) => request("/auth/login", { method: "POST", body: JSON.stringify(body) }),
  dashboard: (filters) => {
    const params = new URLSearchParams();
    if (filters?.college && filters.college !== "all") params.set("college", filters.college);
    if (filters?.section) params.set("section", filters.section);
    if (filters?.cycle_id) params.set("cycle_id", filters.cycle_id);
    if (filters?.startDate) params.set("start_date", filters.startDate);
    if (filters?.endDate) params.set("end_date", filters.endDate);
    const qs = params.toString();
    return request(`/qa/dashboard${qs ? `?${qs}` : ""}`);
  },
  feedback: (filters) => {
    const params = new URLSearchParams();
    if (filters?.startDate) params.set("start_date", filters.startDate);
    if (filters?.endDate) params.set("end_date", filters.endDate);
    const qs = params.toString();
    return request(`/qa/feedback${qs ? `?${qs}` : ""}`);
  },
  feedbackPage: (filters = {}) => request(`/qa/feedback-page?${new URLSearchParams(filters)}`),
  feedbackOptions: (filters = {}) => request(`/qa/feedback-options?${new URLSearchParams(filters)}`),
  mostCommented: (filters = {}) => request(`/qa/most-commented?${new URLSearchParams(filters)}`),
  interventions: (college = "all", page = 1) => request(`/qa/interventions?${new URLSearchParams({ college, page, page_size: 2 })}`),
  interventionWorkspace:()=>request("/qa/interventions?college=all&page=1&page_size=2&include_alerts=true"),
  interventionDetail: (department, aspect_code) => request(`/qa/intervention-detail?${new URLSearchParams({ department, aspect_code })}`),
  feedbackDetail: (id) => request(`/qa/feedback/${id}`),
  headcounts: () => request("/qa/headcounts"),
  saveHeadcounts: (items) =>
    request("/qa/headcounts", { method: "PUT", body: JSON.stringify({ items }) }),
  alerts: (status) => {
    const qs = status ? `?status=${status}` : "";
    return request(`/qa/alerts${qs}`);
  },
  patchAlert: (id, status, note, extra = {}) => {
    const body = { ...extra };
    if (status) body.status = status;
    if (note !== undefined && note !== null) body.note = note;
    return request(`/qa/alerts/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },
  deleteAlert: (id) =>
    request(`/qa/alerts/${id}`, { method: "DELETE" }),
  thresholds: () => request("/qa/thresholds"),
  patchThreshold: (id, data) =>
    request(`/qa/thresholds/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  rules: () => request("/qa/intervention-rules"),
  createRule: (data) =>
    request("/qa/intervention-rules", { method: "POST", body: JSON.stringify(data) }),
  patchRule: (id, data) =>
    request(`/qa/intervention-rules/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteRule: (id) =>
    request(`/qa/intervention-rules/${id}`, { method: "DELETE" }),
  me: () => request("/qa/me"),
  updateProfile: (data) =>
    request("/qa/me", { method: "PATCH", body: JSON.stringify(data) }),
  surveySettings: () => request("/qa/survey-settings"),
  // Public: no auth required — used by the student landing page.
  surveyStatus: () => request("/survey-status"),
  updateSurveySettings: (data) =>
    request("/qa/survey-settings", { method: "PATCH", body: JSON.stringify(data) }),
};

export async function downloadBackup() {
  readCache.clear();
  try {
  const res = await fetch(`${API}/qa/backup`, { method: "POST", headers: {Authorization: `Bearer ${getToken()}`} });
  if (!res.ok) { const body = await res.json(); throw new Error(body.detail || "Backup failed"); }
  return res.text();
  } finally {readCache.clear();}
}
export function saveBackup(text, name = "udm-backup") {
  const url = URL.createObjectURL(new Blob([text], {type: "application/octet-stream"}));
  const a = document.createElement("a"); a.href = url; a.download = `${name}-${new Date().toISOString().slice(0,10)}.udmbackup`; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
