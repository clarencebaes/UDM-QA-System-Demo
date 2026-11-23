import { useState } from "react";
import { Pie, PieChart, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { SENTIMENT_COLORS } from "../sentimentPalette";
import { sentimentDistribution } from "../sentimentDistribution";

const LANGUAGES={english:"English",tagalog:"Tagalog",taglish:"Taglish",undetermined:"Unclassified"};
const LANGUAGE_COLORS={english:"#338578",tagalog:"#ba8c27",taglish:"#7660a8",undetermined:"#a4adb6"};
function Distribution({title,counts,names,colors,filterLabel}){
  const [filter,setFilter]=useState("all");
  const total=Object.values(counts||{}).reduce((a,b)=>a+b,0);
  const rows=Object.entries(names).map(([key,name])=>({key,name,value:counts?.[key]||0})).filter(r=>filter==="all"||r.key===filter);
  const shown=rows.reduce((sum,r)=>sum+r.value,0);
  const plotRows=filter==="all"?rows:[...rows,{key:"other",name:title==="Detected language"?"Other languages":"Other sentiments",value:Math.max(0,total-shown)}];
  return <section className="text-distribution"><div className="text-distribution-head"><h3>{title}</h3><label className="fb-field"><span>{filterLabel}</span><select aria-label={`${filterLabel} distribution filter`} value={filter} onChange={e=>setFilter(e.target.value)}><option value="all">All</option>{Object.entries(names).map(([key,name])=><option key={key} value={key}>{name}</option>)}</select></label></div>
    <div className="text-distribution-content"><div className="text-distribution-chart">{shown?<ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={plotRows} dataKey="value" nameKey="name" innerRadius={58} outerRadius={85} isAnimationActive={false}>{plotRows.map(r=><Cell key={r.key} fill={colors[r.key]||"#e5ebe7"}/>)}</Pie><Tooltip/></PieChart></ResponsiveContainer>:null}<div className="text-donut-center"><strong>{total}</strong><span>written<br/>comments</span></div></div><ul>{rows.map(r=><li key={r.key}><span className="sentiment-dot" style={{background:colors[r.key]}}/><span>{r.name}</span><strong>{r.value}</strong><span>{total?Math.round(r.value/total*100):0}%</span></li>)}<li className="text-distribution-total"><span>Total written comments</span><strong>{total}</strong></li></ul></div></section>;
}
export default function TextDimensions({data,showSentiment=true,showLanguage=true}){
  return <div className={`text-dimensions${showSentiment&&showLanguage?" has-two":""}`}>
    {showSentiment&&<Distribution title="Sentiment" counts={sentimentDistribution(data)} names={{positive:"Positive",constructive:"Constructive",negative:"Negative",neutral:"Neutral",unclassified:"Unclassified"}} colors={SENTIMENT_COLORS} filterLabel="Sentiment"/>}
    {showLanguage&&<Distribution title="Detected language" counts={data?.language_counts} names={LANGUAGES} colors={LANGUAGE_COLORS} filterLabel="Language"/>}
  </div>;
}
