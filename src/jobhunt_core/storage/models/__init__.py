"""SQLAlchemy models, one module per database.md table group.

Every model module is imported here explicitly so ``Base.metadata``
always sees every table before Alembic autogenerate or
``Base.metadata.create_all()`` runs -- same explicit-import-over-
filesystem-walk pattern used for the LLM provider registry
(final_review.md §1.3).
"""

from jobhunt_core.storage.models.application import ApplicationEventModel, ApplicationModel
from jobhunt_core.storage.models.ats import ATSReportModel
from jobhunt_core.storage.models.base import Base
from jobhunt_core.storage.models.document import ResumeVersionModel, TemplateModel
from jobhunt_core.storage.models.interview import InterviewModel, InterviewQuestionModel
from jobhunt_core.storage.models.job import CompanyModel, JobPostingModel, SearchRunModel
from jobhunt_core.storage.models.match import MatchScoreModel
from jobhunt_core.storage.models.profile import CandidateProfileModel

__all__ = [
    "ATSReportModel",
    "ApplicationEventModel",
    "ApplicationModel",
    "Base",
    "CandidateProfileModel",
    "CompanyModel",
    "InterviewModel",
    "InterviewQuestionModel",
    "JobPostingModel",
    "MatchScoreModel",
    "ResumeVersionModel",
    "SearchRunModel",
    "TemplateModel",
]
