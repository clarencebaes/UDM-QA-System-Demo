import { Link } from "react-router-dom";

function Arrow({ previous }) {
  return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true"><polyline points={previous ? "15 18 9 12 15 6" : "9 18 15 12 9 6"} /></svg>;
}

export default function DashboardCardFooter({ page, pages, from, to, total, noun, onPage, href, action, flagged = false }) {
  return <div className="dashboard-card-footer">
    <span className="dashboard-card-range">Showing {from}–{to} of {total} {noun}</span>
    <div className="dashboard-card-navigation">
      <span className="pager-info">Page {page} of {pages}</span>
      <button type="button" className="pager-btn" aria-label="Previous page" disabled={page <= 1} onClick={() => onPage(page - 1)}><Arrow previous /></button>
      <button type="button" className="pager-btn is-next" aria-label="Next page" disabled={page >= pages} onClick={() => onPage(page + 1)}><Arrow /></button>
      <Link to={href} className={flagged ? "flagged-view-intervention" : "dash-full-btn compact"}>{action} →</Link>
    </div>
  </div>;
}
