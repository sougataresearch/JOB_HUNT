"""Repository classes — the only storage-access surface agents are allowed to use."""

from jobhunt_core.storage.repositories.application_repo import ApplicationRepo
from jobhunt_core.storage.repositories.ats_repo import ATSRepo
from jobhunt_core.storage.repositories.document_repo import DocumentRepo
from jobhunt_core.storage.repositories.interview_repo import InterviewRepo
from jobhunt_core.storage.repositories.job_repo import JobRepo
from jobhunt_core.storage.repositories.match_repo import MatchRepo
from jobhunt_core.storage.repositories.profile_repo import ProfileRepo

__all__ = [
    "ATSRepo",
    "ApplicationRepo",
    "DocumentRepo",
    "InterviewRepo",
    "JobRepo",
    "MatchRepo",
    "ProfileRepo",
]
