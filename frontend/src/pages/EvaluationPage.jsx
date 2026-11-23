import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { isValidEmail, isValidStudentNumber, normalizeStudentNumber } from "../studentIdentity";
import { isServiceAreaApplicable } from "../evaluationPolicy";

import { RATING_LABELS } from "../ratingLabels";
import { readDraft, saveDraft, clearDraft } from "../evaluationDraft";
const IDENTITY_KEY = "udm_eval_identity";

function loadIdentity() {
  try {
    return JSON.parse(sessionStorage.getItem(IDENTITY_KEY) || "null");
  } catch {
    return null;
  }
}

function CancelConfirmCard({ onKeep, onConfirm }) {
  // Fixed overlay so the dialog appears centered on screen —
  // no scrolling needed to find it.
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e) => {
      if (e.key === "Escape") onKeep();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
    };
  }, [onKeep]);
  return (
    <div className="modal-overlay" onClick={onKeep} role="presentation">
      <section
        className="modal confirm-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="cancel-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 id="cancel-title">Cancel evaluation?</h3>
        <p>Your entered information will be discarded. Are you sure you want to cancel?</p>
        <div className="modal-actions">
          <button className="btn ghost" onClick={onKeep} autoFocus>
            No, continue
          </button>
          <button className="btn primary" onClick={onConfirm}>
            Yes, cancel
          </button>
        </div>
      </section>
    </div>
  );
}

