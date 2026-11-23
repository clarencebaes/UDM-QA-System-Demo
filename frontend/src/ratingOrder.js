export function sortRatingRows(rows=[],order="service") {
  return [...rows].sort((a,b)=>{
    if(order!=="service") {
      if(a.mean==null&&b.mean!=null)return 1;
      if(b.mean==null&&a.mean!=null)return -1;
      const difference=(a.mean??0)-(b.mean??0);
      if(difference)return order==="highest"?-difference:difference;
    }
    return a.service_area.localeCompare(b.service_area);
  });
}
