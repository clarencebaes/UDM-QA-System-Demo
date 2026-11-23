import { philippineDay } from "../../formatDate";
import SentimentSummary from "../../components/SentimentSummary";
import DashboardSearch from "../../components/DashboardSearch";
import CycleSelect from "../../components/CycleSelect";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Pie, PieChart, ResponsiveContainer, Tooltip, Cell } from "recharts";
import { useRemoteData } from "../../hooks/useRemoteData";
import AsyncContent from "../../components/AsyncContent";
import DashboardCardFooter from "../../components/DashboardCardFooter";
import { api } from "../../api";
import { participationSummary } from "../../participation";

const PAGE_SIZE = 8;

const C = {
  green: "#0d3b2e",
  greenDark: "#0b3b2a",
  gold: "#c9a227",
  comments: "#7d9b88",
  positive: "#5f8f72",
  constructive: "#c4a035",
  negative: "#a45d4a",
  neutral: "#87aade",
  barMuted: "#9bb0a6",
};

const pct = (n, d) => (d > 0 ? Math.round((n / d) * 1000) / 10 : 0);
const fmtInt = (v) => (v === null || v === undefined ? "—" : Number(v).toLocaleString());

function fmtDate(v) {
  if (!v) return "—";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

// Parse a calendar day into local midnight so date-only values never shift
// across timezones (e.g. "2026-10-31" parsed as UTC would land on Oct 30 in
// some zones).
function parseDay(v) {
  if(!v)return null;
  const day=typeof v==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(v)?v:philippineDay(v);
  if(!day)return null;
  const [year,month,date]=day.split("-").map(Number);
  return new Date(year,month-1,date);
}
function startOfToday() { return parseDay(philippineDay()); }

function dayKey(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function dayDiff(later, earlier) {
  return Math.round((later.getTime() - earlier.getTime()) / (1000 * 60 * 60 * 24));
}

function niceMax(value) {
  if (value <= 10) return 10;
  const padded = Math.ceil(value * 1.05);
  const mag = 10 ** Math.max(0, String(Math.floor(padded)).length - 2);
  const step = mag < 5 ? 5 : mag;
  return Math.max(step, Math.ceil(padded / step) * step);
}

export default function Dashboard() {
  const [cycle, setCycle] = useState("");
  const [college, setCollege] = useState("all");
  const [flaggedPageState, setFlaggedPage] = useState(1);
  const [mostCommentedPageState, setMostCommentedPage] = useState(1);
  const [serviceAreaPageState, setServiceAreaPage] = useState(1);
  const [facilityFilter, setFacilityFilter] = useState("all");
  const [showFilter, setShowFilter] = useState("all");
  const summaryLoader = useCallback(() => api.dashboard({ college, cycle_id: cycle, section: "summary" }), [college, cycle]);
  const chartLoader = useCallback(() => api.dashboard({ college, cycle_id: cycle, section: "charts" }), [college, cycle]);
  const issueLoader = useCallback(() => api.interventions(college, flaggedPageState), [college, flaggedPageState]);
  const settingsLoader = useCallback(() => api.surveySettings(), []);
  const summary = useRemoteData(summaryLoader);
  const charts = useRemoteData(chartLoader);
  const issues = useRemoteData(issueLoader);
  const settings = useRemoteData(settingsLoader);
  const dash = summary.data;
  const surveySettings = settings.data;
  const settingsLoaded = !settings.loading && !settings.error;

  const selectedCollege = useMemo(
    () => (dash?.by_college || []).find((c) => c.college === college),
    [dash?.by_college, college]
  );

  const totalResponses = college === "all"
    ? (dash?.unique_respondents ?? 0)
    : (selectedCollege?.responses ?? 0);

  const enrolledStudents = college === "all"
    ? (dash?.overall_enrolled ?? 0)
    : (selectedCollege?.enrolled ?? 0);

  const commentsCount = college === "all"
    ? (dash?.total_comments ?? dash?.by_college?.reduce((sum, c) => sum + (c.comments || 0), 0) ?? 0)
    : (selectedCollege?.comments ?? 0);

  const participation = participationSummary(totalResponses, enrolledStudents);
  const notYetResponded = participation.remaining;
  const pieTotal = participation.denominator;

  const pieData = useMemo(() => [
    { name: "Responded", value: totalResponses, color: C.greenDark },
    { name: "Not yet responded", value: notYetResponded, color: C.gold },
  ], [totalResponses, notYetResponded]);

  const byDept = useMemo(() => (charts.data?.by_department || [])
    .map(d => ({ name: d.department || "Unknown", comments: d.comments ?? d.count ?? 0 }))
    .sort((a, b) => b.comments - a.comments), [charts.data]);
  const byServiceArea = useMemo(() => charts.data?.by_service_area || [], [charts.data]);

  const facilityOptions = useMemo(
    () => byServiceArea.map((d) => d.service_area).sort((a, b) => a.localeCompare(b)),
    [byServiceArea]
  );

  const filteredServiceAreas = useMemo(() => {
    const list = facilityFilter === "all"
      ? byServiceArea
      : byServiceArea.filter((d) => d.service_area === facilityFilter);
    return list
      .map((d) => {
        const visible = {
          ...d,
          positive: showFilter === "all" || showFilter === "positive" ? d.positive : 0,
          constructive: showFilter === "all" || showFilter === "constructive" ? d.constructive : 0,
          negative: showFilter === "all" || showFilter === "negative" ? d.negative : 0,
        };
        visible.neutral=showFilter === "all" || showFilter === "neutral" ? (d.neutral||0) : 0;
        visible.total = visible.positive + visible.constructive + visible.negative + visible.neutral;
        return visible;
      })
      .sort((a, b) => b.total - a.total);
  }, [byServiceArea, facilityFilter, showFilter]);

  const flaggedPreview = issues.data?.feedback || [];
  const flaggedTotal = issues.data?.feedback_total || 0;
  const flaggedPage = issues.data?.feedback_page || 1;
  const flaggedPages = Math.max(1, Math.ceil(flaggedTotal / 2));
  const flaggedFrom = flaggedTotal ? (flaggedPage - 1) * 2 + 1 : 0;
  const flaggedTo = Math.min(flaggedPage * 2, flaggedTotal);
  const collegeLabel = college === "all" ? "All colleges" : college;

  const mostCommentedTotalPages = Math.max(1, Math.ceil(byDept.length / PAGE_SIZE));
  const mostCommentedPage = Math.min(mostCommentedPageState, mostCommentedTotalPages);
  const mostCommentedPaged = byDept.slice((mostCommentedPage - 1) * PAGE_SIZE, mostCommentedPage * PAGE_SIZE);
  const serviceAreaTotalPages = Math.max(1, Math.ceil(filteredServiceAreas.length / PAGE_SIZE));
  const serviceAreaPage = Math.min(serviceAreaPageState, serviceAreaTotalPages);
  const serviceAreaPaged = filteredServiceAreas.slice((serviceAreaPage - 1) * PAGE_SIZE, serviceAreaPage * PAGE_SIZE);

  const barMax = niceMax(Math.max(0, ...filteredServiceAreas.map((d) => d.total)));
  const ticks = [0, barMax / 2, barMax].map((n) => Math.round(n));
  const maxCommented = byDept[0]?.comments || 1;

  // ── Survey metrics ────────────────────────────────────────────────
  // Authoritative source: the survey schedule saved in Settings.
  // Response timestamps are only used for "Response days".
  const surveyStart = useMemo(() => parseDay(surveySettings?.start_date), [surveySettings?.start_date]);
  const surveyEnd = useMemo(() => parseDay(surveySettings?.end_date), [surveySettings?.end_date]);
  // "Today" — refreshed when the calendar day rolls over so a dashboard left
  // open overnight does not show a stale remaining-day count.
  const [today, setToday] = useState(() => startOfToday());
  useEffect(() => {
    const tick = setInterval(() => {
      const next = startOfToday();
      setToday((prev) => (dayKey(prev) === dayKey(next) ? prev : next));
    }, 60 * 1000);
    return () => clearInterval(tick);
  }, []);

  // Survey period: the configured window, never the first/last response.
  const surveyPeriodLabel =
    surveyStart && surveyEnd
      ? `${fmtDate(surveyStart)} – ${fmtDate(surveyEnd)}`
      : surveyStart
        ? `From ${fmtDate(surveyStart)}`
        : surveyEnd
          ? `Until ${fmtDate(surveyEnd)}`
          : "—";

  // Status: the Active/Inactive toggle, combined with the schedule.
  const surveyActive = useMemo(() => {
    if (surveySettings?.is_active === false) return false;
    if (!surveySettings) return false;
    if (surveyStart && today < surveyStart) return false;
    if (surveyEnd && today > surveyEnd) return false;
    return true;
  }, [surveySettings, surveyStart, surveyEnd, today]);

  // Remaining days: calendar days left until the survey end date.
  // The end date itself counts as a remaining day, so Oct 22 with an
  // end date of Oct 31 leaves 10 days (22, 23, ... 31 inclusive).
  // Once the survey has ended it is 0.
  const remainingDays = useMemo(() => {
    if (!surveyEnd) return null;
    return Math.max(0, dayDiff(surveyEnd, today) + 1);
  }, [surveyEnd, today]);

  // Response days: distinct calendar days that actually received responses.
  // The backend's `by_day` breakdown is one entry per calendar day, so the
  // number of distinct dates is the number of response days.
  const responseDays = summary.loading || summary.error ? null : (dash?.by_day || []).length;

  function changeCollege(value) {
    setCollege(value);
    setFlaggedPage(1);
    setMostCommentedPage(1);
    setServiceAreaPage(1);
    setFacilityFilter("all");
  }


  const mostFrom = byDept.length ? (mostCommentedPage - 1) * PAGE_SIZE + 1 : 0;
  const mostTo = Math.min(mostCommentedPage * PAGE_SIZE, byDept.length);
  const saFrom = filteredServiceAreas.length ? (serviceAreaPage - 1) * PAGE_SIZE + 1 : 0;
  const saTo = Math.min(serviceAreaPage * PAGE_SIZE, filteredServiceAreas.length);

  return (
    <div className="dashboard-page">
      <header className="dash-topbar dashboard-header">
        <div className="dash-topbar-left">
          <h1 className="dash-title">Dashboard</h1>
          <p className="dash-subtitle">A quick look at the survey, by college.</p>
        </div>
        <div className="dash-topbar-right">
          <section className="dash-stats">
            <div className="dash-stat">
              <span className="dash-stat-label">Survey period</span>
              <span className="dash-stat-value">{surveyPeriodLabel}</span>
            </div>
            <div className="dash-stat"><span className="dash-stat-label">Semester</span><span className="dash-stat-value">{settings.loading?"—":surveySettings?.active_cycle?.label||"No active semester"}</span></div>
            <div className="dash-stat">
              <span className="dash-stat-label">Status</span>
              {settingsLoaded ? (
                <span className={`dash-status ${surveyActive ? "is-active" : "is-inactive"}`}>
                  {surveyActive ? "Active" : "Inactive"}
                </span>
              ) : (
                <span className="dash-stat-value">—</span>
              )}
            </div>
            <div className="dash-stat">
              <span className="dash-stat-label">Response days</span>
              <span className="dash-stat-value">{fmtInt(responseDays)}</span>
            </div>
            <div className="dash-stat">
              <span className="dash-stat-label">Remaining Days</span>
              <span className="dash-stat-value">{remainingDays !== null ? remainingDays : "—"}</span>
            </div>
          </section>

        </div>
      </header>

      {summary.error ? <AsyncContent resource={summary} label="summary" /> : null}
      {settings.error ? <AsyncContent resource={settings} label="survey settings" /> : null}
      <DashboardSearch cycle={cycle} college={college} />
      <div className="kpi-row">
        <div className="kpi-card">
          <div className="kpi-label">Total responses</div>
          <div className="kpi-value">{summary.loading ? "…" : summary.error ? "—" : fmtInt(totalResponses)}</div>
          <div className="kpi-sub">Students who responded</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Enrolled students</div>
          <div className="kpi-value">{summary.loading ? "…" : summary.error ? "—" : fmtInt(enrolledStudents)}</div>
          <div className="kpi-sub">
            {college === "all" ? "Expected respondents across colleges" : `Expected respondents for ${college}`}
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Comments</div>
          <div className="kpi-value">{summary.loading ? "…" : summary.error ? "—" : fmtInt(commentsCount)}</div>
          <div className="kpi-sub">
            {college === "all" ? "Collected across all colleges" : `Collected for ${college}`}
          </div>
        </div>
      </div>

      <SentimentSummary data={dash} loading={summary.loading} totalComments={commentsCount} controls={<><CycleSelect value={cycle} onChange={setCycle} />
          <div className="dash-college-filter">
            <label className="dash-college-label" htmlFor="college-filter">College</label>
            <select
              id="college-filter"
              className="dash-college-select"
              value={college}
              onChange={(e) => changeCollege(e.target.value)}
            >
              <option value="all">All colleges</option>
              {(dash?.by_college || []).map((c) => (
                <option key={c.college} value={c.college}>{c.college}</option>
              ))}
            </select>
          </div></>} label={collegeLabel.toLowerCase()=== "all colleges"?"all colleges":collegeLabel}/>
      <div className="dashboard-main-grid">
        <section className="dash-card survey-breakdown-card">
          <div className="card-header">
            <h2 className="card-title">Survey breakdown of {collegeLabel}</h2>
            <p className="card-desc">{college === "all" ? "Student participation across all colleges, based on university enrollment." : `Student participation in ${college}, based on its enrolled students.`}</p>
          </div>
          <AsyncContent resource={summary} label="participation">
          <div className="survey-breakdown-content">
            <div className="pie-chart-container">
              {!participation.valid ? (
                <p className="empty-note">{enrolledStudents > 0
                  ? "Enrollment is below the recorded respondent count. Update the enrollment headcount."
                  : "Set enrollment headcounts to calculate participation percentages."}</p>
              ) : <ResponsiveContainer width="100%" height={240}>
                <PieChart>
                  <Pie
                    data={pieData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={65}
                    outerRadius={100}
                    stroke="none"
                  >
                    {pieData.map((entry) => (
                      <Cell key={entry.name} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value, name) => [fmtInt(value), name]} />
                </PieChart>
              </ResponsiveContainer>}
            </div>
            <div className="pie-legend">
              {pieData.map((entry) => (
                <div key={entry.name} className="pie-legend-item">
                  <span className="pie-legend-dot" style={{ backgroundColor: entry.color }} />
                  <span className="pie-legend-text">
                    <strong>{participation.valid ? `${pct(entry.value, pieTotal)}%` : "N/A"}</strong> {entry.name} · {fmtInt(entry.value)}
                  </span>
                </div>
              ))}
            </div>
          </div>
          </AsyncContent>
        </section>

        <section className="dash-card flagged-issues-card">
          <div className="card-header">
            <h2 className="card-title">Newly flagged comments</h2>
            <p className="card-desc flagged-desc">
              {issues.loading || issues.error ? "—" : flaggedTotal} recent negative comment{flaggedTotal === 1 ? "" : "s"} from {issues.data?.feedback_group_total ?? issues.data?.pairs?.length ?? 0} service areas meeting the current trigger settings.
            </p>
          </div>
          <AsyncContent resource={issues} label="flagged issues">
          <div className="flagged-list">
            {flaggedPreview.length === 0 ? (
              <p className="empty-note">No qualifying comments behind current open alerts in this view.</p>
            ) : flaggedPreview.map((item) => (
              <div key={item.id} className="flagged-item">
                <div className="flagged-text">{item.comment}</div>
                <div className="flagged-category">
                  {item.department || "Unknown"}{item.aspect ? ` · ${item.aspect}` : ""} · Negative{item.is_constructive?" · Constructive suggestion":""}
                </div>
              </div>
            ))}
          </div>
          <DashboardCardFooter page={flaggedPage} pages={flaggedPages} from={flaggedFrom} to={flaggedTo} total={flaggedTotal} noun="comments" onPage={setFlaggedPage} href={flaggedPreview[0] ? `/qa/alerts?${new URLSearchParams({ service_area: flaggedPreview[0].department, aspect: flaggedPreview[0].aspect })}` : "/qa/alerts"} action="View intervention" flagged />
          </AsyncContent>
        </section>
      </div>

      <div className="dashboard-bottom-grid">
        <section className="dash-card most-commented-card">
          <div className="card-header">
            <h2 className="card-title">Most commented</h2>
            <p className="card-desc">All {byDept.length} service areas, by number of comments.</p>
          </div>
          <AsyncContent resource={charts} label="comment counts">
          <div className="most-commented-list">
            {mostCommentedPaged.length === 0 ? (
              <p className="empty-note">No comments yet.</p>
            ) : mostCommentedPaged.map((item, idx) => {
              const rank = idx + (mostCommentedPage - 1) * PAGE_SIZE;
              return (
                <div key={item.name} className="most-commented-row">
                  <div className="most-commented-meta">
                    <span className="most-commented-name">{item.name}</span>
                    <span className="most-commented-count">{item.comments}</span>
                  </div>
                  <div className="most-commented-bar">
                    <div
                      className={`most-commented-bar-fill${rank === 0 ? " is-top" : ""}`}
                      style={{ width: `${(item.comments / maxCommented) * 100}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
          <DashboardCardFooter page={mostCommentedPage} pages={mostCommentedTotalPages} from={mostFrom} to={mostTo} total={byDept.length} noun="areas" onPage={setMostCommentedPage} href="/qa/feedback-log" action="View feedback" />
          </AsyncContent>
        </section>

        <section className="dash-card feedback-service-card">
          <div className="card-header">
            <h2 className="card-title">Feedback by service area</h2>
            <p className="card-desc">Comments per area. Hover a bar for the counts.</p>
          </div>
          <AsyncContent resource={charts} label="service-area chart">
          <div className="feedback-service-filters">
            <div className="filter-group">
              <label className="filter-label" htmlFor="facility-filter">Facility</label>
              <select id="facility-filter" className="filter-select" value={facilityFilter} onChange={(e) => { setFacilityFilter(e.target.value); setServiceAreaPage(1); }}>
                <option value="all">All facilities</option>
                {facilityOptions.map((name) => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
            </div>
            <div className="filter-group">
              <label className="filter-label" htmlFor="show-filter">Show</label>
              <select id="show-filter" className="filter-select" value={showFilter} onChange={(e) => { setShowFilter(e.target.value); setServiceAreaPage(1); }}>
                <option value="all">All</option>
                <option value="positive">Positive</option>
                <option value="constructive">Constructive</option>
                <option value="negative">Negative</option><option value="neutral">Neutral</option>
              </select>
            </div>
          </div>
          <div className="feedback-service-legend">
            <span className="legend-item"><span className="dash-legend-dot positive" /> Positive</span>
            <span className="legend-item"><span className="dash-legend-dot constructive" /> Constructive</span>
            <span className="legend-item"><span className="dash-legend-dot negative" /> Negative</span><span className="legend-item"><span className="dash-legend-dot neutral"/> Neutral</span>
          </div>
          <div className="sa-chart">
            {serviceAreaPaged.length === 0 ? (
              <p className="empty-note">No classified comments in this view.</p>
            ) : serviceAreaPaged.map((item) => (
              <div
                key={item.service_area}
                className="sa-row"
                title={`${item.service_area}: ${item.positive} positive, ${item.constructive} constructive, ${item.negative} negative`}
              >
                <div className="sa-name">{item.service_area}</div>
                <div className="sa-track-wrap">
                  <div className="sa-track">
                    {item.positive > 0 && <div className="sa-seg positive" style={{ width: `${(item.positive / barMax) * 100}%` }} />}
                    {item.constructive > 0 && <div className="sa-seg constructive" style={{ width: `${(item.constructive / barMax) * 100}%` }} />}
                    {item.negative > 0 && <div className="sa-seg negative" style={{ width: `${(item.negative / barMax) * 100}%` }} />}{item.neutral>0&&<div className="sa-seg neutral" style={{width:`${item.neutral/barMax*100}%`}}/>}
                  </div>
                </div>
                <div className="sa-total">{item.total}</div>
              </div>
            ))}
            {serviceAreaPaged.length > 0 && (
              <div className="sa-axis">
                <span />
                <div className="sa-ticks">
                  {ticks.map((t) => <span key={t}>{t}</span>)}
                </div>
                <span />
              </div>
            )}
          </div>
          <DashboardCardFooter page={serviceAreaPage} pages={serviceAreaTotalPages} from={saFrom} to={saTo} total={filteredServiceAreas.length} noun="areas" onPage={setServiceAreaPage} href="/qa/analytics" action="View analytics" />
          </AsyncContent>
        </section>
      </div>
    </div>
  );
}
