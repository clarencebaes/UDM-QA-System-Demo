import SearchSuggestions from "../../components/SearchSuggestions";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import { useSearchParams } from "react-router-dom";
import { auditAction, auditTarget, auditChanges } from "../../auditDescription";
import { useNotice } from "../../hooks/useNotice";
import { CONCERN_TYPES, CONCERN_ACTIONS } from "../../concernTypes";
import RoleBadge from "../../components/RoleBadge";
import Pagination from "../../components/Pagination";
import { formatDate } from "../../formatDate";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, getProfile } from "../../api";
import { ROLE_NAMES, ROLE_DESCRIPTIONS, roleOf } from "../../permissions";
const EMPTY = { username:"", display_name:"", role:"viewer", password:"", confirm_password:"", is_active:true };
const STATUS = { open:"Open", reviewing:"In review", resolved:"Resolved" };
function ConcernStatus({ status }) { return <span className={`concern-status status-${status}`}>{STATUS[status] || status}</span>; }

export default function RecordsPage({ kind }) {
  const [params]=useSearchParams();
  const [saveConfirm,setSaveConfirm]=useState(false);
  const saveDialog=useRef(null);
  useEffect(()=>{if(saveConfirm)saveDialog.current?.showModal();else saveDialog.current?.close();},[saveConfirm]);
  const [deleteConfirm,setDeleteConfirm]=useState(false);
  const eventHandled=useRef(false);
  const [data,setData]=useState(null), [search,setSearch]=useState(()=>params.get("search")||""), [query,setQuery]=useState(()=>params.get("search")||""), [page,setPage]=useState(1);
  const [error,setError]=useState(""), [busy,setBusy]=useState(false), [loading,setLoading]=useState(true), [edit,setEdit]=useState(null), [msg,setMsg]=useState("");
  const liveSearch=useDebouncedValue(search);
  useEffect(()=>{setQuery(liveSearch);setPage(1);},[liveSearch]);
  const [audit,setAudit]=useState(null);
  const auditDialog=useRef(null), requestId=useRef(0);
  const role=roleOf(getProfile());
  const title={users:"Users",concerns:"Student concerns",audit:"Audit trail"}[kind];
  const concernOnly=Boolean(edit);
  const [statusFilter,setStatusFilter]=useState("all");
  const [auditLookups,setAuditLookups]=useState({departments:[],cycles:[]});
  const canReview=role!=="assistant";
  const load=useCallback(async()=>{
    const id=++requestId.current;
    setError("");setLoading(true);
    try { const result=await api.request(`/qa/${kind}?${new URLSearchParams({search:query,page,...(kind==="audit"&&params.get("event_id")?{event_id:params.get("event_id")}:{}) ,...(kind==="concerns"?{status:statusFilter}:{})})}`); if(id===requestId.current)setData(result); }
    catch(err){if(id===requestId.current)setError(err.message);}
    finally {if(id===requestId.current)setLoading(false);}
  },[kind,query,page,statusFilter,params]);
  const invalidate=useCallback(()=>{requestId.current++;},[]);
  useNotice(msg,"success");
  useNotice(error,"error");
  useEffect(()=>{load();return invalidate;},[load,invalidate]);
  const editorKey=edit ? edit.id || "new" : "";
  useEffect(()=>{if(editorKey)window.scrollTo(0,0);},[editorKey]);
  useEffect(()=>{if(kind==="audit")Promise.all([api.departments(),api.request("/qa/cycles")]).then(([departments,cycles])=>setAuditLookups({departments,cycles:cycles.items})).catch(()=>{});},[kind]);
  useEffect(()=>{if(audit) auditDialog.current?.showModal();},[audit]);
  async function save(e, confirmed=false){
    e?.preventDefault();setBusy(true);setError("");setMsg("");
    try {
      if (kind === "users" && !edit.id && edit.password !== edit.confirm_password) throw new Error("Passwords do not match. Re-enter the confirmation password.");
      if (!confirmed) {setSaveConfirm(true);return;}
      const body=kind==="users" ? {username:edit.username,display_name:edit.display_name,role:edit.role,password:edit.password,is_active:edit.is_active} : {status:edit.status,staff_note:edit.staff_note};
      await api.request(`/qa/${kind}${edit.id?`/${edit.id}`:""}`,{method:edit.id?(kind==="users"?"PUT":"PATCH"):"POST",body:JSON.stringify(body)});
      setSaveConfirm(false);setEdit(null);setMsg("Changes saved.");await load();
    } catch(err){setSaveConfirm(false);setError(err.message);} finally {setBusy(false);}
  }
  useEffect(()=>{if(kind==="audit"&&params.get("event_id")&&data&&!eventHandled.current){const row=data.items.find(r=>String(r.id)===params.get("event_id"));if(row){eventHandled.current=true;setAudit(row);}}},[data,params,kind]);
  async function removeConcern(){setBusy(true);setError("");try{await api.request(`/qa/concerns/${edit.id}`,{method:"DELETE"});setDeleteConfirm(false);setEdit(null);setMsg("Concern deleted. Evaluation answers were not changed.");await load();}catch(e){setError(e.message);}finally{setBusy(false);}}
  async function removeUser(){setBusy(true);setError("");try{await api.request(`/qa/users/${edit.id}`,{method:"DELETE"});setDeleteConfirm(false);setEdit(null);setMsg("User deleted. Existing sessions no longer have access. Audit history is retained.");await load();}catch(e){setDeleteConfirm(false);setError(e.message);}finally{setBusy(false);}}
  function closeAudit(){auditDialog.current?.close();setAudit(null);}
  return <div className="ops-page records-page"><p className="eyebrow">{kind==="audit"?"Oversight":"Administration"}</p><h1>{concernOnly?(kind==="users"?edit.id?"Edit user":"Create user":"Student concern"):title}</h1>
    <p>{kind==="users"?"Access hierarchy: Executive Director → Administrator → Staff → Read-Only Viewer. New accounts are active. Use Edit to activate or deactivate an account.":kind==="concerns"?"Review student-reported survey difficulties and record the follow-up action.":"Recorded changes, account activity, report previews and recovery operations. Times are shown in Philippine time."}</p>
    {!concernOnly && <form className="ops-actions" onSubmit={e=>{e.preventDefault();setPage(1);setQuery(search);}}>
      <label className="grow">Search {title.toLowerCase()}<input type="search" list="record-suggestions" value={search} onChange={e=>setSearch(e.target.value)} placeholder={kind==="concerns"?"Reference or student number":kind==="audit"?"Actor, action or record":"Name or username"}/></label>
      <button className="btn primary">Search</button><button type="button" className="btn ghost" onClick={()=>{setSearch("");setQuery("");setPage(1);}}>Clear</button>
      {kind==="users"&&<button type="button" className="btn primary" onClick={()=>setEdit({...EMPTY})}>Create user</button>}
    </form>}
    {!concernOnly&&<SearchSuggestions id="record-suggestions" query={search} values={(loading?[]:data?.items||[]).flatMap(row=>kind==="users"?[row.display_name,row.username]:kind==="concerns"?[row.reference,row.student_number,row.category]:[row.actor,auditAction(row.action),auditTarget(row.target)])}/>}
    {kind==="concerns"&&!concernOnly&&<div className="fb-chips" role="group" aria-label="Concern status">{Object.entries({all:"All",...STATUS}).map(([value,label])=><button type="button" key={value} aria-pressed={statusFilter===value} className={`fb-chip${statusFilter===value?" active":""}`} onClick={()=>{setStatusFilter(value);setPage(1);}}><span className="dot"/>{label}<span className="count">{data?.counts?.[value]||0}</span></button>)}</div>}
    {error&&<p className="error" role="alert">{error}</p>}
    {edit&&<form className="ops-card form" onSubmit={save}><h2>{kind==="concerns"?edit.reference:edit.id?"Edit user":"Create user"}</h2>{kind==="users"?<>
      <label>Display name<input required minLength={2} maxLength={100} value={edit.display_name} onChange={e=>setEdit({...edit,display_name:e.target.value})}/></label>
      <label>Username<input required pattern="[A-Za-z0-9._]{3,32}" value={edit.username} onChange={e=>setEdit({...edit,username:e.target.value})}/></label>
      <label>Role<select value={edit.role} onChange={e=>setEdit({...edit,role:e.target.value})}>{Object.entries(ROLE_NAMES).filter(([r])=>role==="executive_director"||!["super_admin","executive_director"].includes(r)).map(([r,label])=><option key={r} value={r}>{label}</option>)}</select></label>
      <div className="selected-role"><RoleBadge role={edit.role}/><p className="role-description">{ROLE_DESCRIPTIONS[edit.role]}</p></div>
      <label>{edit.id?"New password (leave blank to keep existing)":"Initial password"}<input autoComplete="new-password" type="password" required={!edit.id} value={edit.password} onChange={e=>setEdit({...edit,password:e.target.value})}/></label>
      {edit.password && (edit.password.length<12 || new TextEncoder().encode(edit.password).length>72 || !/[A-Za-z]/.test(edit.password) || !/[0-9]/.test(edit.password)) && <p className="error" role="status">Use at least 12 characters, including letters and numbers, and no more than 72 UTF-8 bytes.</p>}
      {!edit.id && <label>Confirm password<input autoComplete="new-password" type="password" required value={edit.confirm_password} onChange={e=>setEdit({...edit,confirm_password:e.target.value})}/></label>}
      {edit.id && <div><span className="field-caption">Account status</span><div className="fb-chips" role="group" aria-label="Account status">{[[true,"Activated"],[false,"Deactivated"]].map(([value,label])=><button type="button" key={label} aria-pressed={edit.is_active===value} className={`fb-chip account-toggle ${value?"activated":"deactivated"}${edit.is_active===value?" active":""}`} onClick={()=>setEdit({...edit,is_active:value})}>{label}</button>)}</div></div>}
    </>:<>
      <div className="concern-summary"><ConcernStatus status={edit.status}/><p><strong>Submitted:</strong> {formatDate(edit.created_at)}</p><p><strong>Student:</strong> {edit.student_number} · {edit.email}</p><p><strong>Type:</strong> {CONCERN_TYPES[edit.category]||edit.category}</p><p className="preserve-lines">{edit.message}</p></div>
      <label>Status<select aria-describedby="concern-status-help" disabled={!canReview} value={edit.status} onChange={e=>setEdit({...edit,status:e.target.value})}>{Object.entries(STATUS).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label><div id="concern-status-help" className="status-help"><p><strong>Open:</strong> Received and waiting for staff attention.</p><p><strong>In review:</strong> Acknowledged by staff and being checked. Record the investigation or next step.</p><p><strong>Resolved:</strong> Follow-up is complete. Record the outcome before saving.</p></div>
      {edit.status==="resolved"&&<p className="status-help"><strong>Suggested resolution:</strong> {CONCERN_ACTIONS[edit.category]||CONCERN_ACTIONS.other} Record the action actually taken; this suggestion does not resolve the concern automatically.</p>}
      {edit.status!=="open"&&<label>Staff remarks<textarea readOnly={!canReview} required minLength={5} maxLength={2000} rows={5} value={edit.staff_note||""} onChange={e=>setEdit({...edit,staff_note:e.target.value})}/></label>}
    </>}
      <div className="ops-actions">{(kind==="users"||canReview)&&<button className="btn primary" disabled={busy}>{busy?"Saving…":"Save changes"}</button>}<button type="button" className="btn ghost" onClick={()=>{setEdit(null);setError("");}}>Back</button>{kind==="users"&&edit.id&&edit.username!==getProfile().username&&<button type="button" className="btn danger editor-delete" disabled={busy} onClick={()=>setDeleteConfirm(true)}>Delete user</button>}{kind==="concerns"&&canReview&&<button type="button" className="btn danger editor-delete" onClick={()=>setDeleteConfirm(true)}>Delete concern</button>}</div>
    </form>}
    {!concernOnly && (!data?<p role="status">Loading records…</p>:<>
      <div className="ops-table-wrap" aria-busy={loading}><table className={`ops-table ${kind}-table`}>
        {kind==="audit"&&<colgroup><col style={{width:"22%"}}/><col style={{width:"16%"}}/><col style={{width:"23%"}}/><col style={{width:"23%"}}/><col style={{width:"16%"}}/></colgroup>}
        <thead><tr>{(kind==="users"?["Name / username","Role","Status","Action"]:kind==="concerns"?["Reference / date","Student","Concern","Status / remarks","Action"]:["Date","Actor","Action","Record","Changes"]).map(h=><th key={h}>{h}</th>)}</tr></thead>
        <tbody>{data.items.map(row=><tr key={row.id}>{kind==="users"?<>
          <td><strong>{row.display_name}</strong><br/>{row.username}</td><td><RoleBadge role={row.role}/></td><td><span className={`account-status ${row.is_active?"activated":"deactivated"}`}>{row.is_active?"Activated":"Deactivated"}</span></td><td>{(role==="executive_director"||!["super_admin","executive_director"].includes(row.role))&&<button className="btn ghost" onClick={()=>setEdit({...row,password:""})}>Edit</button>}</td>
        </>:kind==="concerns"?<>
          <td>{row.reference}<br/>{formatDate(row.created_at)}</td><td>{row.student_number}<br/>{row.email}</td><td><strong>{CONCERN_TYPES[row.category]||row.category}</strong><p>{row.message}</p></td><td><ConcernStatus status={row.status}/>{row.status!=="open"&&row.staff_note&&<p className="concern-remarks">{row.staff_note}</p>}</td><td><button className="btn primary" onClick={()=>{setEdit(row);setMsg("");}}>View concern</button></td>
        </>:<>
          <td>{formatDate(row.created_at)}</td><td>{row.actor}</td><td>{auditAction(row.action)}</td><td>{auditTarget(row.target)}</td><td><button type="button" className="audit-view-button" onClick={()=>setAudit(row)}>View changes</button></td>
        </>}</tr>)}</tbody></table>{!data.items.length&&<p className="empty-note">No matching records.</p>}</div>
      <div className="fb-tablefoot"><span className="fb-range">{data.total} records</span><Pagination page={data.page||page} pages={Math.max(1,Math.ceil(data.total/20))} onChange={setPage} disabled={loading}/></div>
    </>)}
    {deleteConfirm&&<div className="modal-overlay"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="delete-concern-title"><h2 id="delete-concern-title">{kind==="users"?"Delete this user?":"Delete this concern?"}</h2><p>{kind==="users"?`Permanently delete ${edit?.display_name} (${edit?.username})? They will lose access immediately. Audit history and student evaluations are retained.`:<>This removes {edit?.reference} from the inbox. Its audit history is retained; student evaluations are unaffected.</>}</p><div className="modal-actions"><button className="btn ghost" onClick={()=>setDeleteConfirm(false)}>Back</button><button className="btn danger" disabled={busy} onClick={kind==="users"?removeUser:removeConcern}>{kind==="users"?"Delete user":"Delete concern"}</button></div></section></div>}
    <dialog ref={saveDialog} className="audit-modal" onCancel={()=>setSaveConfirm(false)} aria-labelledby="save-confirm-title">
      <h2 id="save-confirm-title">Save changes?</h2><p>Are you sure you want to {kind==="users"?(edit?.id?"save these account changes":"create this account"):"save these concern changes"}?</p>
      {kind==="users"&&edit&&<><p><strong>{edit.display_name}</strong> · {edit.username}</p><RoleBadge role={edit.role}/><p>{edit.is_active?"Activated":"Deactivated"}</p><p>{ROLE_DESCRIPTIONS[edit.role]}</p></>}
      <div className="modal-actions"><button type="button" className="btn ghost" disabled={busy} onClick={()=>setSaveConfirm(false)}>Cancel</button><button type="button" className="btn primary" disabled={busy} onClick={()=>save(null,true)}>{busy?"Saving…":"Yes, save changes"}</button></div>
    </dialog>
    <dialog ref={auditDialog} className="audit-modal" onCancel={()=>setAudit(null)} aria-labelledby="audit-title">
      <h2 id="audit-title">Recorded changes</h2>{audit&&<><p>{formatDate(audit.created_at)}</p><p><strong>{audit.actor}</strong> · {auditAction(audit.action)} · {auditTarget(audit.target)}</p><ul className="audit-changes">{auditChanges(audit,auditLookups).map((line,index)=><li key={index}>{line}</li>)}</ul></>}
      <button type="button" className="btn primary" onClick={closeAudit}>Close</button>
    </dialog>
  </div>;
}
