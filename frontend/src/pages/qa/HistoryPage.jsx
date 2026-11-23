import SearchSuggestions from "../../components/SearchSuggestions";
import { formatDate } from "../../formatDate";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import { useState, useCallback, useEffect } from "react";
import { api } from "../../api";
import { useRemoteData } from "../../hooks/useRemoteData";
import AsyncContent from "../../components/AsyncContent";
import FeedbackClassBadge from "../../components/FeedbackClassBadge";
import AspectBadges from "../../components/AspectBadges";

const PAGE_SIZE = 5;
const COMMENT_PAGE_SIZE = 10;

function classLabel(value) {
  if (!value) return "Unclassified";
  return value.charAt(0).toUpperCase() + value.slice(1);
}

const fmtDate = formatDate;

function goalOf(note) {
  const m = /^\[(Short term|Long term)\]/.exec((note || "").trim());
  return m ? m[1] : "Short term";
}

function recText(a) {
  const raw = (a.note || "").trim();
  const m = /^\[(Short term|Long term)\]\s*([\s\S]*)$/.exec(raw);
  if (m) return m[2].trim() || a.recommendation || "";
  return a.recommendation || raw || "";
}

function Chevron({ dir }) {
  const points = dir === "left" ? "15 18 9 12 15 6" : "9 18 15 12 9 6";
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points={points} />
    </svg>
  );
}

