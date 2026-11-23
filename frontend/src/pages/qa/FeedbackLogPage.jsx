import { toggleCategories } from "../../categorySelection";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import SearchSuggestions from "../../components/SearchSuggestions";
import { formatDate } from "../../formatDate";
import CycleSelect from "../../components/CycleSelect";
import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../../api";
import { collectSurveyExport } from "../../surveyExport";
import { useRemoteData } from "../../hooks/useRemoteData";
import AsyncContent from "../../components/AsyncContent";
import FeedbackClassBadge from "../../components/FeedbackClassBadge";
import AspectBadges from "../../components/AspectBadges";

const PAGE_SIZE = 10;
const MOST_PAGE_SIZE = 4;

const SENTIMENT_COLOR = {
  positive: "#2f9268",
  constructive: "#d99b1e",
  negative: "#c0453a",
};

function Stars({ n }) {
  const filled = Math.max(0, Math.min(5, Number(n) || 0));
  return (
    <span className="fb-starline">
      <span className="fb-stars">{"\u2605".repeat(filled)}</span>
      <span className="fb-stars off">{"\u2605".repeat(5 - filled)}</span>
      <span className="fb-score">{filled}/5</span>
    </span>
  );
}

const fmtDateTime = formatDate;

const CLASS_CHIPS = [
  { key: "all", label: "All", dot: "var(--green-dark)" },
  { key: "positive", label: "Positive", dot: "var(--class-positive)" },
  { key: "negative", label: "Negative", dot: "var(--class-negative)" },
  { key: "constructive", label: "Constructive", dot: "var(--class-constructive)" },
  { key: "neutral", label: "Neutral", dot: "var(--class-neutral)" },
  { key: "unclassified", label: "Unclassified", dot: "#66756e" },
];

function Chevron({ dir }) {
  const points = dir === "left" ? "15 18 9 12 15 6" : "9 18 15 12 9 6";
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points={points} />
    </svg>
  );
}

function Pager({ safePage, pageCount, rangeStart, rangeEnd, total, onPage, noun }) {
  return (
    <div className="fb-tablefoot">
      <span className="fb-range">
        Showing {rangeStart}–{rangeEnd} of {total}{noun ? ` ${noun}` : ""}
      </span>
      <div className="fb-pager">
        <span className="pager-info">Page {safePage} of {pageCount}</span>
        <button
          type="button"
          className="pager-btn"
          onClick={() => onPage(Math.max(1, safePage - 1))}
          disabled={safePage <= 1}
          aria-label="Previous page"
        >
          <Chevron dir="left" />
        </button>
        <button
          type="button"
          className="pager-btn is-next"
          onClick={() => onPage(Math.min(pageCount, safePage + 1))}
          disabled={safePage >= pageCount}
          aria-label="Next page"
        >
          <Chevron dir="right" />
        </button>
      </div>
    </div>
  );
}

