import { CONCERN_TYPES } from "../concernTypes";
import { useNotice } from "../hooks/useNotice";
import { useState } from "react";
import { api } from "../api";
export default function ConcernPage() {
  const [form, setForm] = useState({student_number: "", email: "", category: "submission", message: ""});
  const [busy,setBusy] = useState(false), [error,setError] = useState(""), [result,setResult] = useState(null);
  useNotice(result?.message);useNotice(error,"error");
  const update = (key) => (e) => setForm({...form, [key]: e.target.value});
  async function send(e) { e.preventDefault(); setBusy(true); setError(""); try {setResult(await api.concern(form));} catch(err){setError(err.message);} finally {setBusy(false);} }
  return <main className="ops-page info-page"><p className="eyebrow">Student support</p><h1>Report a concern</h1><p>Report any issues or difficulties encountered while completing the Student Facility Evaluation to help improve the survey process and ensure a better evaluation experience for all students.</p>
    {result ? <section className="ops-card" role="status"><h2>Concern received</h2><p><strong>{result.reference}</strong></p><p>{result.message}</p></section> : <form className="ops-card form" onSubmit={send}>
      <label>Student number<input required maxLength={32} value={form.student_number} onChange={update("student_number")} placeholder="##-##-###" /></label>
      <label>Institutional email<input required type="email" maxLength={160} value={form.email} onChange={update("email")} /></label>
      <label>Concern type<select value={form.category} onChange={update("category")}>{Object.entries(CONCERN_TYPES).filter(([key])=>key!=="duplicate").map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
      <label>What happened?<textarea required minLength={10} maxLength={2000} rows={5} value={form.message} onChange={update("message")} /></label>
      <p className="muted">Your details and message will be available to authorized staff for reviewing this concern.</p>
      {error && <p role="alert" className="error">{error}</p>}<button className="btn primary" disabled={busy}>{busy ? "Sending…" : "Send concern to QUAD"}</button></form>}
    </main>;
}
