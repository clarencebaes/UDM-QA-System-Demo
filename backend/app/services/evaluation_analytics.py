"""Rating counts include evaluations without comments."""
from sqlalchemy import case, func
from app.models import Feedback, SurveySubmission, Department
from app.query_scope import feedback_college


def evaluation_analytics(q):
    ratings = [Feedback.rating_1, Feedback.rating_2, Feedback.rating_3]
    legacy = case((Feedback.rating_1.is_(None) & Feedback.rating_2.is_(None) & Feedback.rating_3.is_(None), Feedback.rating), else_=None)
    values = ratings + [legacy]
    counts = [sum(func.sum(case((column == star, 1), else_=0)) for column in values) for star in range(1,6)]
    rows = q.with_entities(Department.name, func.count(Feedback.id), *counts).group_by(Department.id, Department.name).order_by(Department.name).all()
    stars=[]
    for area, evaluations, *distribution in rows:
        distribution=[int(n or 0) for n in distribution]
        total=sum(distribution)
        stars.append(dict(service_area=area,evaluations=evaluations,rated_answers=total,
                          stars={str(i+1):n for i,n in enumerate(distribution)},
                          mean=round(sum((i+1)*n for i,n in enumerate(distribution))/total,2) if total else None))
    status=func.coalesce(SurveySubmission.student_status,Feedback.student_status,"unknown")
    # Use the most recent status in the selection so a student whose status
    # changes between semesters is not counted twice in the all-period view.
    latest=q.filter(Feedback.respondent_id.isnot(None)).with_entities(
        Feedback.respondent_id.label("respondent_id"),status.label("student_status"),feedback_college().label("college"),
        func.row_number().over(partition_by=Feedback.respondent_id,order_by=(Feedback.created_at.desc(),Feedback.id.desc())).label("position")).subquery()
    by_college=[dict(college=college,status=label,respondents=n) for college,label,n in q.session.query(latest.c.college,latest.c.student_status,func.count()).filter(latest.c.position==1).group_by(latest.c.college,latest.c.student_status)]
    totals={}
    for row in by_college: totals[row["status"]]=totals.get(row["status"],0)+row["respondents"]
    statuses=[dict(status=label,respondents=n) for label,n in totals.items()]
    return dict(star_ratings=stars,student_status=statuses,status_by_college=by_college)
