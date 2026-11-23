import { api, getProfile, getToken } from "./api";
import { can, roleOf } from "./permissions";

// Intent-based GETs only: never preview reports, submit forms, or create backups.
export function prefetchPage(path){
  if(!getToken())return Promise.resolve();
  const role=roleOf(getProfile());
  const routes={
    "/qa/dashboard":["dashboard",()=>[api.dashboard({section:"summary"}),api.dashboard({section:"charts"}),api.surveySettings(),api.interventions()]],
    "/qa/analytics":["analytics",()=>[api.dashboard({section:"summary"}),api.dashboard({section:"charts"}),api.request("/qa/cycles")]],
    "/qa/alerts":["alerts",()=>[api.interventionWorkspace(),api.rules(),api.departments(),api.surveySettings()]],
    "/qa/feedback-log":["feedback",()=>[api.feedbackPage({page:1,page_size:10,search:"",comments_only:true,cycle_id:"",department:"all",college:"all",aspect:"all",sentiment:"all"}),api.feedbackOptions({cycle_id:""}),api.mostCommented({page:1,page_size:4,department:"all",cycle_id:""})]],
    "/qa/history":["history",()=>[api.feedbackPage({page:1,page_size:10,sentiment:"all",search:""}),api.alerts("resolved")]],
    "/qa/reports":["reports",()=>[api.request("/qa/cycles"),api.colleges(),api.departments()]],
    "/qa/settings":["settings",()=>[api.headcounts(),api.colleges(),api.surveySettings(),api.aspects(),api.rules(),api.request("/qa/cycles")]],
    "/qa/users":["users",()=>[api.request("/qa/users?search=&page=1")]],
    "/qa/concerns":["concerns",()=>[api.request("/qa/concerns?search=&page=1&status=all")]],
    "/qa/audit":["audit",()=>[api.request("/qa/audit?search=&page=1"),api.departments(),api.request("/qa/cycles")]],
  };
  const entry=routes[path];
  return entry&&can(role,entry[0])?Promise.allSettled(entry[1]()):Promise.resolve();
}
