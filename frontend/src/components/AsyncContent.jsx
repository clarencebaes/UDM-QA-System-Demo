export default function AsyncContent({ resource, label = "data", children }) {
  if (resource.loading) return <p className="empty-note" role="status">Loading {label}…</p>;
  if (resource.error) return <div role="alert"><p className="error">{resource.error}</p><button type="button" className="btn-secondary" onClick={resource.reload}>Retry {label}</button></div>;
  return children;
}
