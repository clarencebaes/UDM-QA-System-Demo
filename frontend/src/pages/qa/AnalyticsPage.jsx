import TextDimensions from "../../components/TextDimensions";
import PageLoading from "../../components/PageLoading";
import { sortRatingRows } from "../../ratingOrder";
import { StarRatings } from "../../components/EvaluationSummaries";
import CycleSelect from "../../components/CycleSelect";
import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useQaData } from "../../hooks/useQaData";
import { SENTIMENT_COLORS } from "../../sentimentPalette";

// Saturated chart palette taken from the reference design.
const C = {
  ...SENTIMENT_COLORS,
  respondents: "#14563f",
  enrolled: "#d4a017",
  comments: "#8fbf9a",
};

const SA_PAGE_SIZE = 6;

function Swatch({ color }) {
  return <span className="ana-swatch" style={{ background: color }} />;
}

function LegendItem({ color, label }) {
  return (
    <span className="ana-legend-item">
      <Swatch color={color} />
      {label}
    </span>
  );
}

function ChartLegend({ items }) {
  return (
    <div className="ana-legend">
      {items.map((it) => (
        <LegendItem key={it.label} color={it.color} label={it.label} />
      ))}
    </div>
  );
}

function pctOf(part, whole) {
  if (!whole) return 0;
  return Math.round((part / whole) * 100);
}

function formatPct(value) {
  if (value === null || value === undefined) return "N/A";
  return `${Math.round(value)}%`;
}

function AspectTick({x,y,payload}) {
  const lines=[];let line="";
  for(const word of String(payload.value).split(" ")){if((line+" "+word).trim().length>27&&line){lines.push(line);line=word;}else line=(line+" "+word).trim();}
  if(line)lines.push(line);
  return <text x={x-8} y={y-(lines.length-1)*7} textAnchor="end" fontSize={11} fill="#4b6258">{lines.map((text,i)=><tspan key={i} x={x-8} dy={i?14:0}>{text}</tspan>)}</text>;
}

