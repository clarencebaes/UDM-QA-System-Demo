import SearchSuggestions from "../../components/SearchSuggestions";
import PageLoading from "../../components/PageLoading";
import { formatDate } from "../../formatDate";
import { useNotice } from "../../hooks/useNotice";
import { Chevron } from "../../components/Pagination";
import { roleOf } from "../../permissions";
import { Link, useSearchParams } from "react-router-dom";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQaData } from "../../hooks/useQaData";
import { api, getProfile } from "../../api";
import { useRemoteData } from "../../hooks/useRemoteData";
import AsyncContent from "../../components/AsyncContent";
import { SENTIMENT_COLORS } from "../../sentimentPalette";

const SERVICE_AREA_PAGE_SIZE = 10;
const FOLLOW_UP_PAGE_SIZE = 5;
const OPEN = new Set(["new", "acknowledged", "in-progress"]);

function levelLabel(level) {
  if (level === "high") return "High";
  if (level === "medium") return "Medium";
  return "Low";
}

function parseNote(note, fallback) {
  const raw = (note || "").trim();
  const m = /^\[(Short term|Long term)\]\s*([\s\S]*)$/.exec(raw);
  if (m) return { goal: m[1], text: m[2].trim() };
  return { goal: "Short term", text: raw || fallback || "" };
}

const fmtShortDate = formatDate;

function SentimentCounts({ negative = 0, constructive = 0 }) {
  return <div className="iv-comment-counts">
    {negative > 0 ? <span className="iv-sentiment-count iv-neg">{negative} negative</span> : null}
    {constructive > 0 ? <span className="iv-sentiment-count iv-constructive">{constructive} constructive</span> : null}
  </div>;
}

function AreaColumns(){return <colgroup><col className="iv-col-area" /><col className="iv-col-aspect" /><col className="iv-col-count" /><col className="iv-col-count" /><col className="iv-col-priority" /></colgroup>;}
function AreaHead({accessibleOnly=false}){return <thead className={accessibleOnly?"iv-accessible-head":""}>
                <tr>
                  <th scope="col" rowSpan={2}>Service area</th>
                  <th scope="col" rowSpan={2}>Aspect</th>
                  <th scope="colgroup" colSpan={2} className="iv-count-heading">Comments in this area</th>
                  <th scope="col" rowSpan={2}>Service priority</th>
                </tr>
                <tr><th scope="col" className="iv-count-heading">Negative</th><th scope="col" className="iv-count-heading">Constructive</th></tr>
              </thead>;}

