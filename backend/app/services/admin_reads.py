from app.services.text_dimensions import polarity_sql, constructive_clause, category_sql, COMMENT_CATEGORIES
from app.query_scope import feedback_college
"""Read-only paginated feedback and bounded intervention summaries."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import String, and_, case, cast, func, or_, select
from sqlalchemy.orm import joinedload, selectinload, aliased
from app.services.aspect_labels import aspect_matches, effective_aspect_links
from app.services.feedback_text import has_comment, has_substantive_comment, no_substantive_feedback
from app.models import SurveySubmission, Alert, Aspect, Department, Feedback, FeedbackLabel, Respondent, Threshold, FeedbackAspectRun, FeedbackAspectTag


def feedback_query(db):
    return (db.query(Feedback).join(Department, Feedback.department_id == Department.id)
            .outerjoin(Respondent, Feedback.respondent_id == Respondent.id)
            .outerjoin(SurveySubmission, Feedback.submission_id == SurveySubmission.id)
            .outerjoin(FeedbackLabel, FeedbackLabel.feedback_id == Feedback.id)
            .outerjoin(Aspect, Aspect.id == FeedbackLabel.aspect_id))


def load_options():
    return (joinedload(Feedback.department), joinedload(Feedback.respondent), joinedload(Feedback.submission),
            joinedload(Feedback.label).joinedload(FeedbackLabel.aspect),
            joinedload(Feedback.aspect_run).selectinload(FeedbackAspectRun.tags).joinedload(FeedbackAspectTag.aspect))


def comments_clause():
    return has_substantive_comment()


def feedback_page(db, page=1, page_size=10, search=None, department=None, college=None,
                  aspect=None, sentiment=None, comments_only=True, start_date=None, end_date=None, language="all"):
    q = feedback_query(db)
    if comments_only:
        q = q.filter(comments_clause())
    if language != "all":
        from app.services.text_dimensions import language_sql
        q = q.filter(language_sql() == ("undetermined" if language == "unclassified" else language))
    for value, column in ((department, Department.name), (college, feedback_college())):
        if value and value != "all":
            q = q.filter(column == value)
    if aspect == "N/A":
        links = effective_aspect_links()
        q = q.filter(or_(no_substantive_feedback(), ~Feedback.id.in_(db.query(links.c.feedback_id))))
    elif aspect and aspect != "all":
        q = q.filter(aspect_matches(db.query(Aspect.id).filter(Aspect.name == aspect).scalar() or -1))
    if search and search.strip():
        unclassified = or_(no_substantive_feedback(), FeedbackLabel.id.is_(None), ~FeedbackLabel.sentiment.in_(["positive","negative","neutral","constructive"]))
        written_unclassified = and_(has_substantive_comment(), unclassified)
        # Treat %, _ and backslash literally, not as SQL wildcard operators.
        value = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        identity = func.coalesce(Respondent.student_number, Feedback.student_number, "")
        pattern = "%" + value + "%"
        def matches(column):
            # Existing MySQL installations can mix binary and locale collations.
            if db.get_bind().dialect.name == "mysql":
                column = cast(column, String).collate("utf8mb4_unicode_ci")
            return column.ilike(pattern, escape="\\")
        links = effective_aspect_links()
        aspect_ids = select(Aspect.id).where(matches(Aspect.name))
        q = q.filter(written_unclassified if search.strip().casefold() == "unclassified written" else or_(
            matches(identity + " " + cast(Feedback.id, String)),
            matches(Respondent.institutional_email), matches(Feedback.comment), matches(Department.name),
            matches(feedback_college()), matches(category_sql()),
            Feedback.id.in_(select(links.c.feedback_id).where(links.c.aspect_id.in_(aspect_ids))),
        ))
    if start_date:
        q = q.filter(Feedback.created_at >= start_date)
    if end_date:
        q = q.filter(Feedback.created_at <= end_date)
    categories={key:category_sql()==key for key in COMMENT_CATEGORIES}
    counts={"all":q.count()}
    values=q.with_entities(*[func.coalesce(func.sum(case((and_(has_substantive_comment(),condition),1),else_=0)),0) for condition in categories.values()]).one()
    counts.update(dict(zip(categories,map(int,values))))
    # Old clients may still send the previous status names during rollout.
    if sentiment in ("no_substantive", "uncertain"):
        sentiment = "unclassified"
    selected = set((sentiment or "all").split(","))
    if "all" not in selected:
        q = q.filter(has_substantive_comment(), category_sql().in_(selected))
    total = q.count() if "all" not in selected else counts["all"]
    page = min(page, max(1, (total+page_size-1)//page_size))
    items = q.options(*load_options()).order_by(Feedback.created_at.desc(), Feedback.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return dict(items=items, total=total, page=page, page_size=page_size, counts=counts)


def feedback_options(db):
    q = feedback_query(db)
    return dict(service_areas=[v for v, in q.with_entities(Department.name).distinct().order_by(Department.name).all() if v],
                colleges=[v for v, in q.with_entities(feedback_college()).distinct().order_by(feedback_college()).all() if v],
                aspects=[a.name for a in db.query(Aspect).order_by(Aspect.name).all()] + ["N/A"])


def most_commented(db, page=1, page_size=4, department=None):
    q = feedback_query(db).filter(has_substantive_comment())
    if department and department != "all":
        q = q.filter(Department.name == department)
    groups = q.with_entities(Department.name, func.count(Feedback.id)).group_by(Department.name).order_by(func.count(Feedback.id).desc(), Department.name).all()
    total = len(groups)
    page = min(page, max(1,(total+page_size-1)//page_size))
    items = []
    for area, count in groups[(page-1)*page_size:page*page_size]:
        preview = q.filter(Department.name==area).with_entities(Feedback.comment,FeedbackLabel.sentiment).order_by(Feedback.created_at.desc(),Feedback.id.desc()).limit(2).all()
        items.append(dict(area=area, count=count, comments=[dict(text=t,sentiment=s) for t,s in preview]))
    return dict(items=items,total=total,page=page,page_size=page_size)


def intervention_view(db, college=None, now=None, page=1, page_size=2):
    from app.services.alerts import sync_service_area_alerts
    groups, since = sync_service_area_alerts(db, now)
    summaries, pairs, conditions = [], [], []
    for area_id, counts in groups.items():
        if not counts["eligible"]:
            continue
        alert = (db.query(Alert).filter(Alert.department_id == area_id, Alert.status.in_(["new", "acknowledged", "in-progress"]))
                 .order_by(Alert.created_at.desc(), Alert.id.desc()).first())
        if not alert:
            continue
        q = feedback_query(db).filter(Feedback.department_id == area_id, Feedback.created_at >= since,
             has_substantive_comment(), FeedbackLabel.sentiment.in_(["negative", "constructive"]))
        links = effective_aspect_links()
        tagged_aspect = aliased(Aspect)
        tagged = [(name,code) for name,code in q.join(links, links.c.feedback_id == Feedback.id).join(tagged_aspect, tagged_aspect.id == links.c.aspect_id)
                 .with_entities(tagged_aspect.name,tagged_aspect.code).distinct().order_by(tagged_aspect.name)]
        names = [name for name,code in tagged]
        summary = dict(service_area=alert.department.name, aspect="; ".join(names) or alert.aspect.name,
            aspect_names=names, aspect_codes=[code for name,code in tagged], aspect_code="all", alert_id=alert.id, negative=counts["negative"], constructive=counts["constructive"],
            count=counts["total"], min_count=counts["min_negative_count"],
            min_negative_count=counts["min_negative_count"], min_constructive_count=counts["min_constructive_count"],
            include_constructive=counts["include_constructive"], window_days=counts["window_days"], area_count=1, level=counts["level"])
        summaries.append(summary)
        pairs.append({**summary, "aspect_count":summary["count"]})
        conditions.append(Feedback.department_id == area_id)
    pairs.sort(key=lambda item:(-item["count"],item["service_area"]))
    preview, total, group_total = [], 0, 0
    if conditions:
        q = feedback_query(db).filter(or_(*conditions), Feedback.created_at>=since, has_substantive_comment(), polarity_sql()=="negative")
        if college and college != "all":
            q = q.filter(feedback_college()==college.strip().upper())
        total = q.count()
        group_total = q.with_entities(func.count(func.distinct(Feedback.department_id))).scalar() or 0
        page = min(page,max(1,(total+page_size-1)//page_size))
        preview = q.options(*load_options()).order_by(Feedback.created_at.desc(),Feedback.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return dict(aspects=summaries,pairs=pairs,feedback=preview,feedback_total=total,feedback_page=page if total else 1,
                feedback_page_size=page_size,feedback_group_total=group_total)


def selected_area_detail(db, department, aspect_code):
    """Extractive evidence for a selected pair; no generated or relabeled claims."""
    aspect = db.query(Aspect).filter(Aspect.code == aspect_code).first() if aspect_code != "all" else db.query(Aspect).first()
    area = db.query(Department).filter(Department.name == department).first()
    threshold = db.query(Threshold).filter(Threshold.aspect_id == aspect.id).first() if aspect else None
    if not area or not aspect or not threshold:
        return None
    from app.services.alerts import service_area_evidence
    groups, since = service_area_evidence(db)
    days = groups.get(area.id, {}).get("window_days", threshold.window_days)
    q = feedback_query(db).filter(Feedback.department_id == area.id,
        Feedback.created_at >= since,has_substantive_comment(),
        FeedbackLabel.sentiment.in_(["negative","constructive"]))
    if aspect_code != "all": q = q.filter(aspect_matches(aspect.id))
    negative,constructive=q.with_entities(func.coalesce(func.sum(case((polarity_sql()=="negative",1),else_=0)),0),func.coalesce(func.sum(case((constructive_clause(),1),else_=0)),0)).one()
    counts=dict(negative=int(negative),constructive=int(constructive))
    total=q.count()
    # Count literal mentions in the actual selected comments. These are quoted
    # terms, not an assertion that every occurrence is an affirmed complaint.
    terms = {
        "processing_time":["slow","late","waiting","delayed","delay","mabagal","matagal"],
        "staff_responsiveness":["rude","helpful","approachable","staff","accommodating","masungit"],
        "communication_clarity":["unclear","instructions","requirements","announcement","confusing"],
        "service_accessibility":["access","hours","available","closed","schedule","open"],
        "digital_services":["internet","wifi","website","connection","slow"],
        "affordability_value":["price","expensive","mahal","affordable"],
        "service_program_quality":["quality","food","activities","teaching","program"],
        "fairness_inclusion_policy":["fair","rules","policy","equal","treatment"],
        "facility_conditions":["broken","equipment","room","dirty","hot","aircon","sira","mainit"],
    }.get(aspect_code,[])
    mentions=[]
    if terms:
        columns=[func.sum(case((func.lower(Feedback.comment).regexp_match(r"\b"+term+r"\b"),1),else_=0)) for term in terms]
        values=q.with_entities(*columns).one()
        mentions=sorted([dict(term=term,count=int(count)) for term,count in zip(terms,values) if count],key=lambda item:(-item["count"],item["term"]))[:3]
    examples=q.with_entities(Feedback.id,Feedback.comment,FeedbackLabel.sentiment).order_by(Feedback.created_at.desc(),Feedback.id.desc()).limit(3).all()
    return dict(service_area=area.name,aspect="All reported aspects" if aspect_code=="all" else aspect.name,aspect_code=aspect_code,window_days=days,
        count=total,**counts,mentioned_terms=mentions,
        examples=[dict(id=i,text=text,sentiment=sentiment) for i,text,sentiment in examples])
