import io
import logging

from dataclasses import dataclass
from typing import Dict, List

from docx import Document

from abb_app.utils import (
    Abbreviation,
    AbbreviationFormatter,
    AbbreviationTableExtractor,
    AbbreviationTableGenerator,
    process_abbreviations,
)

from .abbreviations import load_approved_dictionary


logger = logging.getLogger('abb_app')
extractor = AbbreviationTableExtractor()
formatter = AbbreviationFormatter()
generator = AbbreviationTableGenerator()


@dataclass(frozen=True)
class ProcessedDocument:
    abbreviations: List[Abbreviation]
    initial_abbreviations: List[Abbreviation]


def process_document(file_path: str) -> ProcessedDocument:
    logger.debug('Processing file: %s', file_path)

    dictionary = load_approved_dictionary()
    logger.debug(
        'Loaded abbreviation dictionary: %s',
        len(dictionary),
    )

    document = Document(file_path)
    initial_abbreviations = extractor.get_abbreviation_table(document)
    abbreviations = process_abbreviations(document, dictionary)

    return ProcessedDocument(
        abbreviations=abbreviations,
        initial_abbreviations=initial_abbreviations,
    )


def build_abbreviation_table_docx(
    abbreviations: List[Dict[str, str]],
) -> bytes:
    cleaned = formatter.clean_and_sort_abbreviations(abbreviations)
    document = generator.generate_document(cleaned)

    stream = io.BytesIO()
    document.save(stream)
    return stream.getvalue()
