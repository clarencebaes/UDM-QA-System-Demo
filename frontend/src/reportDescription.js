import { sentimentDistribution } from "./sentimentDistribution.js";
export const OUTPUT_NAMES = {language:"Language distribution",participation:"Participation",ratings:"Ratings",concerns:"Concerns",actions:"Action status",interventions:"Intervention progress",completed:"Completed interventions",sentiment:"Sentiment distribution",stars:"Star rating distribution",student_status:"Student status",aspects:"Aspect analysis"};
export function reportTitle(sections) {
  if(sections.length===1 && sections[0]==="completed")return "Completed Intervention Report";
  if(sections.every(s=>["actions","interventions","completed"].includes(s)))return "Intervention Progress Report";
  if(sections.some(s=>["actions","interventions","completed"].includes(s)))return "Student Evaluation and Intervention Report";
  return sections.length===1 ? `${OUTPUT_NAMES[sections[0]]} Report` : "Student Evaluation Report";
}
export function reportDescription(report,sections) {
  const facts=[];
  if(sections.includes("participation"))facts.push(`${report.respondents} distinct students provided ${report.evaluations} service-area evaluations.`);
  if(sections.includes("ratings")){
    const rated=report.ratings.filter(r=>r.mean!==null);
    facts.push(rated.length?`Mean ratings range from ${Math.min(...rated.map(r=>r.mean)).toFixed(2)} to ${Math.max(...rated.map(r=>r.mean)).toFixed(2)} out of 5 across ${rated.length} rated service areas.`:"No answered rating questions match this selection.");
  }
  if(sections.includes("sentiment")){const p=sentimentDistribution(report);facts.push(`The selection contains ${report.comments} comments: ${p.positive} positive, ${p.constructive} constructive, ${p.negative} negative, ${p.neutral} neutral and ${p.unclassified} unclassified.`);}
  if(sections.includes("language")){const l=report.language_counts||{};facts.push(`Detected languages: ${l.english||0} English, ${l.tagalog||0} Tagalog and ${l.taglish||0} Taglish; ${l.undetermined||0} unclassified.`);}
  if(sections.includes("stars"))facts.push(`Star rating counts cover ${report.star_ratings?.length||0} service areas, including evaluations without comments.`);
  if(sections.includes("student_status")){const count=(report.student_status||[]).reduce((n,r)=>n+r.respondents,0);facts.push(`The student-status breakdown covers ${count} ${count===1?"respondent":"respondents"}, using each student's latest recorded status.`);}
  if(sections.includes("aspects"))facts.push(`Aspect analysis shows ${report.aspect_analysis?.length||0} classified themes; a comment can belong to more than one theme.`);
  if(sections.includes("concerns"))facts.push(`${report.concerns.length} service-area and aspect combinations contain classified concerns for review.`);
  if(sections.includes("recommendations"))facts.push(`${report.concerns.length} recommendations are presented with the corresponding comment counts and service areas.`);
  if(sections.some(s=>["actions","interventions"].includes(s)))facts.push(`The related action register contains ${report.intervention_summary.awaiting} drafts awaiting approval, ${report.intervention_summary.approved} approved actions in progress and ${report.intervention_summary.completed} completed actions.`);
  if(sections.includes("completed"))facts.push(`${report.completed_interventions.length} completed campus-wide ${report.completed_interventions.length===1?"intervention is":"interventions are"} listed with their recorded action taken and completion date. These action records are not assigned to a college or semester.`);
  return facts.join(" ");
}