export default function AlertsPage() {
  const role = roleOf(getProfile());
  const followupRef=useRef(null);
  const canApprove = role === "executive_director";
  const canComplete = canApprove || role === "admin";
  const [params] = useSearchParams();
  const { alerts, interventions, data, error, loading, reload } = useQaData({ includeAlertContext: true });
  const [search,setSearch] = useState("");
  const [areaFilter, setAreaFilter] = useState("all");
  const [aspectFilter, setAspectFilter] = useState("all");
  const [priorityFilter, setPriorityFilter] = useState("all");
  const [page, setPage] = useState(1);
  const initialArea = params.get("service_area");
  const initialAspect = params.get("aspect");
  const [selectedPair, setSelectedPair] = useState(() => initialArea && initialAspect ? { service_area: initialArea, aspect: initialAspect } : null);
  const initialSelectionHandled = useRef(false);
  const [goal, setGoal] = useState("Short term");
  const [recommendation, setRecommendation] = useState("");
  const [quadNote, setQuadNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [busyRowId, setBusyRowId] = useState(null);
  const [recPage, setRecPage] = useState(1);
  const [rules, setRules] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [surveySettings, setSurveySettings] = useState({ min_trigger_count: 3, alert_window_days: 14 });
  const [followTab, setFollowTab] = useState("awaiting");
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const [followNotice, setFollowNotice] = useState("");
  const [followError, setFollowError] = useState("");
  const [editingDraft,setEditingDraft]=useState(null);
  const [draftText,setDraftText]=useState("");
  const [draftGoal,setDraftGoal]=useState("Short term");
  const [draftRemarks,setDraftRemarks]=useState("");
  const actionHandled=useRef(false);
  const [updating,setUpdating]=useState(null);
  const [progressNote,setProgressNote]=useState("");
  const [completing, setCompleting] = useState(null);
  const [completionNote, setCompletionNote] = useState("");
  const [viewing, setViewing] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  useNotice(notice,"success");
  useNotice(followNotice,"success");
  useNotice(actionError,"error");
  useNotice(followError,"error");
  useEffect(() => {
    api.departments().then(setDepartments).catch((err) => setActionError(err.message));
    api.surveySettings().then(setSurveySettings).catch((err) => setActionError(err.message));
  }, []);

  useEffect(() => {
    const refresh = () => {
      if (document.visibilityState === "hidden") return;
      reload();
      api.surveySettings().then(setSurveySettings).catch(err => setActionError(err.message));
    };
    window.addEventListener("focus", refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener("focus", refresh);
      window.removeEventListener("storage", refresh);
    };
  }, [reload]);

  const aspects = [...new Set(interventions.pairs.flatMap(pair=>pair.aspect_names||[pair.aspect]))];
  const alertedPairs = useMemo(()=>interventions.pairs.filter(pair=>{const action=alerts.find(a=>a.id===pair.alert_id);return !action?.note?.trim()&&action?.status==="new";}),[interventions.pairs,alerts]);
  useEffect(()=>{const id=Number(params.get("action_id"));if(!id||actionHandled.current||!alerts.length)return;const action=alerts.find(a=>a.id===id);if(action){actionHandled.current=true;setFollowTab(action.status==="resolved"?"completed":action.status==="in-progress"?"confirmed":"awaiting");setViewing(action);}},[params,alerts]);

  useEffect(() => {
    if (initialSelectionHandled.current || !initialArea || !initialAspect || !alertedPairs.length) return;
    initialSelectionHandled.current = true;
    const index = alertedPairs.findIndex(pair => pair.service_area === initialArea && pair.aspect === initialAspect);
    if (index >= 0) setPage(Math.floor(index / SERVICE_AREA_PAGE_SIZE) + 1);
  }, [alertedPairs, initialArea, initialAspect]);

  const serviceAreas = useMemo(
    () =>
      [...new Set(alertedPairs.map((r) => r.service_area).filter(Boolean))].sort((a, b) =>
        a.localeCompare(b)
      ),
    [alertedPairs],
  );

  const filteredPairs = useMemo(() => {
    return alertedPairs.filter((r) => {
      if (areaFilter !== "all" && r.service_area !== areaFilter) return false;
      if (aspectFilter !== "all" && !(r.aspect_names||[r.aspect]).includes(aspectFilter)) return false;
      if (priorityFilter !== "all" && r.level !== priorityFilter) return false;
      const alert = alerts.find(a=>a.id===r.alert_id);
      return !search.trim() || [r.service_area,r.aspect,alert?.note,alert?.recommendation,alert?.quad_note].some(value=>value?.toLowerCase().includes(search.trim().toLowerCase()));
    });
  }, [alertedPairs, alerts, areaFilter, aspectFilter, priorityFilter, search]);

  const pageCount = Math.max(1, Math.ceil(filteredPairs.length / SERVICE_AREA_PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const paged = filteredPairs.slice((safePage - 1) * SERVICE_AREA_PAGE_SIZE, safePage * SERVICE_AREA_PAGE_SIZE);

  useEffect(() => {
    setPage(1);
  }, [aspectFilter, priorityFilter, areaFilter, search]);

  // Pagination browses the list without replacing the current detail/editor.
  // A different row or filter changes the selection explicitly.
  const focus = useMemo(() => {
    if (
      selectedPair &&
      filteredPairs.some(
        (r) => r.service_area === selectedPair.service_area && r.aspect === selectedPair.aspect,
      )
    ) {
      return selectedPair;
    }
    const first = filteredPairs[0];
    return first ? { service_area: first.service_area, aspect: first.aspect } : null;
  }, [selectedPair, filteredPairs]);

  const focusedPair = alertedPairs.find((r) => r.service_area === focus?.service_area && r.aspect === focus?.aspect);
  const detailLoader = useCallback(() => focusedPair
    ? api.interventionDetail(focusedPair.service_area, focusedPair.aspect_code) : Promise.resolve(null),
    [focusedPair]);
  const detail = useRemoteData(detailLoader);
  const aspectSummary = interventions.aspects.find((aspect) => aspect.service_area === focusedPair?.service_area);
  const matchingAlert = alerts.find((alert) => alert.id === focusedPair?.alert_id) || null;
  const feedbackNegative = aspectSummary?.negative || 0;
  const feedbackConstructive = aspectSummary?.constructive || 0;
  const aspectLevel = aspectSummary?.level || "medium";
  const windowDays = aspectSummary?.window_days || surveySettings.alert_window_days;

  const parsed = parseNote(matchingAlert?.note, matchingAlert?.recommendation || "");
  const initialGoal = matchingAlert?.note && (!matchingAlert.department || matchingAlert.department === focus?.service_area) ? parsed.goal : surveySettings.default_goal === "long_term" ? "Long term" : "Short term";

  useEffect(() => {
    setGoal(initialGoal);
  }, [matchingAlert?.id, initialGoal]);

  // intervention_rules.aspect_id is UNIQUE, so each aspect has exactly one
  // default rule — matching by aspect_code is unambiguous. Disabled rules are
  // never suggested.
  useEffect(() => {
    if (Array.isArray(interventions.rules)) setRules(interventions.rules);
    else api.rules().then(setRules).catch(err => setActionError(err.message));
  }, [interventions.rules]);

  const matchedRule = useMemo(() => {
    if (!matchingAlert || !focusedPair) return null;
    const codes=focusedPair.aspect_codes||[matchingAlert.aspect_code];
    const selected=rules.filter(r=>codes.includes(r.aspect_code)&&r.is_active!==false);
    if(!selected.length)return null;
    return {items:selected,recommendation:[...new Set(selected.map(r=>r.recommendation))].join("\n\n"),diagnosed_pattern:selected.map(r=>r.diagnosed_pattern).filter(Boolean).join("; ")};
  }, [rules, matchingAlert, focusedPair]);

  const focusDeptId = useMemo(() => {
    if (!focus) return null;
    const dept = departments.find((d) => d.name === focus.service_area);
    return dept ? dept.id : null;
  }, [departments, focus]);

  // Restore saved drafts only. Suggestions enter the editor only through Apply.
  const lastPrefillKey = useRef(null);
  useEffect(() => {
    const key = `${matchingAlert?.id ?? "none"}|${focus?.service_area ?? "none"}`;
    const sameScope = !matchingAlert?.department || matchingAlert.department === focus?.service_area;
    const saved = sameScope ? parseNote(matchingAlert?.note, "").text : "";
    if (lastPrefillKey.current !== key) setQuadNote(sameScope ? matchingAlert?.quad_note || "" : "");
    if (lastPrefillKey.current !== key) {
      setRecommendation(saved || "");
      lastPrefillKey.current = key;
    }
  }, [matchingAlert?.id, matchingAlert?.note, matchingAlert?.department, matchingAlert?.quad_note, focus?.service_area]);

  // ── Recommendations & follow-up buckets ───────────────────────────
  // Awaiting approval: a draft was saved but never approved.
  const awaitingRecs = useMemo(
    () =>
      (alerts || [])
        .filter(
          (a) =>
            (a.status === "new" || a.status === "acknowledged") &&
            parseNote(a.note, "").text,
        )
        .sort(
          (a, b) =>
            new Date(b.updated_at || b.created_at || 0) -
            new Date(a.updated_at || a.created_at || 0),
        ),
    [alerts],
  );
  // Confirmed / in progress: approved, awaiting implementation.
  const activeRecs = useMemo(
    () =>
      (alerts || [])
        .filter((a) => a.status === "in-progress")
        .sort(
          (a, b) =>
            new Date(b.confirmed_at || b.updated_at || 0) -
            new Date(a.confirmed_at || a.updated_at || 0),
        ),
    [alerts],
  );
  // Completed: the team confirmed the action was actually carried out.
  const doneRecs = useMemo(
    () =>
      (alerts || [])
        .filter((a) => a.status === "resolved" || a.status === "completed")
        .sort(
          (a, b) =>
            new Date(b.completed_at || b.updated_at || 0) -
            new Date(a.completed_at || a.updated_at || 0),
        ),
    [alerts],
  );

  const followRows = (followTab === "awaiting" ? awaitingRecs : followTab === "confirmed" ? activeRecs : doneRecs)
    .filter(a=>!search.trim() || [a.aspect,a.department,a.note,a.quad_note,a.completion_note].some(value=>value?.toLowerCase().includes(search.trim().toLowerCase())));
  const recPageCount = Math.max(1, Math.ceil(followRows.length / FOLLOW_UP_PAGE_SIZE));
  const recSafePage = Math.min(recPage, recPageCount);
  const recPaged = followRows.slice((recSafePage - 1) * FOLLOW_UP_PAGE_SIZE, recSafePage * FOLLOW_UP_PAGE_SIZE);
  const recRangeStart = followRows.length === 0 ? 0 : (recSafePage - 1) * FOLLOW_UP_PAGE_SIZE + 1;
  const recRangeEnd = Math.min(recSafePage * FOLLOW_UP_PAGE_SIZE, followRows.length);
  const followColCount = followTab === "awaiting" ? 6 : followTab === "confirmed" ? 7 : 8;

  const openAlert = matchingAlert && OPEN.has(matchingAlert.status) ? matchingAlert : null;

  const editableDraft = canComplete && matchingAlert && ["new","acknowledged"].includes(matchingAlert.status);

  // Save draft: stores the recommendation without approving it. Only a
  // brand-new alert moves to "acknowledged"; an approved one stays approved.
  async function saveDraft() {
    if (!editableDraft || recommendation.trim().length < 10) return;
    setSaving(true);
    setNotice("");
    setActionError("");
    try {
      const nextStatus = openAlert.status === "new" ? "acknowledged" : undefined;
      await api.patchAlert(
        openAlert.id,
        nextStatus,
        `[${goal}] ${recommendation.trim()}`,
        { ...(focusDeptId ? { department_id: focusDeptId } : {}), quad_note: quadNote.trim() },
      );
      setFollowTab("awaiting");setRecPage(1);
      await reload();
      setNotice("Draft saved and listed under Awaiting approval.");
      requestAnimationFrame(()=>followupRef.current?.scrollIntoView({behavior:"smooth",block:"start"}));
    } catch (err) {
      setActionError(err.message);
    } finally {
      setSaving(false);
    }
  }

  // Approve: validates, saves, stamps confirmed_at, moves to follow-up.
  // Approval never completes — Mark complete is a separate step.
  async function approveRecommendation() {
    if (!editableDraft || recommendation.trim().length < 10) return;
    setSaving(true);
    setNotice("");
    setActionError("");
    try {
      await api.patchAlert(
        openAlert.id,
        "in-progress",
        `[${goal}] ${recommendation.trim()}`,
        { ...(focusDeptId ? { department_id: focusDeptId } : {}), quad_note: quadNote.trim() },
      );
      setFollowTab("confirmed");setRecPage(1);
      await reload();
      setNotice("Recommendation approved and moved to follow-up.");
    } catch (err) {
      setActionError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function approveRow(a) {
    const text = parseNote(a.note, "").text;
    if (!text) return;
    setBusyRowId(a.id);
    setFollowNotice("");
    setFollowError("");
    try {
      const dept = departments.find((d) => d.name === a.department);
      await api.patchAlert(a.id, "in-progress", undefined, dept ? { department_id: dept.id } : {});
      setFollowTab("confirmed");setRecPage(1);
      await reload();
      setFollowNotice(`Approved: ${a.aspect} moved to follow-up.`);
    } catch (err) {
      setFollowError(err.message);
    } finally {
      setBusyRowId(null);
    }
  }

  async function saveEditedDraft(e){
    e.preventDefault();if(!editingDraft)return;setBusyRowId(editingDraft.id);setFollowError("");setFollowNotice("");
    try{await api.patchAlert(editingDraft.id,undefined,`[${draftGoal}] ${draftText.trim()}`,{quad_note:draftRemarks.trim()});setEditingDraft(null);await reload();setFollowNotice("Draft updated in Awaiting approval.");}catch(err){setFollowError(err.message);}finally{setBusyRowId(null);}
  }

  async function saveProgress(e) {
    e.preventDefault();if(!updating)return;
    setBusyRowId(updating.id);setFollowError("");setFollowNotice("");
    try {
      await api.patchAlert(updating.id,undefined,undefined,{quad_note:progressNote.trim()});
      setUpdating(null);await reload();
      setFollowNotice("Progress updated. Included in intervention reports.");
    } catch(err){setFollowError(err.message);} finally {setBusyRowId(null);}
  }

  async function completeRow() {
    if (!completing) return;
    setBusyRowId(completing.id);
    setFollowNotice("");
    setFollowError("");
    try {
      await api.patchAlert(
        completing.id,
        "resolved",
        undefined,
        completionNote.trim() ? { completion_note: completionNote.trim() } : {},
      );
      await reload();
      setCompleting(null);
      setCompletionNote("");
      setFollowTab("completed");
      setRecPage(1);
      setFollowNotice(`Marked complete: ${completing.aspect}. It now appears in History.`);
    } catch (err) {
      setFollowError(err.message);
    } finally {
      setBusyRowId(null);
    }
  }

  async function deleteRow() {
    if (!deleteConfirm) return;
    setDeleting(deleteConfirm.id);
    setFollowNotice("");
    setFollowError("");
    try {
      await api.deleteAlert(deleteConfirm.id);
      await reload();
      setDeleting(null);
      setDeleteConfirm(null);
      setViewing(null);
      setFollowNotice(`Deleted: ${deleteConfirm.aspect}. Removed from interventions and history.`);
    } catch (err) {
      setFollowError(err.message);
    } finally {
      setDeleting(null);
    }
  }

  if (loading && !data) return <PageLoading title="Interventions" message="Loading interventions…"/>;
  if (error) return <div className="ops-page"><h1>Interventions</h1><p className="error" role="alert">{error}</p><button className="btn primary" onClick={reload}>Retry interventions</button></div>;

  const rangeStart = filteredPairs.length === 0 ? 0 : (safePage - 1) * SERVICE_AREA_PAGE_SIZE + 1;
  const rangeEnd = Math.min(safePage * SERVICE_AREA_PAGE_SIZE, filteredPairs.length);

  return (
    <div className="iv-page" style={{ "--iv-negative": SENTIMENT_COLORS.negative, "--iv-constructive": SENTIMENT_COLORS.constructive }}>
      <header className="fb-page-head">
        <h1>Interventions</h1>
        <p>Review service-area concerns and track recommended actions.</p>
      </header>

      <form className="iv-search ops-actions" onSubmit={e=>e.preventDefault()}><label className="grow">Search interventions<input type="search" list="intervention-suggestions" value={search} onChange={e=>{setSearch(e.target.value);setRecPage(1);}} placeholder="Search service area, aspect, recommendation or action"/></label><button type="button" className="btn ghost" onClick={()=>setSearch("")}>Clear</button></form>
      <SearchSuggestions id="intervention-suggestions" query={search} values={[...alertedPairs.flatMap(row=>[row.service_area,...(row.aspect_names||[])]),...alerts.flatMap(row=>[row.department,row.aspect,row.note])]} />
      {actionError ? <p className="error" role="alert">{actionError}</p> : null}
      <div className={`iv-top-grid${alertedPairs.length ? "" : " iv-top-grid-empty"}`}>
        <section className="dash-card iv-areas-card">
          <div className="card-header">
            <h2 className="card-title">Needs a recommendation</h2>
            <p className="card-desc">
              One entry per service area. Review its combined comments and prepare an action.
            </p>
          </div>

          <div className="iv-area-filters">
            <label className="fb-field">
              <span>Service area</span>
              <select value={areaFilter} onChange={(e) => setAreaFilter(e.target.value)}>
                <option value="all">All service areas</option>
                {serviceAreas.map((a) => (
                  <option key={a} value={a}>{a}</option>
                ))}
              </select>
            </label>
            <label className="fb-field">
              <span>Aspect</span>
              <select value={aspectFilter} onChange={(e) => setAspectFilter(e.target.value)}>
                <option value="all">All aspects</option>
                {aspects.map((a) => (
                  <option key={a} value={a}>{a}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="fb-chips iv-priority-chips" role="group" aria-label="Intervention priority">{[["all","All priorities"],["high","High"],["medium","Medium"]].map(([value,label])=><button key={value} type="button" aria-pressed={priorityFilter===value} className={`fb-chip${priorityFilter===value?" active":""}`} onClick={()=>setPriorityFilter(value)}><span className="dot"/>{label}</button>)}</div>

          <div className="iv-area-table-shell"><div className="iv-area-header" aria-hidden="true"><table className="iv-table iv-area-table"><AreaColumns/><AreaHead/></table></div>
          <div className="iv-area-body-scroll" role="region" tabIndex={0} aria-label="Service area recommendations">
            <table className="iv-table iv-area-table">
              <AreaColumns/>
              <AreaHead accessibleOnly/>
              <tbody>
                {paged.length === 0 ? (
                  <tr><td colSpan={5} className="empty-note">{alertedPairs.length ? "No service areas match your filters." : "No concerns need a new recommendation right now. New concerns appear here when they meet the configured alert threshold."}</td></tr>
                ) : paged.map((r) => (
                  <tr
                    key={`${r.service_area}-${r.aspect}`}
                    className={focus && focus.service_area === r.service_area && focus.aspect === r.aspect ? "selected" : ""}
                    onClick={() => setSelectedPair({ service_area: r.service_area, aspect: r.aspect })}
                  >
                    <td className="cell-area">{r.service_area}</td>
                    <td title={r.aspect}>{r.aspect_names?.length>1?`${r.aspect_names.length} reported aspects`:r.aspect}</td>
                    <td className="iv-count-cell"><span className="iv-sentiment-count iv-neg" aria-label={`${r.negative} negative comments`}>{r.negative}</span></td>
                    <td className="iv-count-cell"><span className="iv-sentiment-count iv-constructive" aria-label={`${r.constructive} constructive comments`}>{r.constructive}</span></td>
                    <td><span className={`iv-priority ${r.level}`}>{levelLabel(r.level)}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          </div>

          <div className="fb-tablefoot">
            <span className="fb-range">Showing {rangeStart}–{rangeEnd} of {filteredPairs.length} service areas</span>
            <div className="fb-pager">
              <span className="pager-info">Page {safePage} of {pageCount}</span>
              <button type="button" className="pager-btn" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={safePage <= 1} aria-label="Previous page">
                <Chevron dir="left" />
              </button>
              <button type="button" className="pager-btn is-next" onClick={() => setPage((p) => Math.min(pageCount, p + 1))} disabled={safePage >= pageCount} aria-label="Next page">
                <Chevron dir="right" />
              </button>
            </div>
          </div>
        </section>

        <section className="dash-card iv-alert-card">
          <span className="fb-eyebrow">Alert details</span>
          {focus ? (
            <>
              <div className="iv-alert-title">
                <h2>{focus.service_area}</h2>
                <span className={`iv-priority ${aspectLevel}`}>{levelLabel(aspectLevel)} priority</span>
              </div>
              <p className="iv-priority-rule">{feedbackNegative} negative and {feedbackConstructive} constructive comments in this service area within {windowDays} days.</p>

              <dl className="iv-meta">
                <div className="iv-meta-row"><dt>Service area</dt><dd>{focus.service_area}</dd></div>
                <div className="iv-meta-row">
                  <dt>Aspect</dt>
                  <dd>{focus.aspect}</dd>
                </div>
                <div className="iv-meta-row">
                  <dt>Concern</dt>
                  <dd>
                    <div className="iv-evidence-panel"><AsyncContent resource={detail} label="selected-area comments">
                      <p className="iv-concern-summary"><strong>{detail.data?.count || 0} comments</strong> about {focus.aspect} in <strong>{focus.service_area}</strong> within the last {windowDays} days.</p>
                      <SentimentCounts negative={detail.data?.negative} constructive={detail.data?.constructive} />
                      <h3 className="iv-evidence-label">Recent comments from this area</h3>
                      <div className="iv-comment-evidence">
                        {(detail.data?.examples || []).map(item => <blockquote key={item.id} className={`iv-evidence-${item.sentiment}`}>{item.text}</blockquote>)}
                      </div>
                    </AsyncContent></div>
                  </dd>
                </div>
                <div className="iv-meta-row">
                  <dt>Suggested intervention</dt>
                  <dd>
                    {matchedRule ? (
                      <div className="iv-suggested">{matchedRule.items.map(rule=><div className="iv-rule-suggestion" key={rule.id}><h3>{focusedPair.aspect_names?.[focusedPair.aspect_codes?.indexOf(rule.aspect_code)] || rule.aspect_code.replaceAll("_", " ")}</h3><p>{rule.recommendation}</p></div>)}</div>
                    ) : (
                      <p className="empty-note">
                        No active intervention rule matches this aspect. Add one in Settings → Intervention
                        Rules, or write a recommendation manually below.
                      </p>
                    )}
                    <p className="muted">Apply fills the editor. Save draft moves this concern to Awaiting approval.</p>
                    <div className="iv-suggestion-actions">
                      <Link className="btn ghost" to="/qa/settings#intervention-rules">Change in Settings</Link>
                      <button type="button" className="btn primary" disabled={!editableDraft || !matchedRule} onClick={() => {setRecommendation(matchedRule.recommendation);setNotice("Suggestion applied. Review it, then Save draft to move it to Awaiting approval.");}}>Apply</button>
                    </div>
                  </dd>
                </div>
                <div className="iv-meta-row iv-rec-row">
                  <dt>Recommendation</dt>
                  <dd>
                    <textarea
                      rows={4}
                      readOnly={!editableDraft}
                      value={recommendation}
                      onChange={(e) => setRecommendation(e.target.value)}
                      placeholder="Write the recommendation for this concern."
                    />
                  </dd>
                </div>
                <div className="iv-meta-row iv-quad-note-row">
                  <dt><label htmlFor="iv-quad-note">QUAD note</label></dt>
                  <dd><textarea id="iv-quad-note" readOnly={!editableDraft} rows={2} maxLength={4000} value={quadNote} onChange={e => setQuadNote(e.target.value)} placeholder="Optional note for follow-up and history." /></dd>
                </div>
                <div className="iv-meta-row iv-goal-row">
                  <dt id="iv-goal-label">Goal</dt>
                  <dd>
                    <div className="seg-toggle goal-toggle" role="group" aria-labelledby="iv-goal-label">
                      <button
                        type="button"
                        aria-pressed={goal === "Short term"}
                        className={goal === "Short term" ? "is-active" : ""}
                        onClick={() => setGoal("Short term")}
                        disabled={saving || !editableDraft}
                      >
                        Short term
                      </button>
                      <button
                        type="button"
                        aria-pressed={goal === "Long term"}
                        className={goal === "Long term" ? "is-active" : ""}
                        onClick={() => setGoal("Long term")}
                        disabled={saving || !editableDraft}
                      >
                        Long term
                      </button>
                    </div>
                  </dd>
                </div>
              </dl>

              {!openAlert ? (
                <p className="empty-note">
                  This alert is already completed. New alerts appear when thresholds in Settings are
                  breached again.
                </p>
              ) : null}
              <div className="iv-actions">
                <button
                  type="button"
                  className="btn ghost"
                  onClick={saveDraft}
                  disabled={!editableDraft || saving || recommendation.trim().length < 10}
                >
                  {saving ? "Saving…" : "Save draft"}
                </button>
                <button
                  type="button"
                  className="btn primary"
                  onClick={approveRecommendation}
                  disabled={!canApprove || !editableDraft || saving || recommendation.trim().length < 10}
                  title={!canApprove ? "Executive Director approval required" : ""}
                >
                  {saving ? "Saving…" : "Approve recommendation"}
                </button>
              </div>
            </>
          ) : (
            <p className="empty-note">{alertedPairs.length ? "Select a matching service area to see its comments and suggested action." : "Find saved drafts and approved interventions in Recommendations & follow-up below."}</p>
          )}
        </section>

      </div>

      <section ref={followupRef} className="dash-card iv-confirmed-card">
        <div className="card-header">
          <div>
            <h2 className="card-title">Recommendations &amp; follow-up</h2>
            <p className="card-desc">
              Saved drafts await approval. Approved actions remain in progress until completion is recorded.
            </p>
          </div>
        </div>

        <div className="iv-tabs" role="tablist" aria-label="Recommendation follow-up">
          <button
            type="button"
            role="tab"
            aria-selected={followTab === "awaiting"}
            className={`iv-tab${followTab === "awaiting" ? " is-active" : ""}`}
            onClick={() => { setFollowTab("awaiting"); setRecPage(1); }}
          >
            Awaiting approval <span className="iv-tab-count">{awaitingRecs.length}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={followTab === "confirmed"}
            className={`iv-tab${followTab === "confirmed" ? " is-active" : ""}`}
            onClick={() => { setFollowTab("confirmed"); setRecPage(1); }}
          >
            Confirmed / in progress <span className="iv-tab-count">{activeRecs.length}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={followTab === "completed"}
            className={`iv-tab${followTab === "completed" ? " is-active" : ""}`}
            onClick={() => { setFollowTab("completed"); setRecPage(1); }}
          >
            Completed <span className="iv-tab-count">{doneRecs.length}</span>
          </button>
        </div>

        {followError ? <p className="error">{followError}</p> : null}

        <div className="table-wrap">
          <table className="iv-table">
            <thead>
              <tr>
                <th>Service area</th>
                <th>Aspect</th>
                <th>Recommendation</th>
                <th>Goal</th>
                {followTab !== "awaiting" ? <th>Confirmed</th> : null}
                {followTab === "completed" ? <th>Completed</th> : null}
                <th>Status</th>
                <th aria-label="Action"></th>
              </tr>
            </thead>
            <tbody>
              {recPaged.length === 0 ? (
                <tr>
                  <td colSpan={followColCount} className="empty-note">
                    {followTab === "awaiting"
                      ? "No recommendations waiting for approval."
                      : followTab === "confirmed"
                        ? "No approved recommendations in follow-up yet."
                        : "Nothing marked complete yet. Completed actions also appear in History."}
                  </td>
                </tr>
              ) : recPaged.map((a) => {
                const info = parseNote(a.note, a.recommendation);
                const text = (info.text || a.recommendation || "").trim();
                return (
                  <tr key={a.id}>
                    <td className="cell-area">{a.department || "All service areas"}</td>
                    <td><strong>{a.aspect}</strong></td>
                    <td className="iv-rec-text">
                      {text || <span className="empty-note">Not written yet — open this alert in Alert details.</span>}
                      {a.quad_note ? <small className="iv-quad-note"><strong>QUAD note:</strong> {a.quad_note}</small> : null}
                    </td>
                    <td><span className="iv-goal-pill" data-goal={info.goal}>{info.goal}</span></td>
                    {followTab !== "awaiting" ? <td>{fmtShortDate(a.confirmed_at || a.updated_at)}</td> : null}
                    {followTab === "completed" ? <td>{fmtShortDate(a.completed_at || a.updated_at)}</td> : null}
                    <td>
                      <span className={`pill ${followTab === "awaiting" ? "constructive" : followTab === "confirmed" ? "in-progress" : "resolved"}`}>
                        {followTab === "awaiting" ? "Awaiting approval" : followTab === "confirmed" ? "In progress" : "Completed"}
                      </span>
                    </td>
                    <td className="iv-rec-action">
                      {followTab === "awaiting" ? (
                        <div className="iv-progress-actions"><button type="button" className="btn ghost" disabled={!canComplete} onClick={()=>{setEditingDraft(a);setDraftText(parseNote(a.note,"").text);setDraftGoal(parseNote(a.note,"").goal);setDraftRemarks(a.quad_note||"");setFollowError("");}}>Edit draft</button><button
                          type="button"
                          className="dash-full-btn compact"
                          onClick={() => approveRow(a)}
                          disabled={!canApprove || busyRowId === a.id || !text}
                          title={!canApprove ? "Executive Director approval required" : text ? "" : "Write the recommendation in Alert details first."}
                        >
                          {busyRowId === a.id ? "Approving…" : "Approve"}
                        </button></div>
                      ) : followTab === "confirmed" ? (
                        <div className="iv-progress-actions"><button type="button" className="btn ghost" disabled={!canComplete||busyRowId===a.id} onClick={()=>{setUpdating(a);setProgressNote(a.quad_note||"");setFollowError("");}}>Update progress</button><button
                          type="button"
                          className="dash-full-btn compact"
                          onClick={() => { setCompletionNote(""); setFollowError(""); setCompleting(a); }}
                          disabled={!canComplete || busyRowId === a.id}
                        >
                          Mark complete
                        </button></div>
                      ) : (
                        <button
                          type="button"
                          className="btn ghost"
                          onClick={() => setViewing(a)}
                        >
                          View details
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="fb-tablefoot">
          <span className="fb-range">Showing {recRangeStart}–{recRangeEnd} of {followRows.length} {followTab === "awaiting" ? "recommendations awaiting approval" : followTab === "confirmed" ? "confirmed recommendations" : "completed recommendations"}</span>
          <div className="fb-pager">
            <span className="pager-info">Page {recSafePage} of {recPageCount}</span>
            <button type="button" className="pager-btn" onClick={() => setRecPage((p) => Math.max(1, p - 1))} disabled={recSafePage <= 1} aria-label="Previous page">
              <Chevron dir="left" />
            </button>
            <button type="button" className="pager-btn is-next" onClick={() => setRecPage((p) => Math.min(recPageCount, p + 1))} disabled={recSafePage >= recPageCount} aria-label="Next page">
              <Chevron dir="right" />
            </button>
          </div>
        </div>
      </section>

      {editingDraft&&<div className="modal-overlay"><form className="modal" role="dialog" aria-modal="true" aria-labelledby="draft-title" onSubmit={saveEditedDraft}><h3 id="draft-title">Edit saved draft</h3><p>{editingDraft.department||"All service areas"} · {editingDraft.aspect}</p><label className="fb-field"><span>Recommendation</span><textarea autoFocus required minLength={10} maxLength={4000} rows={5} value={draftText} onChange={e=>setDraftText(e.target.value)}/></label><label className="fb-field"><span>Goal</span><select value={draftGoal} onChange={e=>setDraftGoal(e.target.value)}><option>Short term</option><option>Long term</option></select></label><label className="fb-field"><span>QUAD remarks</span><textarea rows={3} maxLength={4000} value={draftRemarks} onChange={e=>setDraftRemarks(e.target.value)}/></label>{followError&&<p className="error">{followError}</p>}<div className="modal-actions"><button type="button" className="btn ghost" onClick={()=>setEditingDraft(null)}>Back</button><button className="btn primary" disabled={busyRowId===editingDraft.id}>Save draft</button></div></form></div>}
      {updating&&<div className="modal-overlay" onClick={()=>setUpdating(null)}><form className="modal" role="dialog" aria-modal="true" aria-labelledby="progress-title" onClick={e=>e.stopPropagation()} onSubmit={saveProgress}><h3 id="progress-title">Update intervention progress</h3><p>{updating.department||"All service areas"} · {updating.aspect}</p><p>{parseNote(updating.note,"").text}</p><label className="fb-field"><span>Progress remarks</span><textarea autoFocus required minLength={10} maxLength={4000} rows={5} value={progressNote} onChange={e=>setProgressNote(e.target.value)} placeholder="Describe the work underway and next steps."/></label>{followError&&<p className="error" role="alert">{followError}</p>}<div className="modal-actions"><button type="button" className="btn ghost" onClick={()=>setUpdating(null)}>Back</button><button className="btn primary" disabled={busyRowId===updating.id}>Save progress</button></div></form></div>}

      {/* Mark complete — records completion date + optional notes */}
      {completing ? (
        <div className="modal-overlay" onClick={() => setCompleting(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Mark complete?</h3>
            <p>
              Confirm the action for <strong>{completing.aspect}</strong>
              {completing.department ? ` in ${completing.department}` : ""} has actually been carried out.
              It will move to Completed and appear in History.
            </p>
            <label className="iv-complete-notes">
              Action taken (required, at least 10 characters)
              <textarea
                rows={3}
                value={completionNote}
                onChange={(e) => setCompletionNote(e.target.value)}
                placeholder="What was done, and by whom?"
              />
            </label>
            {followError ? <p className="error">{followError}</p> : null}
            <div className="modal-actions">
              <button type="button" className="btn ghost" onClick={() => setCompleting(null)}>Cancel</button>
              <button type="button" className="btn primary" onClick={completeRow} disabled={busyRowId === completing.id || completionNote.trim().length < 10}>
                {busyRowId === completing.id ? "Saving…" : "Mark complete"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {/* View details for a completed recommendation */}
      {viewing && !deleteConfirm ? (
        <div className="modal-overlay" onClick={() => setViewing(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>{viewing.status==="resolved"?"Completed intervention":"Intervention details"}</h3>
            <div className="iv-kv">
              <div className="row"><span className="k">Service area</span><span className="v">{viewing.department || "All service areas"}</span></div>
              <div className="row"><span className="k">Aspect</span><span className="v">{viewing.aspect}</span></div>
              <div className="row"><span className="k">Goal</span><span className="v">{parseNote(viewing.note, viewing.recommendation).goal}</span></div>
              <div className="row"><span className="k">Recommendation</span><span className="v">{parseNote(viewing.note, viewing.recommendation).text || "\u2014"}</span></div>
              <div className="row"><span className="k">Confirmed</span><span className="v">{fmtShortDate(viewing.confirmed_at || viewing.updated_at)}</span></div>
              <div className="row"><span className="k">Completed</span><span className="v">{fmtShortDate(viewing.completed_at || viewing.updated_at)}</span></div>
              <div className="row"><span className="k">QUAD note</span><span className="v">{viewing.quad_note || "\u2014"}</span></div>
              <div className="row"><span className="k">Action taken</span><span className="v">{viewing.completion_note || "\u2014"}</span></div>
              <div className="row"><span className="k">Status</span><span className="v"><span className="pill">{viewing.status==="resolved"?"Completed":viewing.status==="in-progress"?"Approved / in progress":"Awaiting approval"}</span></span></div>
            </div>
            <div className="modal-actions">
              {role === "executive_director" && viewing.status==="resolved" && <button type="button" className="btn danger" onClick={() => setDeleteConfirm(viewing)}>Delete</button>}
              <button type="button" className="btn ghost" onClick={() => setViewing(null)}>Close</button>
            </div>
          </div>
        </div>
      ) : null}

      {/* Delete confirmation modal */}
      {deleteConfirm ? (
        <div className="modal-overlay" onClick={() => setDeleteConfirm(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Delete recommendation?</h3>
            <p>
              This will remove the completed intervention for <strong>{deleteConfirm.aspect}</strong>
              {deleteConfirm.department ? ` in ${deleteConfirm.department}` : ""}
              {" "}from both Interventions and History. This cannot be undone.
            </p>
            {followError ? <p className="error">{followError}</p> : null}
            <div className="modal-actions">
              <button type="button" className="btn ghost" onClick={() => setDeleteConfirm(null)}>Cancel</button>
              <button type="button" className="btn danger" onClick={deleteRow} disabled={deleting === deleteConfirm.id}>
                {deleting === deleteConfirm.id ? "Deleting…" : "Delete"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
