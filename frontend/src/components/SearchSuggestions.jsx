export default function SearchSuggestions({ id, query, values=[] }) {
  const term=query.trim().toLowerCase();
  if(!term)return null;
  const matches=[...new Set(values.filter(value=>typeof value==="string"&&value.toLowerCase().includes(term)).map(value=>value.trim()))].slice(0,8);
  return <datalist id={id}>{matches.map(value=><option key={value} value={value}/>)}</datalist>;
}