export default function AnalyticsPage() {
  const [ratingOrder,setRatingOrder]=useState("service");
  const [cycle, setCycle] = useState("");
  const [collegeFilter, setCollegeFilter] = useState("all");
  const { dash, error, loading, reload } = useQaData({ college: collegeFilter, cycle_id: cycle });
  const [aspectFilter,setAspectFilter]=useState("all");
  const [saPage, setSaPage] = useState(1);
  const [saFilter, setSaFilter] = useState("all");
  const [saSentiment, setSaSentiment] = useState("all");
  const scopedColleges = useMemo(
    () => (dash?.by_college || []).filter((row) => collegeFilter === "all" || row.college === collegeFilter),
    [dash?.by_college, collegeFilter],
  );

  // ── Respondents / enrolled / comments by college ──
  const participationData = useMemo(
    () =>
      scopedColleges.map((c) => ({
        college: c.college,
        respondents: c.responses || 0,
        enrolled: c.enrolled || 0,
        comments: c.comments || 0,
      })),
    [scopedColleges]
  );

  // ── Classification by college (100% horizontal stacked) ──
  const collegeClassRows = useMemo(
    () =>
      scopedColleges.map((c) => {
        const total = (c.positive || 0) + (c.constructive || 0) + (c.negative || 0) + (c.neutral || 0);
        return {
          college: c.college,
          name: c.name,
          positive: c.positive || 0,
          constructive: c.constructive || 0,
          negative: c.negative || 0,
          neutral: c.neutral || 0,
          total,
          positivePct: pctOf(c.positive || 0, total),
          constructivePct: pctOf(c.constructive || 0, total),
          negativePct: pctOf(c.negative || 0, total),
          neutralPct: pctOf(c.neutral || 0, total),
        };
      }),
    [scopedColleges]
  );

  // ── Classification by service area (area filter + sentiment + paginated) ──
  const saOptions = useMemo(
    () =>
      (dash?.by_service_area || [])
        .map((f) => f.service_area)
        .sort((a, b) => a.localeCompare(b)),
    [dash?.by_service_area]
  );

  const saRows = useMemo(() => {
    const base = dash?.by_service_area || [];
    const list = saFilter === "all" ? base : base.filter((f) => f.service_area === saFilter);
    return list.map((f) => {
      const pos = f.positive || 0;
      const con = f.constructive || 0;
      const neg = f.negative || 0;
      const neu=f.neutral||0;
      const total = pos + con + neg + neu;
      const keep = (v, key) => (saSentiment === "all" || saSentiment === key ? v : 0);
      return {
        service_area: f.service_area,
        total: f.total ?? total,
        positivePct: pctOf(keep(pos, "positive"), total),
        constructivePct: pctOf(keep(con, "constructive"), total),
        negativePct: pctOf(keep(neg, "negative"), total),
        neutralPct: pctOf(keep(neu, "neutral"), total),
      };
    });
  }, [dash?.by_service_area, saFilter, saSentiment]);

  const saTotalPages = Math.max(1, Math.ceil(saRows.length / SA_PAGE_SIZE));
  const saCurrentPage = Math.min(saPage, saTotalPages);
  const saPaged = saRows.slice(
    (saCurrentPage - 1) * SA_PAGE_SIZE,
    saCurrentPage * SA_PAGE_SIZE
  );
  const saFrom = saRows.length ? (saCurrentPage - 1) * SA_PAGE_SIZE + 1 : 0;
  const saTo = Math.min(saCurrentPage * SA_PAGE_SIZE, saRows.length);

  // ── Counts by aspect ──
  const aspectOptions = useMemo(() => dash?.by_aspect || [], [dash?.by_aspect]);
  const aspectData = aspectFilter === "all" ? aspectOptions : aspectOptions.filter(a=>a.aspect===aspectFilter);

  // ── College analytics table ──
  const collegeRows = scopedColleges;

  if (loading && !dash) return <PageLoading title="Analytics" message="Loading survey analytics…"/>;
  if (error) return <div className="ops-page"><h1>Analytics</h1><p className="error" role="alert">{error}</p><button className="btn primary" onClick={reload}>Retry analytics</button></div>;
  if (!dash) return null;

  return (
    <div className={`dashboard-page${loading?" analytics-is-updating":""}`} aria-busy={loading}>
      <header className="dash-topbar">
        <div className="dash-topbar-left">
          <h1 className="dash-title">Analytics</h1>
          <p className="dash-subtitle">
            Service area, college and aspect analysis of classified comments.
          </p>
        </div>

      </header>

      {loading&&<p className="analytics-update-notice" role="status">Updating analytics for the selected college and semester…</p>}
      {/* Classification distribution */}
      <div className="ana-top-grid">
        <section className="card ana-card">
          <div className="ana-distribution-heading">
            <h2>Classification distribution</h2>
            <div className="analytics-distribution-controls"><div className="analytics-scope-controls">
          <CycleSelect value={cycle} onChange={setCycle} />
          <div className="dash-college-filter">
            <label className="dash-college-label" htmlFor="ana-college">
              College
            </label>
            <select
              id="ana-college"
              className="dash-college-select"
              value={collegeFilter}
              onChange={(e) => {
                setCollegeFilter(e.target.value);
                setSaPage(1);
                setSaFilter("all");
              }}
            >
              <option value="all">All colleges</option>
              {(dash.by_college || []).map((c) => (
                <option key={c.college} value={c.college}>
                  {c.college}
                </option>
              ))}
            </select>
          </div>
        </div></div>
          </div>
          <p className="card-desc">Positive, Constructive, Negative, Neutral and Unclassified comments, and detected language for the selected semester and college.</p>
          <TextDimensions data={dash}/>
        </section>

      </div>

      {/* Respondents, enrolled students and comments by college */}
      <section className="card ana-card">
        <h2>Respondents, enrolled students and comments by college</h2>
        <p className="card-desc">Hover a bar for the exact count.</p>
        <ChartLegend items={[
          { color: C.respondents, label: "Respondents" },
          { color: C.enrolled, label: "Enrolled (expected)" },
          { color: C.comments, label: "Comments" },
        ]} />
        <div className="chart tall">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={participationData} barGap={3}>
              <CartesianGrid vertical={false} stroke="#eef1ee" />
              <XAxis
                dataKey="college"
                tickLine={false}
                axisLine={{ stroke: "#e2e8e4" }}
                tick={{ fontSize: 12, fill: "#5c6b66" }}
              />
              <YAxis
                allowDecimals={false}
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 12, fill: "#8a9692" }}
              />
              <Tooltip cursor={{ fill: "rgba(13,59,46,0.04)" }} />
              <Bar
                dataKey="respondents"
                name="Respondents"
                fill={C.respondents}
                label={{ position: "top", fontSize: 12, fill: "#1a2e28" }}
              />
              <Bar
                dataKey="enrolled"
                name="Enrolled (expected)"
                fill={C.enrolled}
                label={{ position: "top", fontSize: 12, fill: "#1a2e28" }}
              />
              <Bar
                dataKey="comments"
                name="Comments"
                fill={C.comments}
                label={{ position: "top", fontSize: 12, fill: "#1a2e28" }}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* Classification by college */}
      <section className="card ana-card">
        <h2>Classification by college</h2>
        <p className="card-desc">
          Primary feedback categories by college. Suggestions appear under Constructive; their sentiment is counted separately above.
        </p>
        <ChartLegend items={[
          { color: C.positive, label: "Positive" },
          { color: C.constructive, label: "Constructive" },
          { color: C.negative, label: "Negative" },
          { color: C.neutral, label: "Neutral" },
        ]} />
        <div className="ana-hbar-rows">
          {collegeClassRows.map((row) => (
            <div key={row.college} className="ana-hbar-row">
              <div className="ana-hbar-label">
                <span className="code">{row.college}</span>
                <span className="name">{row.name}</span>
              </div>
              <div
                className="ana-hbar-track"
                title={`${row.college}: ${row.positive} positive, ${row.constructive} constructive, ${row.negative} negative`}
              >
                <div className="seg positive" style={{ width: `${row.positivePct}%` }} />
                <div className="seg constructive" style={{ width: `${row.constructivePct}%` }} />
                <div className="seg negative" style={{ width: `${row.negativePct}%` }} /><div className="seg neutral" style={{width:`${row.neutralPct}%`}}/>
              </div>
            </div>
          ))}
        </div>
        <div className="ana-hbar-axis">
          <span />
          <div className="ana-hbar-ticks">
            <span>0%</span>
            <span>50%</span>
            <span>100%</span>
          </div>
        </div>
      </section>

      {/* Counts by aspect */}
      <section className="card ana-card">
        <div className="ana-distribution-heading"><h2>Counts by aspect</h2><label className="fb-field"><span>Aspect</span><select value={aspectFilter} onChange={e=>setAspectFilter(e.target.value)}><option value="all">All aspects</option>{aspectOptions.map(a=><option key={a.aspect}>{a.aspect}</option>)}</select></label></div>
        <p className="card-desc">Primary feedback categories per aspect; a comment may appear under several aspects. Hover or tap for counts and percentages.</p>
        <ChartLegend items={[
          { color: C.positive, label: "Positive" },
          { color: C.constructive, label: "Constructive" },
          { color: C.negative, label: "Negative" },
          { color: C.neutral, label: "Neutral" },
        ]} />
        <div className="aspect-count-chart" style={{height:Math.max(240,aspectData.length*90)}}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart layout="vertical" data={aspectData} barGap={3} margin={{top:8,right:24,bottom:8,left:8}}>
              <CartesianGrid horizontal={false} stroke="#eef1ee" />
              <XAxis type="number" allowDecimals={false} tickLine={false} axisLine={false}/>
              <YAxis type="category" dataKey="aspect" width={220} interval={0} tickLine={false} axisLine={false} tick={<AspectTick/>}/>
              <Tooltip
                cursor={{ fill: "rgba(13,59,46,0.04)" }}
                formatter={(value, name, entry) => {
                  const row = entry.payload;
                  const total = (row.positive || 0) + (row.constructive || 0) + (row.negative || 0) + (row.neutral || 0);
                  return [`${value} (${pctOf(Number(value), total)}% of this aspect)`, name];
                }}
              />
              <Bar dataKey="positive" name="Positive" fill={C.positive} />
              <Bar dataKey="constructive" name="Constructive" fill={C.constructive} />
              <Bar dataKey="negative" name="Negative" fill={C.negative} /><Bar dataKey="neutral" name="Neutral" fill={C.neutral}/>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* Classification by service area */}
      <section className="card ana-card ana-service-card">
        <div className="ana-card-head">
          <div className="ana-card-head-text">
            <h2>Classification by service area</h2>
            <p className="card-desc">
              Primary feedback categories. Saved evaluations count service-area answers, including ratings without comments.
            </p>
          </div>
          <div className="ana-sa-controls">
            <div className="filter-group">
              <label className="filter-label" htmlFor="ana-sa-area">Service area</label>
              <select
                id="ana-sa-area"
                className="filter-select"
                value={saFilter}
                onChange={(e) => { setSaFilter(e.target.value); setSaPage(1); }}
              >
                <option value="all">All service areas</option>
                {saOptions.map((name) => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
            </div>
            <div className="filter-group">
              <label className="filter-label" htmlFor="ana-sa-sentiment">Sentiment</label>
              <select
                id="ana-sa-sentiment"
                className="filter-select"
                value={saSentiment}
                onChange={(e) => { setSaSentiment(e.target.value); setSaPage(1); }}
              >
                <option value="all">All</option>
                <option value="positive">Positive</option>
                <option value="constructive">Constructive</option>
                <option value="negative">Negative</option><option value="neutral">Neutral</option>
              </select>
            </div>
          </div>
        </div>
        <ChartLegend items={[
          { color: C.positive, label: "Positive" },
          { color: C.constructive, label: "Constructive" },
          { color: C.negative, label: "Negative" },
          { color: C.neutral, label: "Neutral" },
        ]} />
        <div className="table-wrap">
          <table className="ana-sa-table">
            <thead>
              <tr>
                <th>Service Area</th>
                <th className="col-bar">Share of classified comments</th>
                <th className="col-count">Saved evaluations</th>
              </tr>
            </thead>
            <tbody>
              {saPaged.map((f) => (
                <tr key={f.service_area}>
                  <td className="area-name"><span title={f.service_area}>{f.service_area}</span></td>
                  <td>
                    <div
                      className="sa-bar"
                      title={`${f.service_area}: ${f.total} evaluations`}
                    >
                      <div className="seg positive" style={{ width: `${f.positivePct}%` }} />
                      <div className="seg constructive" style={{ width: `${f.constructivePct}%` }} />
                      <div className="seg negative" style={{ width: `${f.negativePct}%` }} /><div className="seg neutral" style={{width:`${f.neutralPct}%`}}/>
                    </div>
                  </td>
                  <td className="eval-count">{f.total}</td>
                </tr>
              ))}
              {saPaged.length>0&&Array.from({length:SA_PAGE_SIZE-saPaged.length},(_,i)=><tr key={`space-${i}`} className="ana-service-spacer" aria-hidden="true"><td colSpan={3}/></tr>)}
              {saPaged.length === 0 && (
                <tr>
                  <td colSpan={3} className="empty-note">No classified service areas yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="ana-foot">
          <span className="showing">
            Showing {saFrom}–{saTo} of {saRows.length} service areas
          </span>
          <div className="pager">
            <span className="pager-label">Page {saCurrentPage} of {saTotalPages}</span>
            <button
              className="pager-btn"
              onClick={() => setSaPage((p) => Math.max(1, p - 1))}
              disabled={saCurrentPage <= 1}
              aria-label="Previous page"
            >
              {"‹"}
            </button>
            <button
              className="pager-btn is-next"
              onClick={() => setSaPage((p) => Math.min(saTotalPages, p + 1))}
              disabled={saCurrentPage >= saTotalPages}
              aria-label="Next page"
            >
              {"›"}
            </button>
          </div>
        </div>
      </section>

      <section className="card star-ratings-card"><div className="ana-card-head rating-heading"><h2>Star ratings by service area</h2><label className="rating-order-field"><span>Arrange by</span><select value={ratingOrder} onChange={e=>setRatingOrder(e.target.value)}><option value="service">Service area (A–Z)</option><option value="highest">Highest rating</option><option value="lowest">Lowest rating</option></select></label></div><p className="card-desc">All submitted ratings for the selected semester and college, including evaluations without comments. Each of the three answered questions contributes one star rating. Earlier single-rating records contribute once.</p><StarRatings rows={sortRatingRows(dash?.star_ratings,ratingOrder)}/></section>

      {/* College analytics */}
      <section className="card ana-card">
        <h2>College analytics</h2>
        <p className="card-desc">Classification share and response counts by college.</p>
        <table className="ana-college-table">
          <thead>
            <tr>
              <th>College</th>
              <th>Responses</th>
              <th>Enrolled</th>
              <th>Regular</th><th>Irregular</th><th>Comments</th>
              <th>Positive</th>
              <th>Constructive</th>
              <th>Negative</th><th>Neutral</th>
            </tr>
          </thead>
          <tbody>
            {collegeRows.map((row) => (
              <tr key={row.college}>
                <td>
                  <span className="c-code">{row.college}</span>
                  <span className="c-name">{row.name}</span>
                </td>
                <td>{row.responses ?? 0}</td>
                <td>{row.enrolled ?? "—"}</td>
                <td>{(dash?.status_by_college||[]).find(r=>r.college===row.college&&r.status==="regular")?.respondents||0}</td><td>{(dash?.status_by_college||[]).find(r=>r.college===row.college&&r.status==="irregular")?.respondents||0}</td>
                <td>{row.comments ?? 0}</td>
                <td>
                  <span className="cls-val positive">{row.positive ?? 0}</span>
                  <span className="cls-pct">{formatPct(row.positive_pct)}</span>
                </td>
                <td>
                  <span className="cls-val constructive">{row.constructive ?? 0}</span>
                  <span className="cls-pct">{formatPct(row.constructive_pct)}</span>
                </td>
                <td>
                  <span className="cls-val negative">{row.negative ?? 0}</span>
                  <span className="cls-pct">{formatPct(row.negative_pct)}</span>
                </td>
                <td><span className="cls-val neutral">{row.neutral??0}</span><span className="cls-pct">{formatPct(row.neutral_pct)}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="ana-note">
          Classification share and response counts by college.
        </p>
      </section>
    </div>
  );
}
