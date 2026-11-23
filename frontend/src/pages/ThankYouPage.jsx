import RatingLegend, { RatingStars } from "../components/RatingLegend";
import { formatDate } from "../formatDate";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api } from "../api";
import { referenceWasShown, markReferenceShown } from "../receiptReference";
export default function ThankYouPage() {
  const {state} = useLocation();
  const [showReference] = useState(() => !referenceWasShown(sessionStorage.getItem("udm_receipt")));
  const [receipt, setReceipt] = useState(null), [error, setError] = useState("");
  useEffect(() => { let active = true; const token = sessionStorage.getItem("udm_receipt");
    if (!token) { setError("No receipt is available in this tab. Report a concern if you need help with your submission."); return; }
    api.receipt(token).then(data => {if(active) {markReferenceShown(token); setReceipt(data);}}).catch(err => {if(active) setError(err.message);});
    return () => {active=false;};
  }, []);
  return <main className="ops-page receipt-page"><p className="eyebrow">Student evaluation receipt</p><h1>{receipt ? "Thank you. Your evaluation was received." : "Your evaluation summary"}</h1>
    {state?.alreadyAnswered && <p role="status">You have already answered this semester. Your recorded receipt is shown below.</p>}
    {error ? <p role="alert" className="error">{error}</p> : !receipt ? <p role="status">Loading your recorded answers…</p> : <>
      <section className="ops-card"><h2>{receipt.cycle.label}</h2>
        {showReference ? <div className="receipt-reference"><h3>Your reference number</h3><p><strong>{receipt.reference}</strong></p><p role="note">Save or take a screenshot of this reference number now. It is shown only once in this browser tab. After you reload or leave this page, the number is hidden. Keep it if you need to contact QUAD.</p></div> : <p className="receipt-reference-note">Your reference number was shown on the first confirmation screen and is now hidden. Your recorded answers remain available in this protected browser tab.</p>}
        <dl className="receipt-details">{Object.entries({"Student number":receipt.student_number,"Institutional email":receipt.institutional_email,College:receipt.college,"Student status":receipt.student_status,"Submitted on":formatDate(receipt.submitted_at)}).map(([k,v])=><div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl></section>
      <h2>Your recorded answers</h2><RatingLegend/>
      {receipt.answers.map(a => <section className="ops-card" key={a.service_area}><h3>{a.service_area}</h3><ol>{a.ratings.map((r,i)=><li key={i}>{a.questions[i] || `Question ${i+1}`} <RatingStars value={r}/></li>)}</ol><p><strong>Comment:</strong> {a.comment || "No comment provided."}</p></section>)}
    </>}
    <p>If you have a concern about your answers, you may <Link to="/concern">report a concern</Link>. This is optional.</p><div className="ops-actions receipt-finish"><Link className="btn primary" to="/">Finish</Link></div></main>;
}
