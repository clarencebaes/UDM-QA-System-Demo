from app.query_scope import feedback_college
"""Bounded SQL summaries; never hydrate the full evaluation history."""
from sqlalchemy import Integer, and_, case, cast, func
from app.colleges import configured_colleges
from app.services.aspect_labels import effective_aspect_links
from app.services.feedback_text import comment_text, has_comment, has_substantive_comment, no_substantive_feedback
from app.models import SurveySubmission, Alert, Aspect, CollegeHeadcount, Department, Feedback, FeedbackLabel, Respondent


def pct(part, total):
    return round(part / total * 100, 1) if total else None


def sentiment_counts():
    return [cast(func.coalesce(func.sum(case((and_(has_substantive_comment(), FeedbackLabel.sentiment == value), 1), else_=0)), 0), Integer)
            for value in ("positive", "negative", "constructive", "neutral")]


def aggregate_dashboard(db, start_date=None, end_date=None, college=None, section="all"):
    college = college.strip().upper() if college and college != "all" else None
    base = (db.query(Feedback.id).join(Department, Feedback.department_id == Department.id)
            .outerjoin(Respondent, Feedback.respondent_id == Respondent.id)
            .outerjoin(SurveySubmission, Feedback.submission_id == SurveySubmission.id)
            .outerjoin(FeedbackLabel, FeedbackLabel.feedback_id == Feedback.id)
            .outerjoin(Aspect, FeedbackLabel.aspect_id == Aspect.id))
    if college:
        base = base.filter(feedback_college() == college)
    if start_date:
        base = base.filter(Feedback.created_at >= start_date)
    if end_date:
        base = base.filter(Feedback.created_at <= end_date)
    out = dict(total_feedback=0, unique_respondents=0, overall_enrolled=None, overall_response_rate=None,
               positive=0, negative=0, constructive=0, neutral=0, positive_pct=None, negative_pct=None,
               constructive_pct=None, unlabeled=0, by_aspect=[], by_department=[], by_day=[], priority=[],
               service_area_priority=[], service_area_aspect_priority=[], top_aspects=[], concern_aspects=[],
               open_alerts=0, issue_count=0, by_facility=[], by_service_area=[], by_college=[],
               first_response_at=None, last_response_at=None, assistance_requests=[],
               total_comments=0, classified_comments=0, unclassified_comments=0,
               short_unclassified_comments=0, pending_classification_comments=0, unassigned_comments=0,
               written_comments=0, no_substantive_comments=0)
    from app.services.evaluation_analytics import evaluation_analytics
    out.update(evaluation_analytics(base))
    from app.services.text_dimensions import text_dimensions
    out.update(text_dimensions(base))
    if section != "charts":
        written = has_substantive_comment()
        def count_when(condition):
            return cast(func.coalesce(func.sum(case((condition, 1), else_=0)), 0), Integer)
        total, labeled, first, last, pos, neg, con, neu, comments, short, unassigned, all_written, excluded, respondents = base.with_entities(
            func.count(Feedback.id), func.count(FeedbackLabel.id), func.min(Feedback.created_at),
            func.max(Feedback.created_at), *sentiment_counts(), count_when(written),
            count_when(and_(written,func.length(comment_text()) < 3, FeedbackLabel.id.is_(None))),
            count_when(and_(written,Respondent.id.is_(None))), count_when(has_comment()), count_when(no_substantive_feedback()), func.count(func.distinct(Feedback.respondent_id))).one()
        out.update(total_comments=comments, written_comments=all_written, no_substantive_comments=excluded, classified_comments=pos+neg+con+neu,
            unclassified_comments=comments-pos-neg-con-neu, short_unclassified_comments=short,
            pending_classification_comments=comments-pos-neg-con-neu-short, unassigned_comments=unassigned)
        out.update(unique_respondents=respondents, total_feedback=total, unlabeled=total-labeled, first_response_at=first, last_response_at=last,
                   positive=pos, negative=neg, constructive=con, neutral=neu, issue_count=neg+con,
                   positive_pct=pct(pos, pos+neg+con+neu), negative_pct=pct(neg, pos+neg+con+neu),
                   constructive_pct=pct(con, pos+neg+con+neu))
        day = func.date(Feedback.created_at)
        out["by_day"] = [{"date": str(d), "count": n} for d, n in
                         base.with_entities(day, func.count(Feedback.id)).group_by(day).order_by(day).all()]
        stats = {item["code"]: dict(college=item["code"], name=item["name"], responses=0,
                   evaluations=0, comments=0, positive=0, negative=0, constructive=0, neutral=0)
                 for item in configured_colleges(db, include_inactive=True)}
        rows = base.filter(Respondent.id.isnot(None)).with_entities(
            feedback_college(), func.count(func.distinct(Respondent.id)), func.count(Feedback.id),
            func.sum(case((has_substantive_comment(), 1), else_=0)),
            *sentiment_counts()).group_by(feedback_college()).all()
        for code, responses, evaluations, comments, pos, neg, con, neu in rows:
            stats[code] = dict(college=code, name=stats.get(code, {}).get("name", code), responses=responses,
                               evaluations=evaluations, comments=int(comments), positive=pos, negative=neg, constructive=con, neutral=neu)
        headcounts = {r.college: r.headcount for r in db.query(CollegeHeadcount).all()}
        enrolled_total = 0
        for code, row in stats.items():
            enrolled = headcounts.get(code, 0)
            row["enrolled"] = enrolled if enrolled > 0 else None
            row["response_rate"] = pct(row["responses"], enrolled) if enrolled > 0 else None
            for value in ("positive", "negative", "constructive", "neutral"):
                row[value+"_pct"] = pct(row[value], row["positive"]+row["negative"]+row["constructive"]+row["neutral"])
            if not college or code == college:
                enrolled_total += max(0, enrolled)
        out["by_college"] = list(stats.values())
        out["overall_enrolled"] = enrolled_total or None
        out["overall_response_rate"] = pct(out["unique_respondents"], enrolled_total)
    if section != "summary":
        areas = base.with_entities(Department.name, func.count(Feedback.id), *sentiment_counts(),
                    func.avg(Feedback.rating), func.count(Feedback.rating),
                    func.sum(case((has_substantive_comment(), 1), else_=0)))
        for name, total, pos, neg, con, neu, average, rating_count, comments in areas.group_by(Department.name).order_by(func.min(Feedback.id)).all():
            out["by_department"].append(dict(department=name, count=total, comments=int(comments), positive=pos, negative=neg, constructive=con, neutral=neu))
            out["by_service_area"].append(dict(service_area=name, total=total, positive=pos, negative=neg,
                constructive=con, neutral=neu, avg_rating=round(float(average or 0), 2), rating_count=rating_count,
                positive_pct=pct(pos,pos+neg+con+neu), negative_pct=pct(neg,pos+neg+con+neu), constructive_pct=pct(con,pos+neg+con+neu)))
        links = effective_aspect_links()
        aspect_base = (db.query(Feedback.id).join(Department, Feedback.department_id == Department.id)
            .outerjoin(Respondent, Feedback.respondent_id == Respondent.id)
            .outerjoin(SurveySubmission, Feedback.submission_id == SurveySubmission.id)
            .outerjoin(FeedbackLabel, FeedbackLabel.feedback_id == Feedback.id)
            .join(links, links.c.feedback_id == Feedback.id).join(Aspect, Aspect.id == links.c.aspect_id))
        if college: aspect_base = aspect_base.filter(feedback_college() == college)
        if start_date: aspect_base = aspect_base.filter(Feedback.created_at >= start_date)
        if end_date: aspect_base = aspect_base.filter(Feedback.created_at <= end_date)
        aspect_codes = {}
        for name, code, pos, neg, con, neu in aspect_base.filter(FeedbackLabel.id.isnot(None), has_substantive_comment()).with_entities(
                Aspect.name, Aspect.code, *sentiment_counts()).group_by(Aspect.name, Aspect.code).order_by(func.min(Feedback.id)).all():
            name = name or "Unknown"
            aspect_codes[name] = code or ""
            out["by_aspect"].append(dict(aspect=name, positive=pos, negative=neg, constructive=con, neutral=neu))
        out["top_aspects"] = sorted([dict(aspect=r["aspect"], count=r["positive"]+r["negative"]+r["constructive"]+r["neutral"]) for r in out["by_aspect"]], key=lambda r:r["count"], reverse=True)
        ranked = sorted(out["by_aspect"], key=lambda r:r["negative"], reverse=True)
        out["priority"] = [dict(aspect=r["aspect"], aspect_code=aspect_codes[r["aspect"]], negative=r["negative"], total=r["positive"]+r["negative"]+r["constructive"]+r["neutral"], rank=i+1) for i,r in enumerate(ranked)]
        ranked = sorted([dict(service_area=r["service_area"], negative=r["negative"], constructive=r["constructive"], positive=r["positive"], total=r["total"], negative_pct=round(r["negative"]/r["total"]*100)) for r in out["by_service_area"]], key=lambda r:(r["negative"],r["negative_pct"]), reverse=True)
        out["service_area_priority"] = [dict(**r, rank=i+1, level="high" if r["negative_pct"]>=35 or i<2 else "medium" if r["negative_pct"]>=20 or i<4 else "low") for i,r in enumerate(ranked)]
        pairs = aspect_base.filter(has_substantive_comment(), FeedbackLabel.sentiment.in_(["negative", "constructive"])).with_entities(
            Department.name, Aspect.name, FeedbackLabel.sentiment, func.count(Feedback.id)).group_by(Department.name, Aspect.name, FeedbackLabel.sentiment).order_by(func.min(Feedback.id)).all()
        pairs = sorted([dict(service_area=a, aspect=b or "Unknown", classification=c, count=n) for a,b,c,n in pairs], key=lambda r:r["count"], reverse=True)
        out["service_area_aspect_priority"] = [dict(**r, rank=i+1, level="high" if r["count"]>=5 else "medium" if r["count"]>=2 else "low") for i,r in enumerate(pairs[:15])]
        out["concern_aspects"] = sorted([dict(**r, concern_count=r["negative"]+r["constructive"]) for r in out["by_aspect"]], key=lambda r:(r["concern_count"],r["negative"]), reverse=True)
        out["by_facility"] = out["by_service_area"]
    if section == "all":
        out["open_alerts"] = db.query(func.count(Alert.id)).filter(Alert.status.in_(["new", "acknowledged", "in-progress"])).scalar() or 0
        # One latest entry per respondent; legacy unlinked evaluations stay distinct.
        identity = case((Feedback.respondent_id.isnot(None), Feedback.respondent_id), else_=-Feedback.id)
        ranked = base.with_entities(Feedback.id.label("feedback_id"),
            func.row_number().over(partition_by=identity,
                order_by=(Feedback.created_at.desc(),Feedback.id.desc())).label("position")).subquery()
        out["assistance_requests"] = [dict(student_number=number or "—", created_at=stamp) for number,stamp in
            db.query(func.coalesce(Respondent.student_number,Feedback.student_number),Feedback.created_at)
              .select_from(Feedback).join(ranked,ranked.c.feedback_id==Feedback.id)
              .outerjoin(Respondent,Respondent.id==Feedback.respondent_id)
              .filter(ranked.c.position==1)
              .order_by(Feedback.created_at.desc(),Feedback.id.desc()).limit(10).all()]
    if any(k in db.info for k in ("read_cycle", "answered_from", "answered_through")):
        out["overall_enrolled"] = None
        out["overall_response_rate"] = None
        for row in out["by_college"]:
            row["enrolled"] = None
            row["response_rate"] = None
    return out
