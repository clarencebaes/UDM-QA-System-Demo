import { Link, useLocation } from "react-router-dom";
import { getProfile } from "../api";
import { ROLE_NAMES, roleOf, can } from "../permissions";

const REPORT = ["How do I make a report?", "Open Reports, choose the academic year, semester, colleges, service area, and student status. Select the sections you need, or choose All, then select Preview report. Ratings are arranged from highest to lowest. Student status includes counts and percentages, while sentiment includes the total number of comments. Add Language distribution to include English, Tagalog, Taglish and Unclassified counts. Use Print / Save as PDF for a copy. Intervention progress lists recorded actions across semesters; college and semester filters apply to evaluation results."];
const COUNTS = ["Why are receipt counts lower than respondent counts?", "Respondents count students with saved evaluations, including older records. Receipt counts cover the newer complete-submission process only. Older responses were saved before receipt tracking, so a missing receipt does not mean a student left the survey unfinished. The current survey accepts all required service-area answers together and saves none if validation fails."];
const DASHBOARD = ["How do I filter the dashboard?", "In Dashboard, use the evaluation period and college controls in Comment sentiment distribution. These update the response counts, sentiment results, and Survey breakdown together. The five categories include Unclassified for unclear written feedback. Their total matches the Comments count and the detected-language total for the same filters. N/A, no-comment and blank answers remain stored evaluations but are excluded from written-comment lists."];
const ANALYTICS = ["How do I read the rating results?", "Classification distribution shows Positive, Constructive, Negative, Neutral and Unclassified written comments. Both rings show their total in the center and below the legend. Use Language to view English, Tagalog or Taglish; short or unclear text remains Unclassified. Typos and common texting shortcuts are considered, but predictions still need staff review. Open Analytics to see the star ratings for each service area, including ratings without written comments. Use Arrange by to view service areas by name, highest rating, or lowest rating. College analytics includes Regular and Irregular counts. Classification by service area shows six rows per page. Saved evaluations count one answer per service area, including ratings without comments. In one semester, complete submissions give equal counts across required service areas, except Laboratory. Older missing or repeated records can make those totals differ."];

