import { useNotice } from "../../hooks/useNotice";
import { useEffect, useState } from "react";
import { api } from "../../api";
export default function CycleSettings(){
  const [data,setData]=useState(null),[year,setYear]=useState("2026-2027"),[semester,setSemester]=useState("1st"),[selected,setSelected]=useState(""),[error,setError]=useState(""),[msg,setMsg]=useState(""),[busy,setBusy]=useState(false);
  async function load(){const d=await api.request("/qa/cycles");setData(d);setSelected(String(d.active_id||d.items[0]?.id||""));}
  useNotice(msg,"success");
  useNotice(error,"error");
  useEffect(()=>{load().catch(e=>setError(e.message));},[]);
  async function create(e){e.preventDefault();setBusy(true);setError("");setMsg("");try{await api.request("/qa/cycles",{method:"POST",body:JSON.stringify({academic_year:year,semester})});await load();setMsg("Cycle created. Select it below to use it.");}catch(e){setError(e.message);}finally{setBusy(false);}}
  async function activate(){if(!selected)return;setBusy(true);setError("");setMsg("");try{await api.request(`/qa/cycles/${selected}/activate`,{method:"PUT"});window.location.reload();}catch(e){setError(e.message);setBusy(false);}}
  return <section className="ops-card cycle-settings"><p className="eyebrow">Survey administration</p><h2>Academic year & semester</h2><p>Switching to another semester closes submissions and clears the previous schedule. Historical answers stay in their original cycle.</p>{error&&<p role="alert" className="error">{error}</p>}<form className="ops-actions" onSubmit={create}><label>Academic year<input required pattern="[0-9]{4}-[0-9]{4}" value={year} onChange={e=>setYear(e.target.value)}/></label><label>Semester<select value={semester} onChange={e=>setSemester(e.target.value)}><option>1st</option><option>2nd</option></select></label><button className="btn ghost" disabled={busy}>Create cycle</button></form><div className="ops-actions"><label className="grow">Selected survey cycle<select disabled={!data?.items.length} value={selected} onChange={e=>setSelected(e.target.value)}>{!data?.items.length&&<option value="">Create a cycle first</option>}{data?.items.map(c=><option key={c.id} value={c.id}>{c.label}{c.id===data.active_id?" · Current":""}</option>)}</select></label><button className="btn primary" disabled={busy||!selected||Number(selected)===data?.active_id} onClick={activate}>Use this semester</button></div><p className="muted">Set the schedule and Active toggle in Survey period below.</p></section>;
}
