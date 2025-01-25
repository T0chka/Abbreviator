import os
import csv
import regex
from django.core.management.base import BaseCommand
from abb_app.utils import detect_string_alphabet, split_by_language

class Command(BaseCommand):
    help = 'Clean abbreviations data by removing mixed-language entries and matching descriptions to abbreviation language'

    def add_arguments(self, parser):
        parser.add_argument(
            '--input-file',
            type=str,
            default=os.path.join('abb_app', 'data', 'abb_dict_with_contexts.csv'),
            help='Input CSV file with abbreviations and contexts'
        )
        parser.add_argument(
            '--output-file',
            type=str,
            default=os.path.join('abb_app', 'data', 'abb_dict_cleaned.csv'),
            help='Output CSV file for cleaned data'
        )

    def handle(self, *args, **options):
        input_file = options['input_file']
        output_file = options['output_file']

        if not os.path.exists(input_file):
            self.stderr.write(f"Input file not found: {input_file}")
            return

        cleaned_data = []
        total_entries = 0
        skipped_mixed = 0
        skipped_one_letter = 0
        skipped_few_capitals = 0
        cleaned_descriptions = 0
        unchanged_descriptions = 0
        
        with open(input_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            header = next(reader)
            
            for row in reader:
                total_entries += 1
                if len(row) != 3:
                    raise ValueError(
                        f"\nInvalid row format: {row}. Expected 3 columns."
                    )
                
                abb, desc, contexts = row

                # Skip one-letter abbreviations
                if len(abb) == 1:
                    skipped_one_letter += 1
                    continue

                # Skip abbreviations without at least two capital letters
                if not regex.search(r'\p{Lu}.*\p{Lu}', abb, regex.UNICODE):
                    skipped_few_capitals += 1
                    continue
                
                # Check abbreviation language
                abb_lang = detect_string_alphabet(abb)
                
                # Skip mixed-language abbreviations
                if abb_lang == 'mixed':
                    skipped_mixed += 1
                    continue
                
                # Split description by language
                russian_desc, latin_desc = split_by_language(desc)
                
                # Decide which cleaned description to use
                if abb_lang == 'russian' and russian_desc:
                    if russian_desc != desc:
                        cleaned_descriptions += 1
                        self.stdout.write(
                            f"Initial: {desc} -> Cleaned (Russian): {russian_desc}"
                        )
                    else:
                        unchanged_descriptions += 1 
                    cleaned_desc = russian_desc                        
                elif abb_lang == 'latin' and latin_desc:
                    if latin_desc != desc:
                        cleaned_descriptions += 1
                        self.stdout.write(
                            f"Initial: {desc} -> Cleaned (Latin): {latin_desc}"
                        )
                    else:
                        unchanged_descriptions += 1
                    cleaned_desc = latin_desc
                else:
                    cleaned_desc = desc
                    unchanged_descriptions += 1
                
                cleaned_data.append([abb, cleaned_desc, contexts])

        # Save cleaned data
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(header)
            writer.writerows(cleaned_data)

        self.stdout.write(self.style.SUCCESS(
            f"\nCleaning complete:\n"
            f"- Total entries in input file: {total_entries}\n"
            f"- Mixed-language abbreviations removed: {skipped_mixed}\n"
            f"- One-letter abbreviations removed: {skipped_one_letter}\n"
            f"- Abbreviations without at least two capital letters removed: {skipped_few_capitals}\n"
            f"- Descriptions cleaned: {cleaned_descriptions}\n"
            f"- Descriptions unchanged: {unchanged_descriptions}\n"
            f"Results saved to: {output_file}"
        )) 