import { useState } from "react";
import { api, downloadBackup, saveBackup, clearSession, getProfile } from "../../api";
import { roleOf } from "../../permissions";
import { useNotice } from "../../hooks/useNotice";
export default function BackupPage(){
  const [file,setFile]=useState(null),[password,setPassword]=useState(""),[confirmation,setConfirmation]=useState(""),[busy,setBusy]=useState(false),[msg,setMsg]=useState(""),[error,setError]=useState("");
  useNotice(msg);useNotice(error,"error");
  function chooseFile(e){
    const selected=e.target.files[0];setError("");setFile(null);
    if(!selected)return;
    if(!/\.udmbackup$/i.test(selected.name)){setError("Only .udmbackup files from Download encrypted backup are accepted.");e.target.value="";return;}
    if(selected.size>28*1024*1024){setError("Choose a .udmbackup file smaller than 28 MB.");e.target.value="";return;}
    setFile(selected);
  }
  async function download(){setBusy(true);setError("");setMsg("");try{saveBackup(await downloadBackup());setMsg("Encrypted application backup downloaded.");}catch(e){setError(e.message);}finally{setBusy(false);}}
  async function restore(e){e.preventDefault();setBusy(true);setError("");setMsg("");try{
    if(!file||!/\.udmbackup$/i.test(file.name)||file.size>28*1024*1024)throw new Error("Choose a .udmbackup file smaller than 28 MB.");
    saveBackup(await downloadBackup(),"udm-before-restore");
    const result=await api.request("/qa/restore",{method:"POST",body:JSON.stringify({backup:await file.text(),filename:file.name,password,confirmation})});
    saveBackup(result.recovery_backup,"udm-recovery");clearSession();setMsg(result.message);setPassword("");setFile(null);
  }catch(e){setError(e.message);}finally{setBusy(false);}}
  return <div className="ops-page"><p className="eyebrow">Executive Director · Recovery</p><h1>Backup & restore</h1><p>Download or restore an encrypted application backup.</p>{error&&<p className="error" role="alert">{error}</p>}
    <section className="ops-card"><h2>Create backup</h2><p>Includes surveys, responses, accounts, settings, concerns and audit history. Model files and hosting settings require separate backups.</p><button className="btn primary" disabled={busy} onClick={download}>{busy?"Working…":"Download encrypted backup"}</button></section>
    {roleOf(getProfile()) === "executive_director" ? <form className="ops-card form" onSubmit={restore}><h2>Restore application data</h2><p>Only a <strong>.udmbackup</strong> file created by <strong>Download encrypted backup</strong> is accepted. Its encrypted contents must belong to this installation.</p><p>Restore replaces application records, downloads a recovery copy, retains audit history, closes the survey and revokes staff sessions.</p>
      <label>UDMBACKUP file<input type="file" accept=".udmbackup" required onChange={chooseFile}/></label>
      <label>Current password<input type="password" autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)}/></label>
      <label>Type RESTORE to confirm replacement<input required value={confirmation} onChange={e=>setConfirmation(e.target.value)}/></label>
      <button className="btn danger" disabled={busy||confirmation!=="RESTORE"||!file}>Restore selected backup</button>
    </form> : <p>Application restoration is reserved for the Executive Director.</p>}</div>;
}
