// Short-lived, bounded memory only. Session changes and successful writes clear it.
export function createReadCache({now=Date.now,ttlMs=20_000,maxEntries=100}={}) {
  const entries=new Map();
  function clear(){entries.clear();}
  function read(key,fetcher,{ttl=ttlMs}={}){
    const old=entries.get(key);
    if(old?.pending)return old.pending;
    if(old&&now()<old.expires)return Promise.resolve(old.value);
    const entry={expires:0};
    entries.delete(key);entries.set(key,entry);
    while(entries.size>maxEntries)entries.delete(entries.keys().next().value);
    entry.pending=Promise.resolve().then(fetcher).then(value=>{
      if(entries.get(key)===entry){entry.value=value;entry.expires=now()+ttl;entry.pending=null;}
      return value;
    },error=>{if(entries.get(key)===entry)entries.delete(key);throw error;});
    return entry.pending;
  }
  return {read,clear};
}

export function readKey(path,scope=""){
  const [base,query=""]=path.split("?");const params=new URLSearchParams(query);params.sort();
  return `${scope}\n${base}?${params}`;
}
