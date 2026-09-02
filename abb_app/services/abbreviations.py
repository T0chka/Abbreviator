import re
from typing import Dict, List, NotRequired, Optional, TypedDict

from abb_app.models import AbbreviationEntry


GREEK_TO_LATIN = {
    'α': 'A', 'β': 'B', 'γ': 'G', 'δ': 'D',
    'ε': 'E', 'ζ': 'Z', 'η': 'H', 'θ': 'TH',
    'ι': 'I', 'κ': 'K', 'λ': 'L', 'μ': 'M',
    'ν': 'N', 'ξ': 'X', 'ο': 'O', 'π': 'P',
    'ρ': 'R', 'σ': 'S', 'τ': 'T', 'υ': 'U',
    'φ': 'PH', 'χ': 'CH', 'ψ': 'PS', 'ω': 'O',
}


class HighlightedCharacter(TypedDict):
    char: str
    mismatch: bool
    tooltip: NotRequired[str]


class Abbreviation(TypedDict):
    abbreviation: str
    descriptions: List[str]
    selected_description: NotRequired[Optional[str]]
    reviewed: NotRequired[bool]
    occurrence_count: NotRequired[int]
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


def normalize_description(description: str) -> str:
    """Return a case-insensitive key used only to compare descriptions."""
    return ' '.join(description.split()).casefold()


def _capitalize_by_abbreviation(text: str, abbr_letters: str) -> str:
    abbr_index = 0
    text_pos = 0
    text_chars = list(text)

    while abbr_index < len(abbr_letters) and text_pos < len(text_chars):
        current_char = text_chars[text_pos]
        if (
            current_char.lower() == abbr_letters[abbr_index].lower()
            and (text_pos == 0 or not text_chars[text_pos - 1].isalpha())
        ):
            text_chars[text_pos] = current_char.upper()
            abbr_index += 1
        text_pos += 1

    return ''.join(text_chars)


def format_description(abbreviation: str, description: str) -> str:
    """Return the canonical description stored in the dictionary."""
    formatted = ' '.join(description.split())

    if re.search(r'[A-Za-z]', abbreviation):
        parts = formatted.split('(', 1)
        english_part = parts[0].strip().lower()
        parenthetical_part = f"({parts[1]}" if len(parts) > 1 else ''

        latin_abbr = ''.join(
            GREEK_TO_LATIN.get(char, char) for char in abbreviation
        ).upper()
        abbr_letters = ''.join(re.findall(r'[A-Z]', latin_abbr))
        english_part = _capitalize_by_abbreviation(
            english_part,
            abbr_letters,
        )
        formatted = f'{english_part} {parenthetical_part}'.strip()

    return re.sub(
        r'^(\d*)([a-zA-ZА-Яа-яЁё])',
        lambda match: match.group(1) + match.group(2).upper(),
        formatted,
    )


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
        entry['reviewed'] = True
        return

    if action != 'add':
        raise ValueError('Invalid action')
    if not description:
        raise ValueError('Description is required')

    dictionary_abbreviation = entry.get('correct_form') or abbreviation
    formatted_description = format_description(
        dictionary_abbreviation,
        description,
    )
    normalized_description = normalize_description(formatted_description)

    entry['selected_description'] = formatted_description
    entry['reviewed'] = True

    if any(
        normalize_description(existing) == normalized_description
        for existing in entry['descriptions']
    ):
        return

    existing_descriptions = AbbreviationEntry.objects.filter(
        abbreviation=dictionary_abbreviation,
    ).values_list('description', flat=True)
    if any(
        normalize_description(existing) == normalized_description
        for existing in existing_descriptions
    ):
        return

    AbbreviationEntry.objects.create(
        abbreviation=dictionary_abbreviation,
        description=formatted_description,
        status='for_review',
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
