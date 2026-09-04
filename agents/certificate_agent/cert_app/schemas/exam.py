from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class StartExamRequest(BaseModel):
    topic: str


class AnswerItem(BaseModel):
    question_id: int
    answer: str


class AnswerSubmit(BaseModel):
    exam_id: int
    answers: List[AnswerItem]


class ExamResult(BaseModel):
    exam_id: int
    topic: str
    total_questions: int
    correct_answers: int
    score_percentage: float
    status: str
    passed: bool
    certificate_id: Optional[int] = None
    certificate_number: Optional[str] = None


class CertificateIntentRequest(BaseModel):
    message: str
    context: Optional[str] = None


class CertificateRecipientUpdate(BaseModel):
    recipient_name: str


class CertificateEmailRequest(BaseModel):
    email: str


class CertificateEmailVerificationConfirm(BaseModel):
    email: str
    code: str
