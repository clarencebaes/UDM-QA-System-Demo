export function utcDate(value) {
  if (!value) return null;
  if (value instanceof Date) return Number.isNaN(value.getTime())?null:value;
  const text=String(value);
  const date=new Date(/(?:Z|[+-]\d{2}:?\d{2})$/.test(text)?text:`${text}Z`);
  return Number.isNaN(date.getTime())?null:date;
}
export function formatDate(value) {
  const date=utcDate(value);
  return date?date.toLocaleString("en-PH",{timeZone:"Asia/Manila"}):"—";
}
export function philippineDay(value=new Date()) {
  const date=utcDate(value);
  return date?date.toLocaleDateString("en-CA",{timeZone:"Asia/Manila"}):"";
}
