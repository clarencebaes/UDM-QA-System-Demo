export async function loadInterventionWorkspace(api){
  const interventions=await api.interventionWorkspace();
  // Rolling deployments can briefly have an older backend; keep its read order.
  const alerts=Array.isArray(interventions.alerts)?interventions.alerts:await api.alerts();
  return {interventions,alerts};
}