export default function FeedbackLogPage() {
  const [params] = useSearchParams();
  const commentsOnly=params.get("comments_only")!=="false";
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const [search, setSearch] = useState(() => params.get("search") || "");
  const [cycle, setCycle] = useState(() => params.get("cycle_id") || "");
  const [serviceAreaFilter, setServiceAreaFilter] = useState("all");
  const [collegeFilter, setCollegeFilter] = useState(() => params.get("college") || "all");
  const [languageFilter, setLanguageFilter] = useState("all");
  const [aspectFilter, setAspectFilter] = useState("all");
  const [classFilter, setClassFilter] = useState(() => ["positive", "negative", "neutral", "constructive", "unclassified"].includes(params.get("sentiment")) ? params.get("sentiment") : "all");
  const [page, setPage] = useState(1);
  const [mostPage, setMostPage] = useState(1);
  const [mostServiceAreaFilter, setMostServiceAreaFilter] = useState("all");
  const [selectedId, setSelectedId] = useState(() => Number(params.get("feedback_id")) || null);
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState("");

  const liveSearch=useDebouncedValue(search);
  const pageLoader = useCallback(() => api.feedbackPage({ page, page_size: PAGE_SIZE,
    search:liveSearch, comments_only:commentsOnly, cycle_id: cycle, department: serviceAreaFilter, college: collegeFilter, aspect: aspectFilter, language: languageFilter, sentiment: classFilter }),
    [page, liveSearch, cycle, commentsOnly, serviceAreaFilter, collegeFilter, aspectFilter, languageFilter, classFilter]);
  const feedback = useRemoteData(pageLoader);
  const optionsLoader = useCallback(() => api.feedbackOptions({cycle_id:cycle}), [cycle]);
  const options = useRemoteData(optionsLoader);
  const mostLoader = useCallback(() => api.mostCommented({ page: mostPage, page_size: MOST_PAGE_SIZE, department: mostServiceAreaFilter, cycle_id: cycle }), [mostPage, mostServiceAreaFilter, cycle]);
  const most = useRemoteData(mostLoader);
  const serviceAreas = options.data?.service_areas || [];
  const colleges = options.data?.colleges || [];
  const aspects = options.data?.aspects || [];
  const counts = feedback.data?.counts || { all: 0, positive: 0, negative: 0, constructive: 0 };
  const paged = feedback.loading ? [] : feedback.data?.items || [];
  const total = feedback.data?.total || 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const safePage = feedback.data?.page || 1;
  const selected = paged.find(r => r.id === selectedId) || paged[0] || null;
  const mostPaged = most.loading ? [] : most.data?.items || [];
  const mostTotalPages = Math.max(1, Math.ceil((most.data?.total || 0) / MOST_PAGE_SIZE));
  const mostSafePage = most.data?.page || 1;

  async function exportComments() {
    setExporting(true);
    setExportError("");
    try {
      const data = await collectSurveyExport(params => api.feedbackPage({...params,cycle_id:cycle}));
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `quad-survey-comments-${data.snapshot_at.slice(0, 10)}.json`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { setExportError(error.message); }
    finally { setExporting(false); }
  }

  function changeFilter(setter, value) { setter(value); setPage(1); }

  const detailId = selected?.id;
  useEffect(() => {
    if (!detailId) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    setDetailError("");
    api
      .feedbackDetail(detailId)
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch((err) => {
        if (!cancelled) {
          setDetail(null);
          setDetailError(err.message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [detailId]);


  const shown = detail && selected && detail.id === selected.id ? detail : selected;
  const rangeStart = total === 0 ? 0 : (safePage - 1) * PAGE_SIZE + 1;
  const rangeEnd = Math.min(safePage * PAGE_SIZE, total);

  return (
    <div className="feedback-page">
      <header className="fb-page-head">
        <div className="feedback-title-actions"><h1>Classified evaluations</h1><button type="button" className="btn ghost" onClick={exportComments} disabled={exporting}>{exporting ? "Exporting…" : "Export comments"}</button></div>
        <p>
          Written comments use one category each. Select one or more categories to combine results.
        </p>
      </header>

      {exportError ? <p className="error" role="alert">{exportError}</p> : null}
      <div className="fb-top-grid">
        <section className="dash-card fb-list-card">
          <div className="fb-filters">
            <CycleSelect value={cycle} onChange={value => {changeFilter(setCycle,value);setMostPage(1);setServiceAreaFilter("all");setMostServiceAreaFilter("all");}} />
            <SearchSuggestions id="feedback-suggestions" query={search} values={paged.flatMap(row=>[row.comment,row.student_number,row.department,row.college,...(row.aspects||[])])}/>
            <label className="fb-field feedback-search-field">
              <span>Search evaluations</span>
              <input
                type="search"
                list="feedback-suggestions"
                value={search}
                placeholder="Search comments, student number, service area, college, aspect or classification"
                onChange={(e) => changeFilter(setSearch, e.target.value)}
              />
            </label>
            <label className="fb-field">
              <span>Service area</span>
              <select value={serviceAreaFilter} onChange={(e) => changeFilter(setServiceAreaFilter, e.target.value)}>
                <option value="all">All service areas</option>
                {serviceAreas.map((f) => (
                  <option key={f} value={f}>{f}</option>
                ))}
              </select>
            </label>
            <label className="fb-field">
              <span>College</span>
              <select value={collegeFilter} onChange={(e) => changeFilter(setCollegeFilter, e.target.value)}>
                <option value="all">All</option>
                {colleges.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </label>
            <label className="fb-field"><span>Detected language</span><select value={languageFilter} onChange={e => changeFilter(setLanguageFilter, e.target.value)}><option value="all">All languages</option><option value="english">English</option><option value="tagalog">Tagalog</option><option value="taglish">Taglish</option><option value="unclassified">Unclassified</option></select></label>
            <label className="fb-field">
              <span>Aspect</span>
              <select value={aspectFilter} onChange={(e) => changeFilter(setAspectFilter, e.target.value)}>
                <option value="all">All</option>
                {aspects.map((a) => (
                  <option key={a} value={a}>{a}</option>
                ))}
              </select>
            </label>
          </div>

          <div className="fb-chips" role="group" aria-label="Filter by classification">
            {CLASS_CHIPS.map((chip) => (
              <button
                key={chip.key}
                type="button"
                className={`fb-chip${(chip.key === "all" ? classFilter === "all" : classFilter.split(",").includes(chip.key)) ? " active" : ""}`}
                aria-pressed={(chip.key === "all" ? classFilter === "all" : classFilter.split(",").includes(chip.key))}
                onClick={() => changeFilter(setClassFilter, toggleCategories(classFilter, chip.key))}
              >
                <span className="dot" style={{ background: chip.dot }} />
                {chip.label}
                <span className="count">{counts[chip.key] ?? 0}</span>
              </button>
            ))}
          </div>

          <AsyncContent resource={options} label="filter options" />
          <AsyncContent resource={feedback} label="feedback" />
          <div className="table-wrap">
            <table className="fb-table">
              <colgroup>
                <col className="col-id" />
                <col className="col-college" />
                <col className="col-aspect" />
                <col className="col-area" />
                <col className="col-class" />
              </colgroup>
              <thead>
                <tr>
                  <th>Student ID</th>
                  <th>College</th>
                  <th>Aspects</th>
                  <th>Service area</th>
                  <th>Class</th>
                </tr>
              </thead>
              <tbody>
                {paged.map((r) => (
                  <tr
                    key={r.id}
                    className={selected?.id === r.id ? "selected" : ""}
                    onClick={() => setSelectedId(r.id)}
                  >
                    <td className="cell-strong">{r.student_number || "\u2014"}</td>
                    <td className="cell-college">{r.college || "\u2014"}</td>
                    <td><AspectBadges row={r} /></td>
                    <td className="cell-area">{r.department || "\u2014"}</td>
                    <td>
                      <FeedbackClassBadge row={r} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {!feedback.loading && !feedback.error && total === 0 ? (
            <p className="empty-note">No entries match these filters.</p>
          ) : null}

          <Pager
            safePage={safePage}
            pageCount={pageCount}
            rangeStart={rangeStart}
            rangeEnd={rangeEnd}
            total={total}
            onPage={setPage}
          />
        </section>

        <div className="fb-side">
        {shown ? (
          <aside className="dash-card fb-detail-card">
            <span className="fb-eyebrow">Authorized detail view</span>
            <div className="fb-detail-head">
              <h2>Submission #{String(shown.id).padStart(3, "0")}</h2>
              <FeedbackClassBadge row={shown} />
            </div>

            <div className="fb-kv">
              <div className="row"><span className="k">Student no.</span><span className="v">{shown.student_number || "Not available on this record"}</span></div>
              <div className="row"><span className="k">Email</span><span className="v">{shown.institutional_email || "Not available on this record"}</span></div>
              <div className="row"><span className="k">College</span><span className="v">{shown.college || "\u2014"}</span></div>
              <div className="row"><span className="k">Service area</span><span className="v">{shown.department || "\u2014"}</span></div>
              <div className="row"><span className="k">Aspects</span><span className="v"><AspectBadges row={shown} /></span></div>
              <div className="row"><span className="k">Detected language</span><span className="v">{{english:"English",tagalog:"Tagalog",taglish:"Taglish",undetermined:"Unclassified"}[shown.detected_language]||"Unclassified"}</span></div>
              <div className="row"><span className="k">Date / time</span><span className="v">{fmtDateTime(shown.created_at)}</span></div>

              {shown.rating_1 != null || shown.rating_2 != null || shown.rating_3 != null ? (
                <>
                  <div className="row"><span className="k">Question 1</span><span className="v"><Stars n={shown.rating_1} /></span></div>
                  <div className="row"><span className="k">Question 2</span><span className="v"><Stars n={shown.rating_2} /></span></div>
                  <div className="row"><span className="k">Question 3</span><span className="v"><Stars n={shown.rating_3} /></span></div>
                </>
              ) : shown.rating != null ? (
                <div className="row"><span className="k">Rating</span><span className="v"><Stars n={shown.rating} /></span></div>
              ) : null}

              <div className="row"><span className="k">Comment</span><span className="v comment-block">{shown.comment}</span></div>
            </div>

            {detailError ? <p className="error">{detailError}</p> : null}
          </aside>
        ) : (
          <aside className="dash-card fb-detail-card">
            <p className="empty-note">Select a row to see its details.</p>
          </aside>
        )}
        </div>
      </div>

      <div className="fb-bottom-grid">
        <section className="dash-card fb-comments-card">
          <div className="fb-comments-head">
            <div>
              <h2>Comments</h2>
              <p>What students wrote. Follows the filters above; the selected submission is highlighted.</p>
            </div>
            <p className="muted">Uses the selected categories above.</p>
          </div>

          <ul className="fb-comment-list">
            {!feedback.loading && !feedback.error && paged.length === 0 ? (
              <li className="empty-note">No comments match these filters.</li>
            ) : paged.map((r) => (
              <li
                key={r.id}
                className={`fb-comment-item${selected?.id === r.id ? " selected" : ""}`}
                onClick={() => setSelectedId(r.id)}
              >
                <div className="fb-comment-body">
                  <p>{r.comment}</p>
                  <small>{r.department || "Unknown"}{r.college ? ` · ${r.college}` : ""}</small>
                </div>
                <FeedbackClassBadge row={r} />
              </li>
            ))}
          </ul>

          <div className="fb-comments-foot">
            <Pager
              safePage={safePage}
              pageCount={pageCount}
              rangeStart={rangeStart}
              rangeEnd={rangeEnd}
              total={total}
              onPage={setPage}
              noun="comments"
            />
            <Link to="/qa/alerts" className="fb-intervention-btn">
              Intervention →
            </Link>
          </div>
        </section>

        <section className="dash-card fb-most-card">
          <div className="fb-most-head">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "1rem", flexWrap: "wrap" }}>
              <div>
                <h2>Most commented</h2>
                <p>The service areas students wrote about most, and what they said.</p>
              </div>
              <label className="fb-field fb-most-service-area-filter">
                <span>Service area</span>
                <select value={mostServiceAreaFilter} onChange={(e) => { setMostServiceAreaFilter(e.target.value); setMostPage(1); }}>
                  <option value="all">All service areas</option>
                  {serviceAreas.map((a) => (
                    <option key={a} value={a}>{a}</option>
                  ))}
                </select>
              </label>
            </div>
          </div>
          <AsyncContent resource={most} label="most commented" />
          <div className="fb-most-list">
            {!most.loading && !most.error && mostPaged.length === 0 ? (
              <p className="empty-note">No comments yet.</p>
            ) : mostPaged.map((g) => (
              <div key={g.area} className="fb-most-group">
                <h3>{g.area}</h3>
                {g.comments.slice(0, 2).map((c, i) => (
                  <blockquote
                    key={i}
                    className="fb-most-quote"
                    style={{ borderColor: SENTIMENT_COLOR[c.sentiment] || "#cdd8d2" }}
                  >
                    {c.text}
                  </blockquote>
                ))}
              </div>
            ))}
          </div>
          <div className="fb-most-foot">
            <span className="pager-info">Page {mostSafePage} of {mostTotalPages}</span>
            <div className="pager">
              <button
                type="button"
                className="pager-btn"
                onClick={() => setMostPage((p) => Math.max(1, p - 1))}
                disabled={mostSafePage <= 1}
                aria-label="Previous page"
              >
                <Chevron dir="left" />
              </button>
              <button
                type="button"
                className="pager-btn is-next"
                onClick={() => setMostPage((p) => Math.min(mostTotalPages, p + 1))}
                disabled={mostSafePage >= mostTotalPages}
                aria-label="Next page"
              >
                <Chevron dir="right" />
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
