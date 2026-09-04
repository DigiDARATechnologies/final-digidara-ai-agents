from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from flask import current_app, g
from ..extensions import db
from .test_label import test_label
from ..models import AIUsageEvent, AptitudeTest, AptitudeTestQuestion
from ..models.base import utc_isoformat


def estimated_cost(input_tokens, output_tokens):
    input_rate = Decimal(str(current_app.config.get("OPENAI_INPUT_COST_PER_MILLION", 0.15)))
    output_rate = Decimal(str(current_app.config.get("OPENAI_OUTPUT_COST_PER_MILLION", 0.60)))
    return (Decimal(input_tokens) * input_rate + Decimal(output_tokens) * output_rate) / Decimal(1_000_000)


def record_usage(student_id, operation, model, usage, test_id=None, question_id=None):
    input_tokens = int(usage.get("input_tokens", 0) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)
    if input_tokens + output_tokens == 0:
        return None
    event = AIUsageEvent(
        student_id=student_id, test_id=test_id, question_id=question_id,
        operation=operation, model=usage.get("model") or model, input_tokens=input_tokens,
        output_tokens=output_tokens, total_tokens=input_tokens + output_tokens,
        estimated_cost_usd=estimated_cost(input_tokens, output_tokens),
    )
    db.session.add(event)
    # Real per-call usage for the orchestrator's token billing -- read back
    # in app/__init__.py's after_request hook and returned as a response
    # header, so the gateway can charge the caller for actual LLM cost
    # instead of a flat guess.
    g.tokens_used_this_request = g.get("tokens_used_this_request", 0) + input_tokens + output_tokens
    return event


def allocate_usage(usage, count):
    if not count:
        return []
    result=[]
    for index in range(count):
        input_tokens=usage.get("input_tokens",0)//count + int(index < usage.get("input_tokens",0)%count)
        output_tokens=usage.get("output_tokens",0)//count + int(index < usage.get("output_tokens",0)%count)
        result.append({"input_tokens":input_tokens,"output_tokens":output_tokens,"total_tokens":input_tokens+output_tokens})
    return result


def _empty_totals():
    return {"input_tokens":0,"output_tokens":0,"total_tokens":0,"cost_usd":Decimal("0")}


def _add(target, event):
    target["input_tokens"] += event.input_tokens
    target["output_tokens"] += event.output_tokens
    target["total_tokens"] += event.total_tokens
    target["cost_usd"] += Decimal(event.estimated_cost_usd)


def _public(totals):
    return {**totals,"cost_usd":float(round(totals["cost_usd"],8))}


def usage_payload(student_id):
    local_zone=timezone(timedelta(minutes=current_app.config["APP_TIMEZONE_OFFSET_MINUTES"]))
    now_local=datetime.now(local_zone)
    today_start_local=now_local.replace(hour=0,minute=0,second=0,microsecond=0)
    today_start=today_start_local.astimezone(timezone.utc)
    trend_start_local=today_start_local-timedelta(days=6)
    trend_start=trend_start_local.astimezone(timezone.utc)
    events=AIUsageEvent.query.filter_by(student_id=student_id).order_by(AIUsageEvent.created_at.desc()).all()
    tests=AptitudeTest.query.filter_by(student_id=student_id).order_by(AptitudeTest.started_at.desc()).all()
    test_map={test.id:test for test in tests}
    latest_test=tests[0] if tests else None
    today=_empty_totals(); session=_empty_totals(); per_test=defaultdict(_empty_totals); daily=defaultdict(_empty_totals)
    for event in events:
        created=event.created_at
        if created.tzinfo is None: created=created.replace(tzinfo=timezone.utc)
        if created>=today_start:_add(today,event)
        if latest_test and event.test_id==latest_test.id:_add(session,event)
        if event.test_id:_add(per_test[event.test_id],event)
        if created>=trend_start:_add(daily[created.astimezone(local_zone).date().isoformat()],event)
    per_tests=[]
    for test in tests[:10]:
        totals=per_test[test.id]
        if totals["total_tokens"]:
            per_tests.append({"test_id":test.id,"name":test_label(test),"date":utc_isoformat(test.started_at),**_public(totals)})
    question_rows=[]
    if latest_test:
        questions=AptitudeTestQuestion.query.filter_by(test_id=latest_test.id).order_by(AptitudeTestQuestion.sequence_no).all()
        by_question=defaultdict(_empty_totals);by_question_operation=defaultdict(lambda:defaultdict(_empty_totals))
        for event in events:
            if event.test_id==latest_test.id and event.question_id:
                _add(by_question[event.question_id],event);_add(by_question_operation[event.question_id][event.operation],event)
        for question in questions:
            totals=by_question[question.id]
            if totals["total_tokens"]:
                operations=[{"operation":operation,**_public(operation_totals)} for operation,operation_totals in sorted(by_question_operation[question.id].items())]
                question_rows.append({"question_number":question.sequence_no,"topic":question.topic,"category":question.category,"operations":operations,**_public(totals)})
    trend=[]
    for offset in range(7):
        day=(trend_start_local+timedelta(days=offset)).date()
        trend.append({"date":day.isoformat(),**_public(daily[day.isoformat()])})
    return {
        "summary":{"today":_public(today),"session":_public(session),"recent_test":_public(session)},
        "session_test_id":latest_test.id if latest_test else None,
        "per_tests":per_tests,"per_questions":question_rows,"daily_trend":trend,
        "pricing":{"model":current_app.config["OPENAI_MODEL"],"currency":"USD","input_per_million":current_app.config["OPENAI_INPUT_COST_PER_MILLION"],"output_per_million":current_app.config["OPENAI_OUTPUT_COST_PER_MILLION"]},
    }
