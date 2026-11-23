export function StarRatings({ rows=[] }) {
  return <div className="ops-table-wrap"><table className="ops-table"><thead><tr>{["Service area","Saved evaluations","1 ★","2 ★","3 ★","4 ★","5 ★","Mean / 5"].map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{rows.map(r=><tr key={r.service_area}><td>{r.service_area}</td><td>{r.evaluations}</td>{[1,2,3,4,5].map(star=><td key={star}>{r.stars[String(star)]||0}</td>)}<td>{r.mean??"—"}</td></tr>)}</tbody></table>{!rows.length&&<p className="empty-note">No ratings in this selection.</p>}</div>;
}
export function StudentStatus({ rows=[] }) {
  const total=rows.reduce((n,r)=>n+r.respondents,0);
  return <div className="student-status-summary">{["regular","irregular","unknown"].filter(status=>status!=="unknown"||rows.some(r=>r.status===status)).map(status=>{const count=rows.find(r=>r.status===status)?.respondents||0;return <div className="status-stat" key={status}><span>{status==="unknown"?"Status not recorded":status==="regular"?"Regular":"Irregular"}</span><strong>{count}</strong><small>{total?Number((count/total*100).toFixed(1)):0}% of respondents</small></div>;})}</div>;
}
