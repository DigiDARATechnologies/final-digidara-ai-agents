from collections import defaultdict
from ..extensions import db
from ..models import TopicPerformance
from .test_generation import CATEGORIES


def analytics_payload(tests):
    tests=[test for test in tests if test.status=="completed"]
    stats=defaultdict(lambda:{"attempts":0,"correct":0,"time":0})
    for test in tests:
        for question in test.questions:
            if question.answer:
                row=stats[question.category];row["attempts"]+=1;row["correct"]+=int(question.answer.is_correct);row["time"]+=question.answer.time_taken_seconds
    categories=[]
    for category in CATEGORIES:
        value=stats[category]
        attempts=value["attempts"]
        categories.append({"category":category,"attempts":attempts,"accuracy":round(value["correct"]/attempts*100,1) if attempts else 0,"average_time":round(value["time"]/attempts,1) if attempts else 0})
    ordered=sorted(categories,key=lambda row:row["accuracy"],reverse=True)
    attempted=[row for row in ordered if row["attempts"]]
    return {"score_trend":[{"label":f"Test {i+1}","score":float(test.percentage)} for i,test in enumerate(tests)],"categories":categories,"strongest_area":attempted[0]["category"] if attempted else "Complete a test","focus_area":attempted[-1]["category"] if attempted else "Complete a test"}


def recalculate_topic_performance(student_id):
    from ..models import AptitudeAnswer, AptitudeTest, AptitudeTestQuestion
    rows=db.session.query(AptitudeTestQuestion.category,AptitudeTestQuestion.topic,db.func.count(AptitudeAnswer.id),db.func.sum(AptitudeAnswer.is_correct),db.func.avg(AptitudeAnswer.time_taken_seconds)).join(AptitudeAnswer,AptitudeAnswer.question_id==AptitudeTestQuestion.id).join(AptitudeTest,AptitudeTest.id==AptitudeAnswer.test_id).filter(AptitudeAnswer.student_id==student_id,AptitudeTest.status=="completed").group_by(AptitudeTestQuestion.category,AptitudeTestQuestion.topic).all()
    TopicPerformance.query.filter_by(student_id=student_id).delete(synchronize_session=False)
    for category,topic,attempts,correct,average_time in rows:
        performance=TopicPerformance(student_id=student_id,category=category,topic=topic)
        performance.attempts=attempts;performance.correct_count=int(correct or 0);performance.accuracy=round(performance.correct_count/attempts*100,2);performance.average_time_seconds=round(float(average_time or 0),2)
        db.session.add(performance)
