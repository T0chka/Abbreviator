import os
from collections import defaultdict
from docx import Document
import csv
from django.core.management.base import BaseCommand
from abb_app.utils import (
    AbbreviationTableExtractor,
    TextProcessor
)

class Command(BaseCommand):
    help = 'Extract abbreviations with contexts from Word files'

    def add_arguments(self, parser):
        parser.add_argument(
            '--input-dir',
            type=str,
            default=os.path.join('abb_app', 'data', 'word_files'),
            help='Directory containing Word files'
        )
        parser.add_argument(
            '--output-file',
            type=str,
            default=os.path.join('abb_app', 'data', 'abb_dict_with_contexts.csv'),
            help='Output CSV file path'
        )
        parser.add_argument(
            '--max-contexts',
            type=int,
            default=10,
            help='Maximum number of contexts to extract for each abbreviation'
        )

    def handle(self, *args, **options):
        input_dir = options['input_dir']
        output_file = options['output_file']
        max_contexts = options['max_contexts']


        if not os.path.exists(input_dir):
            self.stderr.write(f"Input directory not found: {input_dir}")
            return

        abb_contexts = defaultdict(list)
        table_extractor = AbbreviationTableExtractor()
        text_processor = TextProcessor()

        for filename in os.listdir(input_dir):
            if not filename.endswith('.docx'):
                continue

            filepath = os.path.join(input_dir, filename)
            self.stdout.write(f"\nProcessing {filename}...")

            try:
                doc = Document(filepath)
                abbreviations = table_extractor.get_abbreviation_table(doc)
                text = text_processor.extract_relevant_text(doc)

                for abb in abbreviations:
                    contexts = text_processor.find_abbreviation_context(
                        text, abb['abbreviation'], window=100, find_all=True, max_contexts=max_contexts 
                    )
                    
                    if contexts:
                        for desc in abb['descriptions']:
                            key = (abb['abbreviation'], desc)
                            abb_contexts[key].extend(contexts)

            except Exception as e:
                self.stderr.write(f"Error processing {filename}: {e}")

        self.stdout.write(f"\nSaving results to {output_file}...")
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(['abbreviation', 'description', 'contexts'])
            
            for (abb, desc), contexts in abb_contexts.items():
               # print(f"\nAbbreviation: {abb}, Description: {desc}, Contexts: {contexts}")
                contexts_str = ' '.join(contexts)
                writer.writerow([abb, desc, contexts_str])

        total_abbs = len(abb_contexts)
        total_contexts = sum(len(contexts) for contexts in abb_contexts.values())
        
        self.stdout.write(self.style.SUCCESS(
            f"\nExtracted {total_abbs} abbreviations "
            f"with {total_contexts} total contexts"
        ))
        self.stdout.write(
            f"Results saved to {output_file}"
        ) 