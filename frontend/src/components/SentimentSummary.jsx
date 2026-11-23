import TextDimensions from "./TextDimensions";
export default function SentimentSummary({data,label="all colleges",loading=false,controls=null,analysis}) {
  return <section className="dash-card sentiment-summary"><div className="sentiment-summary-head"><h2>Comment sentiment distribution</h2>{controls&&<div className="sentiment-controls">{controls}</div>}</div>
    <p className="card-desc">Positive, Constructive, Negative, Neutral and Unclassified comments for {label}.</p>
    {loading?<p role="status">Loading comment analysis…</p>:<TextDimensions data={analysis||data} showLanguage={false}/>}
  </section>;
}