export default function EvaluationPage() {
  const navigate = useNavigate();
  const [allServiceAreas, setServiceAreas] = useState([]);
  const [colleges, setColleges] = useState([]);
  const [cycle, setCycle] = useState(null);
  const [draft] = useState(() => readDraft());
  const submitted = useRef(false);
  const [draftSaved, setDraftSaved] = useState(true);
  const [studentStatus, setStudentStatus] = useState(draft?.studentStatus || "");
  const [configLoading, setConfigLoading] = useState(true);
  const [step, setStep] = useState(draft?.step || 0);
  const [ratings, setRatings] = useState(draft?.ratings || {});
  const [comments, setComments] = useState(draft?.comments || {});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  // Track validation errors for each field
  const [validationErrors, setValidationErrors] = useState({
    student_number: "",
    institutional_email: "",
    college: ""
  });
  const saved = loadIdentity();
  const [identityDone, setIdentityDone] = useState(Boolean(draft));
  const [identity, setIdentity] = useState(
    draft?.identity || saved || { student_number: "", institutional_email: "", college: "" },
  );
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const serviceAreas = useMemo(
    () => allServiceAreas.filter((area) => isServiceAreaApplicable(area, identity.college)),
    [allServiceAreas, identity.college],
  );

  const loadConfiguration = useCallback(async (force = false) => {
    setConfigLoading(true);
    setError("");
    try {
      const config = await api.evaluationConfig(force);
      const active = config.departments.filter(d => d.is_active);
      if (!active.length || !config.colleges.length) throw new Error("Evaluation options are unavailable. Please retry.");
      setServiceAreas(active);
      const applicable = active.filter(area => isServiceAreaApplicable(area, draft?.identity.college || ""));
      setStep(value => Math.min(value, Math.max(0, applicable.length - 1)));
      setColleges(config.colleges);
      setCycle(config.cycle);
      if (draft && draft.cycleId !== config.cycle?.id) {
        sessionStorage.removeItem("udm_request_key");
        clearDraft(); setRatings({}); setComments({}); setStep(0); setIdentityDone(false);
        throw new Error("The survey semester changed. Your old draft cannot be submitted. Check your details to start this semester.");
      }
      if (!config.cycle) throw new Error("No semester is configured. Please return home or report a concern.");
      if (draft && sessionStorage.getItem("udm_request_key")) {
        const status = await api.request("/submissions/status", {method: "POST", body: JSON.stringify({
          cycle_id: config.cycle.id, ...draft.identity,
          request_key: sessionStorage.getItem("udm_request_key")
        })});
        if (status.receipt_available) {
          submitted.current = true;
          sessionStorage.setItem("udm_receipt", status.receipt_token);
          clearDraft();
          sessionStorage.removeItem("udm_request_key");
          sessionStorage.removeItem("udm_eval_consent");
          sessionStorage.removeItem("udm_eval_started");
          sessionStorage.removeItem(IDENTITY_KEY);
          navigate("/thanks", {state: {alreadyAnswered: true}});
        }
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setConfigLoading(false);
    }
  }, [draft, navigate]);

  useEffect(() => {
    if (sessionStorage.getItem("udm_eval_consent") !== "1") {
      sessionStorage.setItem("udm_scroll_eval", "1");
      navigate("/");
      return;
    }
    loadConfiguration();
  }, [navigate, loadConfiguration]);

  useEffect(() => {
    if (submitted.current || !identityDone || !cycle || configLoading || busy) return;
    setDraftSaved(saveDraft({cycleId: cycle.id, identity, studentStatus, ratings, comments, step}));
  }, [identityDone, cycle, configLoading, busy, identity, studentStatus, ratings, comments, step]);

  const current = serviceAreas[step];
  const progress = serviceAreas.length ? Math.round(((step + 1) / serviceAreas.length) * 100) : 0;
  const stepLabel = useMemo(() => {
    if (!current) return "";
    return `${step + 1} of ${serviceAreas.length}`;
  }, [current, step, serviceAreas.length]);

  const currentRatings = ratings[current?.id] || { rating_1: 0, rating_2: 0, rating_3: 0 };
  const currentComment = comments[current?.id] || "";
  const hasLowRating = [currentRatings.rating_1, currentRatings.rating_2, currentRatings.rating_3].some((r) => r >= 1 && r <= 2);

  function updateRating(questionIndex, value) {
    setRatings((prev) => ({
      ...prev,
      [current.id]: { ...(prev[current.id] || { rating_1: 0, rating_2: 0, rating_3: 0 }), [`rating_${questionIndex}`]: value },
    }));
  }

  // Clear validation error when user types
  function handleIdentityChange(field, value) {
    let normalizedValue = value;
    if (field === "student_number") {
      normalizedValue = normalizeStudentNumber(value);
    }
    setIdentity((prev) => ({ ...prev, [field]: normalizedValue }));
    if (validationErrors[field]) {
      setValidationErrors((prev) => ({ ...prev, [field]: "" }));
    }
  }

  function validateIdentity() {
    if (!studentStatus) {setError("Select Regular or Irregular student status.");return false;}
    if (!cycle) {setError("Wait for the semester configuration.");return false;}
    const errors = { student_number: "", institutional_email: "", college: "" };
    const student_number = normalizeStudentNumber(identity.student_number).trim().toUpperCase();
    const institutional_email = identity.institutional_email.trim();
    const college = identity.college;

    if (!student_number) {
      errors.student_number = "Student number is required.";
    } else if (!isValidStudentNumber(student_number)) {
      errors.student_number = "Enter a student number in the format ##-##-### (digits and hyphens only).";
    }

    if (!institutional_email) {
      errors.institutional_email = "Institutional Email is required.";
    } else if (!isValidEmail(institutional_email)) {
      errors.institutional_email = "Enter a valid @udm.edu.ph email address.";
    }

    if (!college) {
      errors.college = "Please select your college.";
    } else if (!colleges.some((c) => c.code === college)) {
      errors.college = "Please select a valid college.";
    }

    setValidationErrors(errors);
    return Object.values(errors).every((e) => e === "");
  }

  async function onIdentitySubmit(e) {
    e.preventDefault();
    setError("");
    if (validateIdentity()) {
      const student_number = normalizeStudentNumber(identity.student_number).trim().toUpperCase();
      const institutional_email = identity.institutional_email.trim();
      const college = identity.college;
      const next = { student_number, institutional_email, college };
      setBusy(true);
      try {
        const status = await api.request("/submissions/status", {method: "POST", body: JSON.stringify({
          cycle_id: cycle.id, ...next, token: sessionStorage.getItem("udm_receipt") || "",
          request_key: sessionStorage.getItem("udm_request_key") || ""
        })});
        if (status.submitted) {
          if (status.receipt_available) {
            sessionStorage.setItem("udm_receipt", status.receipt_token);
            clearDraft(); navigate("/thanks", {state: {alreadyAnswered: true}}); return;
          }
          setError("You have already answered this semester. Your saved receipt can be viewed in the browser tab used to submit. If it is unavailable, report a concern for QUAD assistance.");
          return;
        }
      } catch (err) { setError(err.message); return; }
      finally { setBusy(false); }
      setIdentity(next);
      setStep(0);
      sessionStorage.setItem(IDENTITY_KEY, JSON.stringify(next));
      sessionStorage.setItem("udm_eval_started", "1");
      setIdentityDone(true);
    }
  }

  async function onSubmitBatch() {
    setError("");
    if (!current) return;
    const incomplete = serviceAreas.some((area) => {
      const values = ratings[area.id] || {};
      const scores = [values.rating_1, values.rating_2, values.rating_3];
      return scores.some((score) => !(score >= 1 && score <= 5))
        || (scores.some((score) => score <= 2) && (comments[area.id] || "").trim().length < 10);
    });
    if (incomplete) {
      setError("Complete all required ratings and low-rating comments before submitting.");
      return;
    }
    if (hasLowRating && currentComment.trim().length < 10) {
      setError("Your rating is low. Please explain your concern or provide a suggestion for improvement in the comment box.");
      return;
    }
    setBusy(true);
    try {
      const normalizedStudentNumber = normalizeStudentNumber(identity.student_number).trim().toUpperCase();
      const items = serviceAreas
        .map((area) => {
          const areaRatings = ratings[area.id] || { rating_1: 0, rating_2: 0, rating_3: 0 };
          const areaComment = comments[area.id] || "";
          return {
            department_id: area.id,
            aspect_id: null,
            comment: areaComment,
            rating:
              areaRatings.rating_1 && areaRatings.rating_2 && areaRatings.rating_3
                ? Math.round((areaRatings.rating_1 + areaRatings.rating_2 + areaRatings.rating_3) / 3)
                : null,
            rating_1: areaRatings.rating_1 || null,
            rating_2: areaRatings.rating_2 || null,
            rating_3: areaRatings.rating_3 || null,
            student_number: normalizedStudentNumber,
            institutional_email: identity.institutional_email,
            college: identity.college,
            consent: true,
          };
        })
        .filter((item) => item.comment || item.rating_1 || item.rating_2 || item.rating_3);
      if (items.length === 0) {
        setError("Please provide at least one rating or comment.");
        setBusy(false);
        return;
      }
      let requestKey = sessionStorage.getItem("udm_request_key");
      if (!requestKey) {requestKey=crypto.randomUUID();sessionStorage.setItem("udm_request_key",requestKey);}
      const result = await api.submitSurvey({items, cycle_id:cycle.id,student_status:studentStatus,request_key:requestKey,consent_version:"2026-10-29"});
      submitted.current = true;
      sessionStorage.setItem("udm_receipt",result.receipt_token);
      clearDraft();
      sessionStorage.removeItem("udm_request_key");
      sessionStorage.removeItem("udm_eval_consent");
      sessionStorage.removeItem("udm_eval_started");
      sessionStorage.removeItem(IDENTITY_KEY);
      navigate("/thanks");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function onNext(e) {
    e.preventDefault();
    setError("");
    if (!current) return;

    // Check if all 3 ratings are provided
    const allRated = currentRatings.rating_1 > 0 && currentRatings.rating_2 > 0 && currentRatings.rating_3 > 0;
    if (!allRated) {
      setError("Please rate all three questions before continuing.");
      return;
    }

    if (hasLowRating && currentComment.trim().length < 10) {
      setError("Your rating is low. Please explain your concern or provide a suggestion for improvement in the comment box.");
      return;
    }
    if (step + 1 >= serviceAreas.length) {
      onSubmitBatch();
      return;
    }
    setStep((s) => s + 1);
  }

  function onPrevious() {
    setStep((s) => Math.max(0, s - 1));
  }

  if (!identityDone) {
    return (
      <main className="page narrow evaluation-page">
        <section className="card eval-card">
          <h1>Student information</h1>
          <form className="form" onSubmit={onIdentitySubmit} noValidate>
            <label>
              Student number
              <input
                type="text"
                autoComplete="off"
                value={identity.student_number}
                onChange={(e) => handleIdentityChange("student_number", e.target.value)}
                placeholder=""
                aria-invalid={validationErrors.student_number ? "true" : "false"}
              />
              {validationErrors.student_number && <span className="error">{validationErrors.student_number}</span>}
            </label>
            <label>
              Institutional Email
              <input
                type="email"
                autoComplete="email"
                value={identity.institutional_email}
                onChange={(e) => handleIdentityChange("institutional_email", e.target.value)}
                placeholder=""
                aria-invalid={validationErrors.institutional_email ? "true" : "false"}
              />
              {validationErrors.institutional_email && <span className="error">{validationErrors.institutional_email}</span>}
            </label>
            <label>
              College
              <select
                disabled={configLoading}
                value={identity.college}
                onChange={(e) => handleIdentityChange("college", e.target.value)}
                aria-invalid={validationErrors.college ? "true" : "false"}
              >
                <option value="">Select your college</option>
                {colleges.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.code} — {c.name}
                  </option>
                ))}
              </select>
              {validationErrors.college && <span className="error">{validationErrors.college}</span>}
            </label>
            <label>Student status<select required value={studentStatus} onChange={e=>setStudentStatus(e.target.value)}><option value="">Select student status</option><option value="regular">Regular</option><option value="irregular">Irregular</option></select></label>
            <p><strong>Survey semester:</strong> {cycle?.label || "Loading…"}</p>
            {configLoading ? <p className="muted" role="status">Loading college and evaluation options… You can enter your student number and email now.</p> : null}
            {error ? <div role="alert"><p className="error">{error}</p><Link to="/concern">Report a concern</Link></div> : null}
            {!configLoading && !allServiceAreas.length ? <button type="button" className="btn ghost" onClick={() => loadConfiguration(true)}>Retry evaluation options</button> : null}
            <div className="actions">
              <button className="btn primary" type="submit" disabled={busy || configLoading || !allServiceAreas.length}>
                Continue
              </button>
              <button
                className="btn ghost"
                type="button"
                onClick={() => setShowCancelConfirm(true)}
              >
                Cancel
              </button>
            </div>
          </form>
        </section>

        {showCancelConfirm && (
          <CancelConfirmCard
            onKeep={() => setShowCancelConfirm(false)}
            onConfirm={() => {
              sessionStorage.removeItem("udm_eval_started");
              sessionStorage.removeItem("udm_eval_identity");
              sessionStorage.setItem("udm_scroll_eval", "1");
              navigate("/");
            }}
          />
        )}
      </main>
    );
  }

  const isLast = step + 1 >= serviceAreas.length;
  const submitLabel = busy ? "Submitting…" : isLast ? "Submit evaluation" : "Next →";

  if (!serviceAreas.length && !error) {
    return (
      <main className="page narrow evaluation-page">
        <p className="muted">Loading evaluation…</p>
      </main>
    );
  }

  if (!serviceAreas.length && error) {
    return (
      <main className="page narrow evaluation-page">
        <p className="error">{error}</p>
        <button type="button" className="btn ghost" onClick={() => loadConfiguration(true)}>Retry evaluation options</button>
      </main>
    );
  }

  return (
    <main className="page narrow evaluation-page">
      <div className="eval-progress">
        <span>Student Facility Evaluation · {stepLabel}</span>
        <div className="eval-progress-bar">
          <div className="eval-progress-fill" style={{ width: `${progress}%` }} />
        </div>
      </div>

      <section className="card eval-card eval-answer-card">
        <h1>{current?.name || "Evaluation"}</h1>
        <p className="lead eval-desc">{current?.description || "Share your experience with this service area."}</p>
        <p className="muted">
          {identity.college} · {identity.student_number}
        </p>

        <p className={draftSaved ? "draft-status" : "error"} role="status">{draftSaved
          ? "Progress is saved in this browser tab. If you reload, your ratings and comments will return. Submit to send your final answers to QUAD."
          : "This browser could not save your draft. Keep this tab open until you submit."}</p>
        <form className="form" onSubmit={onNext}>
          <div className="rating-block">
            {[1, 2, 3].map((questionIndex) => (
              <div key={questionIndex} className="rating-question">
                <p className="question-text">
                  {questionIndex}. {current?.questions?.[questionIndex - 1] || `Please rate your experience with ${current?.name}.`}
                </p>
                <div className="rating-row center-stars">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <div key={star} className="evaluation-rating-option">
                      <button
                        type="button"
                        className={`star-btn large ${currentRatings[`rating_${questionIndex}`] >= star ? "active" : ""}`}
                        onClick={() => updateRating(questionIndex, star)}
                        aria-label={`Question ${questionIndex}: ${star} out of 5, ${RATING_LABELS[star - 1]}`}
                        aria-pressed={currentRatings[`rating_${questionIndex}`] === star}
                      >
                        ★
                      </button>
                      <span className="evaluation-rating-number" aria-hidden="true">{star}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
            <p className="rating-caption">
              <span>Strongly Dissatisfied</span>
              <strong>
                {currentRatings.rating_1 || currentRatings.rating_2 || currentRatings.rating_3
                  ? RATING_LABELS[
                      Math.round(
                        ((currentRatings.rating_1 || 0) + (currentRatings.rating_2 || 0) + (currentRatings.rating_3 || 0)) /
                          3
                      ) - 1
                    ]
                  : "Select a rating"}
              </strong>
              <span>Very Satisfied</span>
            </p>
          </div>

          <label>
            Share any concern, positive experience, or suggestion for improvement.
            {hasLowRating && <span className="req">required</span>}
            <textarea
              rows={6}
              value={currentComment}
              onChange={(e) => setComments((prev) => ({ ...prev, [current.id]: e.target.value }))}
              placeholder={
                hasLowRating
                  ? "Your rating is low. Please explain your concern or provide a suggestion for improvement in the comment box."
                  : "Optional: share your experience or suggestions."
              }
            />
          </label>

          {error ? <div role="alert"><p className="error">{error}</p><Link to="/concern">Report a concern</Link></div> : null}

          <div className="actions eval-navigation">
            <button type="button" className="btn ghost" disabled={busy || step === 0} onClick={onPrevious}>Previous</button>
            <button className="btn primary" type="submit" disabled={busy}>{submitLabel}</button>
          </div>
        </form>
      </section>

      {showCancelConfirm && (
        <CancelConfirmCard
          onKeep={() => setShowCancelConfirm(false)}
          onConfirm={() => {
            sessionStorage.removeItem("udm_eval_started");
            sessionStorage.removeItem(IDENTITY_KEY);
            sessionStorage.removeItem("udm_eval_consent");
            sessionStorage.setItem("udm_scroll_eval", "1");
            navigate("/");
          }}
        />
      )}
    </main>
  );
}
