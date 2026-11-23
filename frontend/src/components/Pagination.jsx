export function Chevron({ dir }) {
  return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points={dir === "left" ? "15 18 9 12 15 6" : "9 18 15 12 9 6"} /></svg>;
}

export default function Pagination({ page, pages, onChange, disabled = false }) {
  return <div className="fb-pager">
    <span className="pager-info">Page {page} of {pages}</span>
    <button type="button" className="pager-btn" aria-label="Previous page" disabled={disabled || page <= 1} onClick={() => onChange(page - 1)}><Chevron dir="left" /></button>
    <button type="button" className="pager-btn is-next" aria-label="Next page" disabled={disabled || page >= pages} onClick={() => onChange(page + 1)}><Chevron dir="right" /></button>
  </div>;
}
