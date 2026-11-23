import { useEffect } from "react";
import { Navigate } from "react-router-dom";

/** Legacy route — consent lives on the home page. */
export default function ConsentPage() {
  useEffect(() => {
    sessionStorage.setItem("udm_scroll_eval", "1");
  }, []);
  return <Navigate to="/" replace />;
}
