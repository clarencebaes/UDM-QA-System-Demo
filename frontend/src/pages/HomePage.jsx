import { useNotice } from "../hooks/useNotice";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

function fmtDate(v) {
  if (!v) return null;
  const d = new Date(v.endsWith("Z") ? v : v+"Z");
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone:"Asia/Manila" });
}

export default function HomePage() {
  const navigate = useNavigate();
  const [agreed, setAgreed] = useState(false);
  const [consentError, setConsentError] = useState("");
  const [survey, setSurvey] = useState(null);

  useNotice(consentError,"error");
  // Survey period from Settings (Active/Inactive toggle + schedule).
  useEffect(() => {
    // Warm public options while the student reads the consent notice.
    api.evaluationConfig().catch(() => {});
    api
      .surveyStatus()
      .then(setSurvey)
      .catch(() => setSurvey(null));
  }, []);

  const surveyActive = survey?.is_active === true;
  const scheduleStart = fmtDate(survey?.start_date);
  const scheduleEnd = fmtDate(survey?.end_date);
  const schedule =
    scheduleStart && scheduleEnd
      ? `${scheduleStart} to ${scheduleEnd}`
      : scheduleStart
        ? `From ${scheduleStart}`
        : scheduleEnd
          ? `Until ${scheduleEnd}`
          : "To be announced";

  function startEvaluation(e) {
    e.preventDefault();
    setConsentError("");
    if (!surveyActive) {
      setConsentError("The survey is not open right now. Please check back during the survey period.");
      return;
    }
    if (!agreed) {
      setConsentError("Please confirm the data privacy notice before proceeding.");
      return;
    }
    // Keep the draft and browser receipt capability for resume and duplicate checks.
    sessionStorage.setItem("udm_eval_consent", "1");
    navigate("/evaluate");
  }

  return (
    <main className="landing-page">
      <section className="landing-panel landing-intro">
        <p className="eyebrow center">Universidad de Manila</p>
        <h1 className="landing-title">Student Facility Evaluation</h1>
        <div className="landing-status-box">
          <span className={`landing-status-badge ${!survey || surveyActive ? "is-active" : "is-inactive"}`}>
            Survey Status: {survey ? (surveyActive ? "Active" : "Inactive") : "Checking availability"}
          </span>
          <p className="landing-schedule">
            <strong>Semester:</strong> {survey?.cycle?.label || "Not configured"}<br/><strong>Schedule:</strong> {schedule}
          </p>
        </div>
        <p className="landing-copy">
          Thank you for taking the UDM Student Satisfaction Survey.
        </p>
        <p className="landing-copy secondary">
          Your responses will serve as valuable input in improving the quality of services provided by the University.
          All responses will be treated with confidentiality and will be used for the evaluation and continuous
          improvement of University services.
        </p>
        <p className="landing-copy secondary">
          Your honest feedback is important in helping the University identify areas that are performing well and
          areas that may need improvement. Please rate each statement based on your actual experience.
        </p>
      </section>

      <section className="landing-panel landing-evaluation">
        <h2 className="consent-heading">Privacy & consent notice</h2>
        <hr className="consent-rule" />

        <div className="consent-notice-box">
          <p>
            Each question may be rated from 1 (lowest) to 5 (highest):
          </p>
          <ul className="rating-scale-list">
            <li><strong>5 — Very Satisfied:</strong> Satisfaction is consistently exceptional.</li>
            <li><strong>4 — Satisfied:</strong> Satisfaction meets expectations.</li>
            <li><strong>3 — Neutral:</strong> Satisfaction meets some but not all expectations.</li>
            <li><strong>2 — Dissatisfied:</strong> Satisfaction is below expectations.</li>
            <li><strong>1 — Strongly Dissatisfied:</strong> Satisfaction is consistently below expectations.</li>
          </ul>
          <p>
            For ratings of 1 or 2, please provide a brief explanation of your concern or a recommendation for
            improvement in the comment box. This will help the University better understand the issue and identify
            possible ways to address it.
          </p>
          <p>
            This evaluation forms part of Group 9’s capstone research at Universidad De Manila and supports
            the evaluation and improvement of University services. We collect your student number, institutional
            email, college, student status, ratings, comments, consent and submission date. These records are
            confidential, not anonymous, and may be reviewed by authorized QUAD staff. Aggregate research reports
            do not display student numbers or email addresses. Automated classifications support human review.
          </p>
          <p>
            Participation is voluntary. You may leave before submitting. Please avoid including unnecessary
            personal information about yourself or others in comments. By proceeding, you agree to this collection
            and use for the capstone research and service evaluation described above. For questions about your
            data or a submission problem, use Report a concern. Notice version: 29 October 2026.
          </p>
        </div>

        <form className="consent-form" onSubmit={startEvaluation}>
          <label className="check consent-check">
            <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
            <span>I have read and agree to the data privacy notice before proceeding.</span>
          </label>
          {consentError ? <p className="error">{consentError}</p> : null}
          {!surveyActive ? (
            <p className="landing-status-note">
              The survey is currently inactive. Submissions are closed until an administrator reopens it in Settings.
            </p>
          ) : null}
          <button type="submit" className="btn landing-primary" disabled={!agreed || !surveyActive}>
            Begin Evaluation
          </button>
        </form>
      </section>
    </main>
  );
}
