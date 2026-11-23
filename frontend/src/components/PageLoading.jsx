export default function PageLoading({title,message}){
  return <div className="ops-page page-loading" aria-busy="true"><h1>{title}</h1><p role="status">{message}</p><div className="page-loading-grid" aria-hidden="true"><div/><div/></div></div>;
}
