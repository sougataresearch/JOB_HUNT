"""Shared Pydantic schemas — the common vocabulary between agents.

Zero internal dependencies on other jobhunt_core subpackages
(architecture.md §2).
"""

from jobhunt_core.schemas.application import (
    Application,
    ApplicationEvent,
    ApplicationEventSource,
    ApplicationStatus,
)
from jobhunt_core.schemas.ats import ATSReport
from jobhunt_core.schemas.interview import (
    Interview,
    InterviewQuestion,
    InterviewType,
    QuestionCategory,
)
from jobhunt_core.schemas.job import Company, JobPosting, RemoteType
from jobhunt_core.schemas.match import MatchScore
from jobhunt_core.schemas.profile import CandidateProfile, EducationEntry, ExperienceEntry

__all__ = [
    "ATSReport",
    "Application",
    "ApplicationEvent",
    "ApplicationEventSource",
    "ApplicationStatus",
    "CandidateProfile",
    "Company",
    "EducationEntry",
    "ExperienceEntry",
    "Interview",
    "InterviewQuestion",
    "InterviewType",
    "JobPosting",
    "MatchScore",
    "QuestionCategory",
    "RemoteType",
]
