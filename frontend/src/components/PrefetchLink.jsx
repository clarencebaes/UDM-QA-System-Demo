import { useEffect, useRef } from "react";
import { Link, NavLink } from "react-router-dom";
import { prefetchPage } from "../pagePrefetch";

export default function PrefetchLink({navigation=false,onPointerEnter,onPointerLeave,onFocus,...props}){
  const timer=useRef(null);
  useEffect(()=>()=>clearTimeout(timer.current),[]);
  const Component=navigation?NavLink:Link;
  return <Component {...props} onPointerEnter={e=>{onPointerEnter?.(e);clearTimeout(timer.current);timer.current=setTimeout(()=>prefetchPage(props.to),120);}}
    onPointerLeave={e=>{clearTimeout(timer.current);onPointerLeave?.(e);}}
    onFocus={e=>{onFocus?.(e);prefetchPage(props.to);}}/>;
}
