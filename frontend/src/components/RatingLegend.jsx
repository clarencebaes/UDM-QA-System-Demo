import { RATING_LABELS } from "../ratingLabels";

export function RatingStars({value}) {
  if (!Number.isInteger(value) || value < 1 || value > 5) return <span>Not recorded</span>;
  return <span className="receipt-stars" aria-label={`${value} out of 5 stars: ${RATING_LABELS[value - 1]}`}><span aria-hidden="true">{"★".repeat(value)}<span className="empty-stars">{"☆".repeat(5 - value)}</span></span><span className="rating-value"> {value} of 5 stars</span></span>;
}

export default function RatingLegend() {
  return <aside className="rating-legend" aria-label="Rating legend"><h2>Rating legend</h2><ul>{RATING_LABELS.map((label, index) => <li key={label}><span className="legend-stars" aria-label={`${index + 1} stars`}>{"★".repeat(index + 1)}</span><span>{label}</span></li>)}</ul></aside>;
}