const PROFILE = ["How do I change my credentials?", "Open My profile and enter your current password with the changes. A new password needs at least 12 characters with letters and numbers. Saving credentials signs you out of existing sessions; sign in again with the updated details."];
const DRAFT = ["How do I prepare a recommendation?", "Open Interventions, select a service area and review its comments and reported aspects. Apply the short suggested steps or write your own recommendation, then save a draft. An Executive Director must approve it before it can be completed."];
const COMPLETE = ["How do I record a completed action?", "In Interventions, find an approved recommendation in follow-up. Record the action actually taken, then mark it complete. Completed actions remain available in History."];
const CONCERNS = ["How do I handle a student concern?", "Open Student concerns and choose View concern. Verify the student's details through the university's established process, record staff remarks, and update the status. Receiving a concern does not automatically change or delete an evaluation."];
const APPROVE = ["How do I approve a recommendation?", "Review the supporting comments and proposed action in Interventions. Approve the recommendation when it is ready for implementation. Approval and completion are separate steps; completion requires a record of the action taken."];
const USERS = ["How do I manage staff access?", "Open Users to create or edit a named account and choose its role. Deactivate accounts that no longer need access; their history is retained. Account changes revoke previous sessions. You cannot deactivate your own account or remove the last active Executive Director."];
const FAQS = {
  viewer: [REPORT, COUNTS, ["Can I edit records or see student identities?", "Your Read-Only Viewer account provides aggregate reports and your own profile. Student-level feedback, concerns, account administration, and system settings are unavailable."], PROFILE],
  assistant: [DASHBOARD, ANALYTICS, REPORT, COUNTS, ["Can I change records?", "Staff access is read-only. You can view feedback, analytics, recommendations and reports. Administrators handle operational changes and student concerns. The Executive Director approves recommendations."], PROFILE],
  admin: [DASHBOARD, ANALYTICS, DRAFT, COMPLETE, CONCERNS, REPORT, COUNTS, PROFILE],
  executive_director: [DASHBOARD, ANALYTICS, COUNTS, APPROVE, COMPLETE, USERS, ["Which accounts can I manage?", "You have the highest access and can manage all roles. Administrators can manage Administrator, Staff and Viewer accounts but cannot create or edit Director accounts."], ["Where can I review changes?", "Open Audit trail to search recorded actors, actions, and records. Expand View changes to see details and timestamps in Philippine time."], CONCERNS, REPORT, PROFILE],
  executive_director_help: [["How do I open the semester survey?", "In Settings, create the academic year and semester at the top of the page, then select it and choose Use this semester. Changing semesters closes the survey and clears the previous schedule. In Survey period, enter both start and end dates, choose Active, and save. Submissions are accepted only within those dates."], ["What happens when I create a cycle?", "Creating a cycle adds it to the list; it does not activate it. A green confirmation tells you to select the cycle before using it."], DASHBOARD, ANALYTICS, COUNTS, USERS, APPROVE, COMPLETE, CONCERNS, ["How do backup and restore work?", "Use Backup & restore to download an encrypted application-data backup. Keep the file and installation encryption secret securely. Restore requires your current password and the RESTORE confirmation. It retains audit history, closes the survey, and signs out existing sessions. Backups do not contain model files or hosting configuration."], REPORT, PROFILE],
};
FAQS.executive_director = [...FAQS.executive_director_help.slice(0, 2), ...FAQS.executive_director, FAQS.executive_director_help.find(([q]) => q.includes("backup"))];
FAQS.admin = [...FAQS.executive_director_help.slice(0, 2), ...FAQS.admin, USERS];
const STUDENT = [
  ["How do I start my evaluation?", "Check the survey schedule on the home page, read and accept the consent notice, and start the evaluation. Enter your student number, institutional email, college, and Regular or Irregular status."],
  ["What do I need to answer?", "Rate all three questions for each applicable service area. If you select one or two stars, explain your experience in a comment of at least 10 characters. You may write in English, Filipino, or Taglish."],
  ["Are unfinished surveys saved?", "Your unfinished ratings, comments and current page are saved in this browser tab and return after a reload. A message on the form confirms draft saving. This draft is not yet sent to QUAD. Submit all required answers to record your evaluation. Closing the tab or clearing browser data may remove the draft."],
  ["Can I answer again next semester?", "Yes, when the next semester survey opens. One submission is accepted for your student number and institutional email per semester."],
  ["Are my answers anonymous?", "No. Your student number and institutional email are collected with your answers. Authorized staff can review records. Aggregate reports exclude those identifiers. Avoid including someone else's private information in comments."],
  ["Where can I see my submitted answers?", "After evaluating, you will see a brief summary of the semester, your information, date, ratings, and comments in the same browser tab. Save the reference number immediately: it is shown only on the first confirmation screen in that browser tab and hidden after reload or a later visit. Keep it for concerns."],
  ["What if I see a duplicate warning or made a mistake?", "Choose Report in the header, select the concern type, and explain what happened. Include your reference number if you have one. QUAD staff will review your concern; this does not automatically replace your answers."],
];
const DESTINATIONS=[
 ["Reports","/qa/reports","reports"], ["Dashboard","/qa/dashboard","dashboard"], ["Analytics","/qa/analytics","analytics"], ["Interventions","/qa/alerts","alerts"],
 ["History","/qa/history","history"], ["Student concerns","/qa/concerns","concerns"],
 ["Users","/qa/users","users"], ["Settings","/qa/settings","settings"],
 ["Audit trail","/qa/audit","audit"], ["Backup & restore","/qa/backup","backup"],
 ["My profile","/qa/profile","profile"],
];

function FaqAnswer({ text, destinations }) {
  if (!destinations.length) return text;
  const labels = destinations.map(([label]) => label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const parts = text.split(new RegExp(`\\b(${labels.join("|")})\\b`));
  return parts.map((part,index) => {
    const destination = destinations.find(([label]) => label === part);
    return destination ? <Link className="faq-inline-link" key={index} to={destination[1]}>{part}</Link> : part;
  });
}

export default function InformationPage() {
  const { pathname } = useLocation();
  const staff = pathname.startsWith("/qa"), about = pathname.endsWith("about");
  const role = roleOf(getProfile());
  const entries = staff ? FAQS[role] || [] : STUDENT;
  const destinations = staff ? DESTINATIONS.filter(([, ,area]) => can(role,area)) : [["home page","/"],["Report","/concern"]];
  return <main className="ops-page info-page"><p className="eyebrow">Universidad de Manila</p><h1>{about ? "About this project" : staff ? `${ROLE_NAMES[role]} FAQs` : "Student FAQs"}</h1>
    {about ? <>
      <section className="ops-card"><h2>A Web-Based Student Facility Evaluation and Prescriptive Intervention System Using Aspect-Based Naïve Bayes for Administrative Quality Assurance at Universidad de Manila</h2><p className="eyebrow">BSIT - 42 · College of Computing Studies</p><p>A capstone project at Universidad de Manila that organizes student ratings and written feedback on university facilities and services for the Quality Assurance and Accreditation Division (QUAD).</p><p>Using aspect-based text classification, the project helps QUAD identify recurring concerns, review service trends, and plan and track recommended improvement actions.</p></section>

    </> : entries.map(([q,a]) => <details className="ops-card faq-item" key={q}><summary>{q}</summary><p><FaqAnswer text={a} destinations={destinations}/></p></details>)}
  </main>;
}
