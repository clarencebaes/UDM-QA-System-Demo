import { useDebouncedValue } from "../hooks/useDebouncedValue";
import { useCallback, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useRemoteData } from "../hooks/useRemoteData";
import AsyncContent from "./AsyncContent";
export default function DashboardSearch({ cycle, college }) {
  const [text,setText]=useState("");
  const debounced=useDebouncedValue(text);
  const query=debounced.trim().length>=2?debounced.trim():"";
  const loader=useCallback(()=>{
    if(!query)return Promise.resolve(null);
    const params=new URLSearchParams({q:query,college});if(cycle)params.set("cycle_id",cycle);
    return api.request(`/qa/search?${params}`);
  },[query,cycle,college]);
  const results=useRemoteData(loader);
  return <section className="dash-card dashboard-search-card"><form className="ops-actions" onSubmit={e=>{e.preventDefault();}}>
    <label className="grow">Search the system<input type="search" minLength={2} maxLength={120} value={text} onChange={e=>setText(e.target.value)} placeholder="Search pages, evaluations, interventions and records available to your role"/></label>
    <button className="btn primary">Search</button><button type="button" className="btn ghost" onClick={()=>{setText("");}}>Clear</button>
  </form>{query&&query===text.trim()&&<AsyncContent resource={results} label="search results"><p>{results.data?.total||0} matches across the areas available to your role. Evaluation results follow the selected semester and college.</p>{results.data?.groups.map(group=><section className="system-search-group" key={group.label}><h3>{group.label} <span className="count">{group.total}</span></h3><ul className="dashboard-search-results">{group.items.map((item,i)=><li key={i}><Link to={item.url}>{item.title}</Link><p>{item.description}</p></li>)}</ul>{group.total>group.items.length&&<Link to={group.url}>View more {group.label.toLowerCase()}</Link>}</section>)}</AsyncContent>}</section>;
}
