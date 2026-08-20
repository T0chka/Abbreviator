from typing import Dict, List, Optional

from abb_app.models import AbbreviationEntry
from abb_app.utils import Abbreviation


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


def get_selected_abbreviations(
    doc_abbs: List[Abbreviation],
) -> List[Dict[str, str]]:
    return [
        {
            'abbreviation': abb['abbreviation'],
            'description': abb['selected_description'],
        }
        for abb in doc_abbs
        if abb.get('selected_description') is not None
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
        defaults={
            'status': 'for_review',
            'highlighted': entry.get('highlighted'),
        },
    )