export default function HistoryPage() {
  const [search,setSearch]=useState("");
  const query=useDebouncedValue(search);
  useEffect(()=>{setFeedbackPage(1);setAlertsPage(1);},[query]);
  const [sentimentFilter, setSentimentFilter] = useState("all");
  const [feedbackPage, setFeedbackPage] = useState(1);
  const [alertsPage, setAlertsPage] = useState(1);

  const feedbackLoader = useCallback(() => api.feedbackPage({ page: feedbackPage, page_size: COMMENT_PAGE_SIZE, sentiment: sentimentFilter, search:query }), [feedbackPage, sentimentFilter,query]);
  const feedback = useRemoteData(feedbackLoader);
  const alertLoader = useCallback(() => api.alerts("resolved"), []);
  const alertResult = useRemoteData(alertLoader);
  const alerts = alertResult.data || [];
  const total = feedback.data?.total || 0;
  const feedbackTotalPages = Math.max(1, Math.ceil(total / COMMENT_PAGE_SIZE));
  const feedbackSafePage = feedback.data?.page || 1;
  const feedbackPaged = feedback.data?.items || [];
  const fbRangeStart = total === 0 ? 0 : (feedbackSafePage - 1) * COMMENT_PAGE_SIZE + 1;
  const fbRangeEnd = Math.min(feedbackSafePage * COMMENT_PAGE_SIZE, total);

  const completedAlerts = alerts.filter((a) => (a.status === "resolved" || a.status === "completed") && (!query.trim()||[a.department,a.aspect,a.note,a.quad_note,a.completion_note].some(value=>value?.toLowerCase().includes(query.trim().toLowerCase()))));
  const alertsTotalPages = Math.max(1, Math.ceil(completedAlerts.length / PAGE_SIZE));
  const alertsSafePage = Math.min(alertsPage, alertsTotalPages);
  const alertsPaged = completedAlerts.slice(
    (alertsSafePage - 1) * PAGE_SIZE,
    alertsSafePage * PAGE_SIZE
  );
  const ivRangeStart = completedAlerts.length === 0 ? 0 : (alertsSafePage - 1) * PAGE_SIZE + 1;
  const ivRangeEnd = Math.min(alertsSafePage * PAGE_SIZE, completedAlerts.length);


  return (
    <div className="history-page">
      <header className="dash-topbar">
        <div className="dash-topbar-left">
          <h1 className="dash-title">History</h1>
          <p className="dash-subtitle">Every submitted comment and every completed intervention, in one place.</p>
        </div>
      </header>

      <section className="card his-comments-card" aria-busy={feedback.loading}>
        <div className="ana-card-head">
          <div className="ana-card-head-text">
            <h2>Submitted comments</h2>
            <p className="card-desc">All written comments from Feedback, newest first.</p>
          </div>
        </div>
        <label className="history-search">Search history<input type="search" list="history-suggestions" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search comments, service areas, colleges, aspects or completed actions"/></label>
        <SearchSuggestions id="history-suggestions" query={search} values={[...feedbackPaged.flatMap(row=>[row.comment,row.department,row.college]),...completedAlerts.flatMap(row=>[row.department,row.aspect,row.note])]} />
        <div className="fb-chips" role="group" aria-label="History sentiment">{Object.entries({all:"All",positive:"Positive",negative:"Negative",constructive:"Constructive",neutral:"Neutral",unclassified:"Unclassified"}).map(([key,label])=><button type="button" key={key} className={`fb-chip${sentimentFilter===key?" active":""}`} aria-pressed={sentimentFilter===key} onClick={()=>{setSentimentFilter(key);setFeedbackPage(1);}}><span className="dot"/>{label}<span className="count">{feedback.data?.counts?.[key]||0}</span></button>)}</div>

        <div className="history-load-status">{feedback.loading ? <p role="status">Updating submitted comments...</p> : feedback.error ? <AsyncContent resource={feedback} label="submitted comments" /> : null}</div>
        <ul className="his-comment-list">
          {!feedback.loading && !feedback.error && feedbackPaged.length === 0 ? (
            <li className="empty-note">No comments found.</li>
          ) : feedbackPaged.map((f) => (
            <li key={f.id} className="his-comment-item">
              <div className="his-comment-body">
                <p>{f.comment}</p>
                <small>
                  {f.department || "Unknown"}
                  {f.college ? ` · ${f.college}` : ""}
                </small>
                <div className="history-aspects"><AspectBadges row={f} /></div><small className="history-timestamp">{formatDate(f.created_at)}</small>
              </div>
              <FeedbackClassBadge row={f} />
            </li>
          ))}
        </ul>

        <div className="fb-tablefoot">
          <span className="fb-range">Showing {fbRangeStart}–{fbRangeEnd} of {total} comments</span>
          <div className="fb-pager">
            <span className="pager-info">Page {feedbackSafePage} of {feedbackTotalPages}</span>
            <button type="button" className="pager-btn" onClick={() => setFeedbackPage((p) => Math.max(1, p - 1))} disabled={feedback.loading || feedbackSafePage <= 1} aria-label="Previous page">
              <Chevron dir="left" />
            </button>
            <button type="button" className="pager-btn is-next" onClick={() => setFeedbackPage((p) => Math.min(feedbackTotalPages, p + 1))} disabled={feedback.loading || feedbackSafePage >= feedbackTotalPages} aria-label="Next page">
              <Chevron dir="right" />
            </button>
          </div>
        </div>
      </section>

      <section className="card">
        <h2>Completed interventions</h2>
        <p className="muted card-desc">Every intervention the QUAD team has confirmed and completed, newest first.</p>

        <AsyncContent resource={alertResult} label="completed interventions" />
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Service area</th>
                <th>Aspect</th>
                <th>Goal</th>
                <th>Recommendation</th>
                <th>Confirmed</th>
                <th>Completed</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {alertsPaged.length === 0 ? (
                <tr>
                  <td colSpan={7} className="empty-note">No completed interventions yet.</td>
                </tr>
              ) : (
                alertsPaged.map((a) => (
                  <tr key={a.id}>
                    <td>{a.department || "All service areas"}</td>
                    <td><strong>{a.aspect}</strong></td>
                    <td><span className="iv-goal-pill" data-goal={goalOf(a.note)}>{goalOf(a.note)}</span></td>
                    <td>
                      {recText(a)}
                      {a.quad_note ? <small className="his-completion-note"><strong>QUAD note:</strong> {a.quad_note}</small> : null}
                      {a.completion_note ? (
                        <small className="his-completion-note">Completion note: {a.completion_note}</small>
                      ) : null}
                    </td>
                    <td>{fmtDate(a.confirmed_at || a.updated_at || a.created_at)}</td>
                    <td>{fmtDate(a.completed_at || a.updated_at)}</td>
                    <td>
                      <span className={`pill ${a.status === "resolved" ? "resolved" : "in-progress"}`}>
                        {a.status === "resolved" ? "Completed" : classLabel(a.status)}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="fb-tablefoot">
          <span className="fb-range">Showing {ivRangeStart}–{ivRangeEnd} of {completedAlerts.length} completed interventions</span>
          <div className="fb-pager">
            <span className="pager-info">Page {alertsSafePage} of {alertsTotalPages}</span>
            <button type="button" className="pager-btn" onClick={() => setAlertsPage((p) => Math.max(1, p - 1))} disabled={alertsSafePage <= 1} aria-label="Previous page">
              <Chevron dir="left" />
            </button>
            <button type="button" className="pager-btn is-next" onClick={() => setAlertsPage((p) => Math.min(alertsTotalPages, p + 1))} disabled={alertsSafePage >= alertsTotalPages} aria-label="Next page">
              <Chevron dir="right" />
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
