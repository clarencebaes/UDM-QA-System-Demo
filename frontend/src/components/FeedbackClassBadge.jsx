export default function FeedbackClassBadge({ row }) {
  const category = ["positive", "negative", "constructive", "neutral"].includes(row.sentiment) ? row.sentiment : "unclassified";
  return <span className={`pill ${category === "unclassified" ? "no-substantive" : category}`}>{category.charAt(0).toUpperCase() + category.slice(1)}</span>;
}
