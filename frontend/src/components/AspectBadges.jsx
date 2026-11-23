export default function AspectBadges({ row }) {
  const names = Array.isArray(row?.aspects) ? row.aspects : row?.aspect && row.aspect !== "N/A" ? [row.aspect] : [];
  if (!names.length) return <span className="aspect-na">N/A</span>;
  return <span className="aspect-badges">{names.map(name => <span className="aspect-badge" key={name}>{name}</span>)}</span>;
}
