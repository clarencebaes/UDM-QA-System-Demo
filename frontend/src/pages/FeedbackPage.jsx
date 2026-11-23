import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { isValidEmail, isValidStudentNumber } from "../studentIdentity";

export default function FeedbackPage() {
  const navigate = useNavigate();
  const [departments, setDepartments] = useState([]);
  const [aspects, setAspects] = useState([]);
  const [colleges, setColleges] = useState([]);
  const [form, setForm] = useState({
    department_id: "",
    aspect_id: "",
    comment: "",
    rating: 3,
    student_number: "",
    institutional_email: "",
    college: "",
    consent: false,
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([api.departments(), api.aspects(), api.colleges()])
      .then(([d, a, c]) => {
        setDepartments(d);
        setAspects(a);
        setColleges(c);
      })
      .catch((err) => setError(err.message));
  }, []);

  function update(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    if (!form.department_id) {
      setError("Please choose a facility.");
      return;
    }
    if (form.comment.trim().length < 10) {
      setError("Please write at least 10 characters so the classifier has enough text.");
      return;
    }
    const student_number = form.student_number.trim().toUpperCase();
    if (!student_number) {
      setError("Student number is required.");
      return;
    }
    if (!isValidStudentNumber(student_number)) {
      setError("Enter a student number in the format ##-##-### (digits and hyphens only).");
      return;
    }
    const institutional_email = form.institutional_email.trim();
    if (!institutional_email) {
      setError("Institutional Email is required.");
      return;
    }
    if (!isValidEmail(institutional_email)) {
      setError("Enter a valid email address.");
      return;
    }
    if (!form.college) {
      setError("Please select your college.");
      return;
    }
    if (!colleges.some((c) => c.code === form.college)) {
      setError("Please select a valid college.");
      return;
    }
    if (!form.consent) {
      setError("Please confirm the privacy consent checkbox.");
      return;
    }
    setBusy(true);
    try {
      await api.submitFeedback({
        department_id: Number(form.department_id),
        aspect_id: form.aspect_id ? Number(form.aspect_id) : null,
        comment: form.comment.trim(),
        rating: form.rating,
        student_number,
        institutional_email,
        college: form.college,
        consent: true,
      });
      navigate("/thanks");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page narrow">
      <h1>Submit facility evaluation</h1>
      <p className="lead">
        This form is for <strong>non-academic facilities</strong> only (comfort rooms, library, classrooms, security, canteen). You may write in English, Filipino, or Taglish.
      </p>

      <form className="card form" onSubmit={onSubmit}>
        <label>
          Facility <span className="req">required</span>
          <select
            value={form.department_id}
            onChange={(e) => update("department_id", e.target.value)}
          >
            <option value="">Select a facility</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </label>

        <label>
          Star rating
          <div className="rating-row">
            {[1, 2, 3, 4, 5].map((star) => (
              <button
                key={star}
                type="button"
                className={`star-btn ${form.rating >= star ? "active" : ""}`}
                onClick={() => update("rating", star)}
                aria-label={`Rate ${star} out of 5`}
              >
                ★
              </button>
            ))}
            <span className="rating-label">
              {form.rating >= 1 ? ["Very Poor", "Poor", "Average", "Good", "Excellent"][form.rating - 1] : ""}
            </span>
          </div>
        </label>

        <label>
          Aspect (optional — leave blank to let Naïve Bayes detect it)
          <select
            value={form.aspect_id}
            onChange={(e) => update("aspect_id", e.target.value)}
          >
            <option value="">Auto-detect aspect</option>
            {aspects.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </label>

        <label>
          Your comment <span className="req">required</span>
          <textarea
            rows={7}
            value={form.comment}
            onChange={(e) => update("comment", e.target.value)}
            placeholder="Halimbawa: Sobrang tagal ng pila sa registrar at hindi clear yung requirements..."
          />
        </label>

        <label>
          Student number <span className="req">required</span>
          <input
            type="text"
            value={form.student_number}
            onChange={(e) => update("student_number", e.target.value)}
            placeholder="##-##-###"
            required
          />
        </label>

        <label>
          Institutional Email <span className="req">required</span>
          <input
            type="email"
            value={form.institutional_email}
            onChange={(e) => update("institutional_email", e.target.value)}
            placeholder="you@example.com"
            required
          />
        </label>

        <label>
          College <span className="req">required</span>
          <select
            value={form.college}
            onChange={(e) => update("college", e.target.value)}
            required
          >
            <option value="">Select your college</option>
            {colleges.map((c) => (
              <option key={c.code} value={c.code}>
                {c.code} — {c.name}
              </option>
            ))}
          </select>
        </label>

        <label className="check">
          <input
            type="checkbox"
            checked={form.consent}
            onChange={(e) => update("consent", e.target.checked)}
          />
          <span>
            I agree that this comment will be stored for quality assurance under
            the Data Privacy Act of 2012 (RA 10173).
          </span>
        </label>

        {error ? <p className="error">{error}</p> : null}

        <button className="btn primary" type="submit" disabled={busy}>
          {busy ? "Sending…" : "Send evaluation"}
        </button>
      </form>
    </main>
  );
}
