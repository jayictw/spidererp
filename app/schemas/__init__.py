from app.schemas.common import ApiErrorResponse, ApiSuccessResponse, MessageResponse
from app.schemas.domain import (
    AuditLogCreate,
    AuditLogRead,
    ErrorBucketCreate,
    ErrorBucketRead,
    JobCreate,
    JobRead,
    JobRunCreate,
    JobRunRead,
    RuleCreate,
    RuleRead,
    RuleVersionCreate,
    RuleVersionRead,
    SampleCreate,
    SampleRead,
    SampleTraceAuditLogRead,
    SampleTraceDedupeRead,
    SampleTraceResponse,
    SystemConfigItem,
    TrainingQueueItemCreate,
    TrainingQueueItemRead,
)
from app.schemas.rules_actions import SampleMarkDuplicateAction
