import { useEffect, useState } from "react";
import { api } from "../api";

export default function CycleSelect({ value, onChange, className = "fb-field" }) {
  const [cycles, setCycles] = useState([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api.request("/qa/cycles").then(data => { if (active) setCycles(data.items); })
      .catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
  }, []);
  return <label className={className}><span>Evaluation period</span>
    <select value={value} onChange={e => onChange(e.target.value)}>
      <option value="">All semesters</option>
      {cycles.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
    </select>{error && <small className="error" role="alert">{error}</small>}
  </label>;
}
