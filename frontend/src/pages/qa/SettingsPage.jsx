import { philippineDay } from "../../formatDate";
import { useNotice } from "../../hooks/useNotice";
import CycleSettings from "./CycleSettings";
import { useEffect, useState, useMemo } from "react";
import { api } from "../../api";

export default function SettingsPage() {
  const [headcounts, setHeadcounts] = useState([]);
  const [originalHeadcounts, setOriginalHeadcounts] = useState([]);
  const [colleges, setColleges] = useState([]);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [savingColleges, setSavingColleges] = useState(false);
  const [savingHeadcounts, setSavingHeadcounts] = useState(false);
  const [deletingCollege, setDeletingCollege] = useState(null);
  const [addingCollege, setAddingCollege] = useState(false);
  const [newCollege, setNewCollege] = useState({ code: "", name: "" });
  const [validationErrors, setValidationErrors] = useState({ code: "", name: "" });

  // Survey settings
  const [surveySettings, setSurveySettings] = useState({
    start_date: "",
    end_date: "",
    is_active: true,
    min_trigger_count: 3,
    min_negative_count: 3,
    min_constructive_count: 3,
    alert_window_days: 14,
    default_goal: "short_term",
    include_constructive: "true",
  });
  const [savingSurvey, setSavingSurvey] = useState(false);
  const [savingAlerts, setSavingAlerts] = useState(false);

  // Intervention rules (QUAD-configurable prescribed recommendations)
  const [rules, setRules] = useState([]);
  const [aspects, setAspects] = useState([]);
  const [ruleForm, setRuleForm] = useState(null); // null | { id?, aspect_id, diagnosed_pattern, recommendation, is_active }
  const [ruleErrors, setRuleErrors] = useState({});
  const [savingRule, setSavingRule] = useState(false);
  const [deletingRule, setDeletingRule] = useState(null);
  const [ruleMsg, setRuleMsg] = useState("");
  const [ruleError, setRuleError] = useState("");

  useNotice(msg,"success");
  useNotice(ruleMsg,"success");
  useNotice(error,"error");
  useNotice(ruleError,"error");
  useEffect(() => {
    Promise.all([api.headcounts(), api.colleges(), api.surveySettings(), api.aspects(), api.rules()])
      .then(([h, c, s, a, r]) => {
        setHeadcounts(h);
        setOriginalHeadcounts(h);
        setColleges(c);
        setAspects(a || []);
        setRules(r || []);
        if (s) {
          setSurveySettings({
            start_date: s.start_date ? philippineDay(s.start_date) : "",
            end_date: s.end_date ? philippineDay(s.end_date) : "",
            is_active: s.is_active,
            min_trigger_count: s.min_trigger_count,
            min_negative_count: s.min_negative_count ?? s.min_trigger_count,
            min_constructive_count: s.min_constructive_count ?? s.min_trigger_count,
            alert_window_days: s.alert_window_days,
            default_goal: s.default_goal,
            include_constructive: s.include_constructive == null ? "true" : String(s.include_constructive),
          });
        }
      })
      .catch((err) => setError(err.message));
  }, []);

  // Track if there are any headcount changes
  const hasHeadcountChanges = useMemo(() => {
    if (headcounts.length !== originalHeadcounts.length) return true;
    return headcounts.some((current, index) => {
      const original = originalHeadcounts[index];
      return current.college !== original.college || current.headcount === "" || Number(current.headcount) !== Number(original.headcount);
    });
  }, [headcounts, originalHeadcounts]);

  // Validation
  function validateCode(code) {
    const v = (code || "").trim().toUpperCase();
    if (!v) return "Input a valid College Code";
    if (v.length < 2 || v.length > 4) return "College Code must be 2-4 characters";
    if (!/^[A-Z][A-Z0-9]+$/.test(v)) return "College Code must start with a letter and contain only letters or numbers";
    if (colleges.some((c) => c.code === v)) return "College Code already exists";
    return "";
  }

  function validateName(name) {
    const v = (name || "").trim();
    if (!v) return "Input a valid College Name";
    if (v.length < 2) return "College Name must be at least 2 characters";
    if (colleges.some((c) => c.name.toLowerCase() === v.toLowerCase())) return "College Name already exists";
    return "";
  }

  async function saveHeadcounts() {
    setMsg("");
    setError("");
    const invalid = headcounts.find((row) => row.headcount === "" ||
      !Number.isInteger(Number(row.headcount)) || Number(row.headcount) < 0 || Number(row.headcount) > 100000);
    if (invalid) {
      setError(`Enter a whole number from 0 to 100,000 for ${invalid.college} enrolled students.`);
      return;
    }
    const payload = headcounts.map((row) => ({ ...row, headcount: Number(row.headcount) }));
    setSavingHeadcounts(true);
    try {
      await api.saveHeadcounts(payload);
      setHeadcounts(payload);
      setOriginalHeadcounts(payload);
      setMsg("Enrolled students saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingHeadcounts(false);
    }
  }

  async function confirmAddCollege() {
    const codeErr = validateCode(newCollege.code);
    const nameErr = validateName(newCollege.name);
    if (codeErr || nameErr) {
      setValidationErrors({ code: codeErr, name: nameErr });
      return;
    }
    setAddingCollege(true);
  }

  async function addCollege() {
    const codeErr = validateCode(newCollege.code);
    const nameErr = validateName(newCollege.name);
    if (codeErr || nameErr) {
      setValidationErrors({ code: codeErr, name: nameErr });
      return;
    }
    setAddingCollege(false);
    setError("");
    setMsg("");
    setSavingColleges(true);
    try {
      const payload = {
        code: newCollege.code.trim().toUpperCase(),
        name: newCollege.name.trim(),
      };
      await api.addCollege(payload);
      setNewCollege({ code: "", name: "" });
      setValidationErrors({ code: "", name: "" });
      const updated = await api.colleges();
      setColleges(updated);
      setMsg("College added successfully.");
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingColleges(false);
    }
  }

  async function cancelAdd() {
    setAddingCollege(false);
  }

  async function confirmDeleteCollege(code) {
    setDeletingCollege(code);
  }

  async function deleteCollege() {
    if (!deletingCollege) return;
    setError("");
    setMsg("");
    setSavingColleges(true);
    try {
      await api.deleteCollege(deletingCollege);
      setColleges((c) => c.filter((col) => col.code !== deletingCollege));
      setMsg("College deleted.");
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingColleges(false);
      setDeletingCollege(null);
    }
  }

  async function cancelDelete() {
    setDeletingCollege(null);
  }

  async function saveSurveySettings() {
    setMsg("");
    setError("");
    if (surveySettings.is_active && (!surveySettings.start_date || !surveySettings.end_date)) {
      setError("Enter both the start date and end date before activating the survey.");
      document.getElementById(!surveySettings.start_date ? "survey-start" : "survey-end")?.focus();
      return;
    }
    if (surveySettings.start_date && surveySettings.end_date && surveySettings.start_date > surveySettings.end_date) {
      setError("The end date must be on or after the start date.");
      return;
    }
    setSavingSurvey(true);
    try {
      await api.updateSurveySettings({
        start_date: surveySettings.start_date ? `${surveySettings.start_date}T00:00:00+08:00` : null,
        end_date: surveySettings.end_date ? `${surveySettings.end_date}T23:59:59+08:00` : null,
        is_active: surveySettings.is_active,
      });
      setMsg("Survey period saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingSurvey(false);
    }
  }

  async function saveAlertSettings() {
    setMsg("");
    setError("");
    if (![surveySettings.min_negative_count,surveySettings.min_constructive_count,surveySettings.alert_window_days].every(v=>Number.isInteger(Number(v))&&Number(v)>=1&&Number(v)<=100000)) {setError("Enter whole numbers from 1 to 100,000 for trigger counts and a valid alert window.");return;}
    setSavingAlerts(true);
    try {
      await api.updateSurveySettings({
        min_negative_count: Number(surveySettings.min_negative_count),
        min_constructive_count: Number(surveySettings.min_constructive_count),
        alert_window_days: Number(surveySettings.alert_window_days),
        default_goal: surveySettings.default_goal,
        ...(surveySettings.include_constructive === "mixed" ? {} : {
          include_constructive: surveySettings.include_constructive === "true",
        }),
      });
      localStorage.setItem("quad-alert-settings-updated", String(Date.now()));
      setMsg("Alert settings saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingAlerts(false);
    }
  }

  // ── Intervention rules ──────────────────────────────────────────────
  function aspectName(code) {
    const found = aspects.find((a) => a.code === code);
    return found ? found.name : code;
  }

  function openAddRule() {
    setRuleErrors({});
    setRuleError("");
    setRuleForm({ aspect_id: "", diagnosed_pattern: "", recommendation: "", is_active: true });
  }

  function openEditRule(rule) {
    const aspect = aspects.find((a) => a.code === rule.aspect_code);
    setRuleErrors({});
    setRuleError("");
    setRuleForm({
      id: rule.id,
      aspect_id: aspect ? String(aspect.id) : "",
      diagnosed_pattern: rule.diagnosed_pattern || "",
      recommendation: rule.recommendation || "",
      is_active: rule.is_active !== false,
    });
  }

  function closeRuleForm() {
    setRuleForm(null);
    setRuleErrors({});
    setRuleError("");
  }

  function validateRuleForm(form) {
    const errs = {};
    if (!form.aspect_id) errs.aspect_id = "Choose an aspect.";
    if (form.diagnosed_pattern.trim().length < 3) {
      errs.diagnosed_pattern = "Describe the pattern in at least 3 characters.";
    }
    if (form.recommendation.trim().length < 10) {
      errs.recommendation = "Write at least 10 characters so the recommendation is actionable.";
    }
    // Prevent duplicate rules per aspect client-side; the backend enforces it too.
    const aspect = aspects.find((a) => String(a.id) === String(form.aspect_id));
    if (aspect && rules.some((r) => r.aspect_code === aspect.code && r.id !== form.id)) {
      errs.aspect_id = "This aspect already has a rule — edit that rule instead.";
    }
    return errs;
  }

  async function saveRule() {
    if (!ruleForm) return;
    const errs = validateRuleForm(ruleForm);
    setRuleErrors(errs);
    if (Object.keys(errs).length > 0) return;
    setSavingRule(true);
    setRuleError("");
    setRuleMsg("");
    const payload = {
      aspect_id: Number(ruleForm.aspect_id),
      diagnosed_pattern: ruleForm.diagnosed_pattern.trim(),
      recommendation: ruleForm.recommendation.trim(),
      is_active: ruleForm.is_active,
    };
    try {
      if (ruleForm.id) {
        await api.patchRule(ruleForm.id, payload);
        setRuleMsg("Rule updated.");
      } else {
        await api.createRule(payload);
        setRuleMsg("Rule added.");
      }
      setRules(await api.rules());
      closeRuleForm();
    } catch (err) {
      setRuleError(err.message);
    } finally {
      setSavingRule(false);
    }
  }

  async function confirmDeleteRule() {
    if (!deletingRule) return;
    setSavingRule(true);
    setRuleError("");
    setRuleMsg("");
    try {
      await api.deleteRule(deletingRule.id);
      setRules((rows) => rows.filter((r) => r.id !== deletingRule.id));
      setRuleMsg("Rule deleted.");
    } catch (err) {
      setRuleError(err.message);
    } finally {
      setSavingRule(false);
      setDeletingRule(null);
    }
  }

  return (
    <>
      <header className="dash-topbar">
        <div className="dash-topbar-left">
          <h1 className="dash-title">Settings</h1>
          <p className="dash-subtitle">Survey period, alerts and college management.</p>
        </div>
      </header>

      {error ? <p className="error">{error}</p> : null}


      <div className="settings-top-grid">
      <CycleSettings />
      {/* Survey Period */}
      <section className="card settings-card survey-period-card">
        <h2>Survey period</h2>
        <p className="muted card-desc">Students can only respond while the survey is open.</p>

        <div className="settings-fields">
          <div className="settings-row">
            <label>
              Start Date
              <input
                type="date"
                id="survey-start" required={surveySettings.is_active}
                value={surveySettings.start_date}
                onChange={(e) => setSurveySettings({ ...surveySettings, start_date: e.target.value })}
              />
            </label>
            <label>
              End Date
              <input
                type="date"
                id="survey-end" required={surveySettings.is_active} min={surveySettings.start_date}
                value={surveySettings.end_date}
                onChange={(e) => setSurveySettings({ ...surveySettings, end_date: e.target.value })}
              />
            </label>
          </div>

          <div>
            <label>Survey Status</label>
            <div className="seg-toggle status" role="group" aria-label="Survey status">
              <button
                type="button"
                aria-pressed={surveySettings.is_active}
                className={surveySettings.is_active ? "is-active" : ""}
                onClick={() => {
                  setSurveySettings({ ...surveySettings, is_active: true });
                  if (!surveySettings.start_date || !surveySettings.end_date) {
                    setError("Enter both the start date and end date, then save to activate the survey.");
                    document.getElementById(!surveySettings.start_date ? "survey-start" : "survey-end")?.focus();
                  }
                }}
              >
                Active
              </button>
              <button
                type="button"
                aria-pressed={!surveySettings.is_active}
                className={!surveySettings.is_active ? "is-active" : ""}
                onClick={() => setSurveySettings({ ...surveySettings, is_active: false })}
              >
                Inactive
              </button>
            </div>
          </div>

          <div className="settings-save">
            <button
              type="button"
              className="btn primary"
              onClick={saveSurveySettings}
              disabled={savingSurvey}
            >
              {savingSurvey ? "Saving…" : "Save changes"}
            </button>
          </div>
        </div>
      </section>

      {/* Alerts & Interventions */}
      <section className="card settings-card">
        <h2>Alerts & interventions</h2>
        <p className="muted card-desc">
          Set separate negative and constructive triggers for each service area. Either trigger opens one recommendation entry; new comments update its counts. High priority means at least twice either trigger.
        </p>

        <div className="settings-fields">
          <div className="settings-row">
            <label>
              Minimum negative count
              <input
                type="number"
                min={1}
                value={surveySettings.min_negative_count}
                onChange={(e) => setSurveySettings({ ...surveySettings, min_negative_count: e.target.value })}
              />
            </label>
            <label>Minimum constructive count<input type="number" min={1} max={100000} value={surveySettings.min_constructive_count} onChange={e=>setSurveySettings({...surveySettings,min_constructive_count:e.target.value})}/></label>
            <label>
              Alert Window (Days)
              <input
                type="number"
                min={1}
                value={surveySettings.alert_window_days}
                onChange={(e) => setSurveySettings({ ...surveySettings, alert_window_days: e.target.value })}
              />
            </label>
          </div>

          <label className="settings-constructive-field">
            Constructive feedback
            <select value={surveySettings.include_constructive}
              onChange={(e) => setSurveySettings({ ...surveySettings, include_constructive: e.target.value })}>
              <option value="true">Enable constructive trigger</option>
              <option value="false">Disable constructive trigger</option>
            </select>
          </label>
          <div>
            <label>Default Goal</label>
            <div className="seg-toggle goal-toggle" role="group" aria-label="Default goal">
              <button
                type="button"
                className={surveySettings.default_goal === "short_term" ? "is-active" : ""}
                onClick={() => setSurveySettings({ ...surveySettings, default_goal: "short_term" })}
              >
                Short term
              </button>
              <button
                type="button"
                className={surveySettings.default_goal === "long_term" ? "is-active" : ""}
                onClick={() => setSurveySettings({ ...surveySettings, default_goal: "long_term" })}
              >
                Long term
              </button>
            </div>
          </div>

          <div className="settings-save">
            <button
              type="button"
              className="btn primary"
              onClick={saveAlertSettings}
              disabled={savingAlerts}
            >
              {savingAlerts ? "Saving…" : "Save changes"}
            </button>
          </div>
        </div>
      </section>
      </div>

      {/* Intervention Rules */}
      <section id="intervention-rules" className="card settings-rules">
        <div className="card-header">
          <div>
            <h2>Intervention Rules</h2>
            <p className="muted card-desc">
              Matching rules provide suggestions on the Interventions page. Press Apply to copy a suggestion, then edit it before approval.
            </p>
          </div>
          <button type="button" className="btn primary" onClick={openAddRule}>
            + Add rule
          </button>
        </div>

        {ruleError ? <p className="error">{ruleError}</p> : null}


        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Aspect</th>
                <th>Reported concern</th>
                <th>Suggested action</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rules.length === 0 ? (
                <tr>
                  <td colSpan={5} className="empty-note">
                    No intervention rules yet. Add one to prefill suggestions on the Interventions page.
                  </td>
                </tr>
              ) : rules.map((r) => (
                <tr key={r.id} className={r.is_active === false ? "rule-inactive" : ""}>
                  <td><strong>{aspectName(r.aspect_code)}</strong></td>
                  <td>{r.diagnosed_pattern}</td>
                  <td>{r.recommendation}</td>
                  <td>
                    <span className={`pill ${r.is_active === false ? "negative" : "positive"}`}>
                      {r.is_active === false ? "Inactive" : "Active"}
                    </span>
                  </td>
                  <td><div className="rule-actions">
                    <button
                      type="button"
                      className="btn ghost"
                      onClick={() => openEditRule(r)}
                      disabled={savingRule}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      className="btn ghost danger"
                      onClick={() => { setRuleError(""); setDeletingRule(r); }}
                      disabled={savingRule}
                    >
                      Delete
                    </button>
                  </div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Add / Edit rule form */}
        {ruleForm ? (
          <div className="modal-overlay" onClick={closeRuleForm}>
            <div className="modal rule-modal" onClick={(e) => e.stopPropagation()}>
              <h3>{ruleForm.id ? "Edit Intervention Rule" : "Add Intervention Rule"}</h3>

              <label className="rule-field">
                Aspect
                <select
                  value={ruleForm.aspect_id}
                  onChange={(e) => { setRuleForm({ ...ruleForm, aspect_id: e.target.value }); setRuleErrors({}); }}
                >
                  <option value="">Select an aspect</option>
                  {aspects.map((a) => (
                    <option key={a.id} value={a.id}>{a.name}</option>
                  ))}
                </select>
                {ruleErrors.aspect_id ? <span className="error">{ruleErrors.aspect_id}</span> : null}
              </label>

              <label className="rule-field">
                Reported concern
                <input
                  type="text"
                  maxLength={500}
                  value={ruleForm.diagnosed_pattern}
                  onChange={(e) => setRuleForm({ ...ruleForm, diagnosed_pattern: e.target.value })}
                  placeholder="e.g. Cleanliness and maintenance concerns"
                />
                <small>Describe the reported concern this rule addresses; verify it against the selected comments.</small>
                {ruleErrors.diagnosed_pattern ? <span className="error">{ruleErrors.diagnosed_pattern}</span> : null}
              </label>

              <label className="rule-field">
                Suggested action
                <textarea
                  rows={4}
                  maxLength={4000}
                  value={ruleForm.recommendation}
                  onChange={(e) => setRuleForm({ ...ruleForm, recommendation: e.target.value })}
                  placeholder="e.g. Implement scheduled facility inspections with a checklist and maintenance log."
                />
                <small>This is a reusable suggestion. Review the selected area’s comments before pressing Apply.</small>
                {ruleErrors.recommendation ? <span className="error">{ruleErrors.recommendation}</span> : null}
              </label>

              <div className="rule-field">
                <span className="rule-status-label">Status</span>
                <div className="seg-toggle status" role="group" aria-label="Rule status">
                  <button
                    type="button"
                    aria-pressed={ruleForm.is_active}
                    className={ruleForm.is_active ? "is-active" : ""}
                    onClick={() => setRuleForm({ ...ruleForm, is_active: true })}
                  >
                    Active
                  </button>
                  <button
                    type="button"
                    aria-pressed={!ruleForm.is_active}
                    className={!ruleForm.is_active ? "is-active" : ""}
                    onClick={() => setRuleForm({ ...ruleForm, is_active: false })}
                  >
                    Inactive
                  </button>
                </div>
                <small>Inactive rules are kept but never suggested on the Interventions page.</small>
              </div>

              <div className="modal-actions">
                <button type="button" className="btn ghost" onClick={closeRuleForm}>Cancel</button>
                <button type="button" className="btn primary" onClick={saveRule} disabled={savingRule}>
                  {savingRule ? "Saving…" : "Save Rule"}
                </button>
              </div>
            </div>
          </div>
        ) : null}

        {/* Delete confirmation */}
        {deletingRule ? (
          <div className="modal-overlay" onClick={() => setDeletingRule(null)}>
            <div className="modal" onClick={(e) => e.stopPropagation()}>
              <h3>Delete Intervention Rule?</h3>
              <p>
                Delete the rule for <strong>{aspectName(deletingRule.aspect_code)}</strong>? Existing alerts keep
                their saved recommendation text, but no new suggestion will be made for this aspect.
              </p>
              <div className="modal-actions">
                <button type="button" className="btn ghost" onClick={() => setDeletingRule(null)}>Cancel</button>
                <button type="button" className="btn danger" onClick={confirmDeleteRule} disabled={savingRule}>
                  {savingRule ? "Deleting…" : "Confirm"}
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </section>

      {/* College Management */}
      <section className="card settings-colleges">
        <div className="card-header">
          <h2>College Management</h2>
          {hasHeadcountChanges && (
            <div className="unsaved-changes-banner">
              <span className="unsaved-indicator">●</span>
              <span>You have unsaved changes to enrolled students</span>
              <button
                type="button"
                className="btn primary"
                onClick={saveHeadcounts}
                disabled={savingHeadcounts}
              >
                {savingHeadcounts ? "Saving…" : "Save Changes"}
              </button>
            </div>
          )}
        </div>
        <p className="muted card-desc">
          Add, remove, and configure colleges in the system. Set enrollment headcounts per college to track survey response rates across the university.
        </p>

        {/* College List with Headcounts */}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>College</th>
                <th>Name</th>
                <th>Enrolled Students</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {colleges.map((c) => {
                const headcount = headcounts.find((h) => h.college === c.code);
                const originalHeadcount = originalHeadcounts.find((h) => h.college === c.code);
                const currentHeadcount = headcount ? headcount.headcount : 0;
                const originalCount = originalHeadcount ? originalHeadcount.headcount : 0;
                const isChanged = currentHeadcount === "" || Number(currentHeadcount) !== Number(originalCount);
                return (
                  <tr key={c.code} className={isChanged ? "has-changes" : ""}>
                    <td><strong>{c.code}</strong></td>
                    <td>{c.name}</td>
                    <td>
                      <input
                        type="text"
                        inputMode="numeric"
                        pattern="[0-9]*"
                        aria-label={`${c.code} enrolled students`}
                        disabled={savingHeadcounts}
                        value={currentHeadcount}
                        onChange={(e) => {
                          const value = e.target.value;
                          if (!/^\d*$/.test(value)) return;
                          setHeadcounts((rows) => {
                            const existing = rows.find((r) => r.college === c.code);
                            if (existing) {
                              return rows.map((r) =>
                                r.college === c.code ? { ...r, headcount: value } : r
                              );
                            } else {
                              return [...rows, { college: c.code, name: c.name, headcount: value }];
                            }
                          });
                        }}
                      />
                      {isChanged && <span className="change-indicator" title="Unsaved change">●</span>}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="btn ghost danger"
                        onClick={() => confirmDeleteCollege(c.code)}
                        disabled={savingColleges}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                );
              })}
              {/* Add New College Row at Bottom */}
              <tr className="add-college-row">
                <td>
                  <input
                    type="text"
                    value={newCollege.code}
                    onChange={(e) => {
                      const value = e.target.value.toUpperCase();
                      setNewCollege({ ...newCollege, code: value });
                      setValidationErrors((prev) => ({ ...prev, code: "" }));
                    }}
                    maxLength={4}
                    placeholder="Code"
                  />
                </td>
                <td>
                  <input
                    type="text"
                    value={newCollege.name}
                    onChange={(e) => {
                      setNewCollege({ ...newCollege, name: e.target.value });
                      setValidationErrors((prev) => ({ ...prev, name: "" }));
                    }}
                    placeholder="College Name"
                  />
                </td>
                <td></td>
                <td>
                  <button
                    type="button"
                    className="btn primary"
                    onClick={confirmAddCollege}
                    disabled={!newCollege.code || !newCollege.name || savingColleges}
                  >
                    {savingColleges ? "Adding…" : "Add"}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Add College Confirmation Modal */}
        {addingCollege && (
          <div className="modal-overlay" onClick={cancelAdd}>
            <div className="modal" onClick={(e) => e.stopPropagation()}>
              <h3>Add College?</h3>
              <p>Add <strong>{newCollege.code}</strong> — <strong>{newCollege.name}</strong>?</p>
              <div className="modal-actions">
                <button className="btn ghost" onClick={cancelAdd}>Cancel</button>
                <button className="btn primary" onClick={addCollege} disabled={savingColleges}>
                  {savingColleges ? "Adding…" : "Confirm"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Validation Errors for Add Row */}
        {validationErrors.code && (
          <div className="error add-college-error">Code: {validationErrors.code}</div>
        )}
        {validationErrors.name && (
          <div className="error add-college-error">Name: {validationErrors.name}</div>
        )}

        {/* Delete Confirmation Modal */}
        {deletingCollege && (
          <div className="modal-overlay" onClick={cancelDelete}>
            <div className="modal" onClick={(e) => e.stopPropagation()}>
              <h3>Delete College?</h3>
              <p>Are you sure you want to delete <strong>{deletingCollege}</strong>? This cannot be undone.</p>
              <div className="modal-actions">
                <button className="btn ghost" onClick={cancelDelete}>Cancel</button>
                <button className="btn danger" onClick={deleteCollege} disabled={savingColleges}>
                  {savingColleges ? "Deleting…" : "Confirm"}
                </button>
              </div>
            </div>
          </div>
        )}

      </section>

      <style>{`
        .card-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 1rem;
          gap: 1rem;
        }
        .card-header h2 {
          margin: 0;
        }
        .unsaved-changes-banner {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          padding: 0.75rem 1rem;
          background: #FFF8E6;
          border: 1px solid #FFEBB5;
          border-radius: 8px;
          color: #B8860B;
          font-size: 0.9rem;
        }
        .unsaved-indicator {
          animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
        .change-indicator {
          display: inline-block;
          margin-left: 0.5rem;
          color: #B8860B;
          font-size: 0.8rem;
          animation: pulse 1.5s infinite;
        }
        .has-changes td {
          background: #FFF8E6;
        }
        .has-changes td:first-child {
          border-top-left-radius: 8px;
          border-bottom-left-radius: 8px;
        }
        .has-changes td:last-child {
          border-top-right-radius: 8px;
          border-bottom-right-radius: 8px;
        }
        .add-college-row td {
          border-top: 2px dashed #E7E3D8;
        }
        .add-college-row input {
          width: 100%;
          padding: 0.5rem;
          border: 1px solid #E7E3D8;
          border-radius: 4px;
          font-size: 0.9rem;
        }
        .add-college-error {
          margin-top: 0.5rem;
          font-size: 0.85rem;
        }
        .note-inline {
          color: #2E8B57;
          font-size: 0.9rem;
          margin: 0.5rem 0;
        }
      `}</style>
    </>
  );
}
