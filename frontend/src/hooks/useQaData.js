import { useCallback } from "react";
import { api } from "../api";
import { useRemoteData } from "./useRemoteData";
import { mergeDashboardData } from "../mergeDashboardData";
import { loadInterventionWorkspace } from "../interventionWorkspace";

export function useQaData({ includeAlertContext = false, college = "all", cycle_id = "" } = {}) {
  const loader = useCallback(async () => {
    if (includeAlertContext) {
      return loadInterventionWorkspace(api);
    }
    const [summary,charts]=await Promise.all([api.dashboard({college,cycle_id,section:"summary"}),api.dashboard({college,cycle_id,section:"charts"})]);
    return { dash: mergeDashboardData(summary,charts),scope:{college,cycle_id} };
  }, [includeAlertContext, college, cycle_id]);
  const result = useRemoteData(loader);
  const changingScope=Boolean(result.data&&!includeAlertContext&&(result.data.scope?.college!==college||result.data.scope?.cycle_id!==cycle_id));
  return { ...result,loading:result.loading||changingScope, dash: result.data?.dash, alerts: result.data?.alerts || [],
    interventions: result.data?.interventions || { aspects: [], pairs: [], feedback: [], feedback_total: 0 } };
}
