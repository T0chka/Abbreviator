from typing import Dict, List, NotRequired, Optional, TypedDict

from abb_app.models import AbbreviationEntry


class HighlightedCharacter(TypedDict):
    char: str
    mismatch: bool
    tooltip: NotRequired[str]


class Abbreviation(TypedDict):
    abbreviation: str
    descriptions: List[str]
    selected_description: NotRequired[Optional[str]]
    contexts: NotRequired[Optional[List[str]]]
    correct_form: NotRequired[Optional[str]]
    highlighted: NotRequired[Optional[List[HighlightedCharacter]]]


class TableEntry(TypedDict):
    abbreviation: str
    description: str
    highlighted: Optional[List[HighlightedCharacter]]


class ComparisonResult(TypedDict):
    missing_abbs: List[Abbreviation]
    new_found: List[TableEntry]


def load_approved_dictionary() -> List[Abbreviation]:
    entries = AbbreviationEntry.objects.filter(
        status='approved'
    ).values('abbreviation', 'description')

    grouped: Dict[str, List[str]] = {}
    for entry in entries:
        grouped.setdefault(entry['abbreviation'], []).append(
            entry['description']
        )

    return [
        {
            'abbreviation': abbreviation,
            'descriptions': descriptions,
        }
        for abbreviation, descriptions in grouped.items()
    ]


def update_abbreviation_selection(
    doc_abbs: List[Abbreviation],
    abbreviation: str,
    description: Optional[str],
    action: str,
) -> None:
    entry = next(
        (
            item for item in doc_abbs
            if item['abbreviation'] == abbreviation
        ),
        None,
    )
    if entry is None:
        raise ValueError('Abbreviation not found')

    if action == 'skip':
        entry['selected_description'] = None
        return

    if action != 'add':
        raise ValueError('Invalid action')
    if not description:
        raise ValueError('Description is required')

    entry['selected_description'] = description
    if description in entry['descriptions']:
        return

    AbbreviationEntry.objects.get_or_create(
        abbreviation=entry.get('correct_form') or abbreviation,
        description=description,
        defaults={'status': 'for_review'},
    )


def compare_abbreviations(
    old_abbs: List[Abbreviation],
    new_abbs: List[TableEntry],
) -> ComparisonResult:
    """Compare exact abbreviation names in the original and current tables."""
    old_names = {entry['abbreviation'] for entry in old_abbs}
    new_names = {entry['abbreviation'] for entry in new_abbs}

    return {
        'missing_abbs': [
            entry for entry in old_abbs
            if entry['abbreviation'] not in new_names
        ],
        'new_found': [
            entry for entry in new_abbs
            if entry['abbreviation'] not in old_names
        ],
    }
