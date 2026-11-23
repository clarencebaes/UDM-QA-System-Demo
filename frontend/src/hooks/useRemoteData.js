import { useNotice } from "./useNotice";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, clearSession, getToken } from "../api";

// A stable loader gives each card its own lifecycle, error and retry action.
export function useRemoteData(loader) {
  const navigate = useNavigate();
  const [state, setState] = useState({ data: null, loading: true, error: "" });
  const serial = useRef(0);
  const invalidate = useCallback(() => { serial.current++; }, []);
  const run = useCallback(async (fresh=false) => {
    if(fresh)api.invalidateReads();
    const request = ++serial.current;
    setState(previous => ({ ...previous, loading: true, error: "" }));
    try {
      const data = await loader();
      if (request === serial.current) setState({ data, loading: false, error: "" });
    } catch (error) {
      if (request !== serial.current) return;
      if (/log in|expired|Unauthorized|401/i.test(error.message)) {
        clearSession();
        navigate("/qa/login");
      }
      setState({ data: null, loading: false, error: error.message });
    }
  }, [loader, navigate]);
  const reload=useCallback(()=>run(true),[run]);
  useEffect(() => {
    if (!getToken()) {
      navigate("/qa/login");
      return;
    }
    run();
    return invalidate;
  }, [run, navigate, invalidate]);
  useNotice(state.error,"error");
  return { ...state, reload };
}
