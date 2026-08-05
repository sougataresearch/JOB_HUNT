"""CV file parsers (PDF, DOCX, Markdown) — api.md §1 CV Parser API.

Importing this package registers every parser instance -- the same
explicit-import discovery pattern used for LLM providers and
SQLAlchemy models (final_review.md §1.3), so ``parser_for_file()``
always has every parser available once this package has been imported.
"""

from jobhunt_core.documents.parsers.base import (
    CVParser,
    parser_for_file,
    register_parser,
)
from jobhunt_core.documents.parsers.docx import DOCXParser
from jobhunt_core.documents.parsers.markdown import MarkdownParser
from jobhunt_core.documents.parsers.pdf import PDFParser

register_parser(PDFParser())
register_parser(DOCXParser())
register_parser(MarkdownParser())

__all__ = [
    "CVParser",
    "DOCXParser",
    "MarkdownParser",
    "PDFParser",
    "parser_for_file",
    "register_parser",
]
