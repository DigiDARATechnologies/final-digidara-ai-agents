def load_models():
    from .student import Student
    from .test import AptitudeTest
    from .question import AptitudeTestQuestion
    from .answer import AptitudeAnswer
    from .performance import TopicPerformance
    from .topic_history import LearnerLastTopics
    from .mixed_test_config import LearnerMixedTestConfig
    from .operations import RecentQuestionHash, AIRecommendation, BackgroundJob, AuditEvent, RateLimitEvent, AIUsageEvent, WorkerHeartbeat, BankGenerationLease, QuestionBankItem
    return (Student, AptitudeTest, AptitudeTestQuestion, AptitudeAnswer, TopicPerformance, LearnerLastTopics, LearnerMixedTestConfig, RecentQuestionHash, AIRecommendation, BackgroundJob, AuditEvent, RateLimitEvent, AIUsageEvent, WorkerHeartbeat, BankGenerationLease, QuestionBankItem)

from .student import Student
from .test import AptitudeTest
from .question import AptitudeTestQuestion
from .answer import AptitudeAnswer
from .performance import TopicPerformance
from .topic_history import LearnerLastTopics
from .mixed_test_config import LearnerMixedTestConfig
from .operations import RecentQuestionHash, AIRecommendation, BackgroundJob, AuditEvent, RateLimitEvent, AIUsageEvent, WorkerHeartbeat, BankGenerationLease, QuestionBankItem
