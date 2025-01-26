import os
from collections import defaultdict
from docx import Document
import csv
from django.core.management.base import BaseCommand
from abb_app.utils import (
    AbbreviationTableExtractor,
    TextProcessor
)
import time

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
            default=1,
            help='Maximum number of contexts to extract for each abbreviation'
        )
        parser.add_argument(
            '--context-window',
            type=int,
            default=50,
            help='Context window size for each abbreviation'
        )

    def handle(self, *args, **options):
        input_dir = options['input_dir']
        output_file = options['output_file']
        max_contexts = options['max_contexts']
        context_window = options['context_window']

        if not os.path.exists(input_dir):
            self.stderr.write(f"Input directory not found: {input_dir}")
            return

        unique_pairs = defaultdict(set)
        table_extractor = AbbreviationTableExtractor()
        text_processor = TextProcessor()

        for filename in os.listdir(input_dir):
            if not filename.endswith('.docx'):
                continue

            filepath = os.path.join(input_dir, filename)
            self.stdout.write(f"\nProcessing {filename}...")

            try:
                doc = Document(filepath)

                start_time = time.time()
                abb_table = table_extractor.get_abbreviation_table(doc)
                elapsed_time = time.time() - start_time
                self.stdout.write(f"Abbreviation table extraction time: {elapsed_time:.2f} seconds")

                start_time = time.time()
                text = text_processor.extract_relevant_text(doc)
                elapsed_time = time.time() - start_time
                self.stdout.write(f"Relevant text extraction time: {elapsed_time:.2f} seconds")

                start_time = time.time()
                for abb in abb_table:
                    contexts = text_processor.find_abbreviation_context(
                        text, abb['abbreviation'],
                        window=context_window,
                        max_contexts=max_contexts
                    )
                    if contexts:
                        for desc in abb['descriptions']:
                            key = (abb['abbreviation'], desc.strip().lower())
                            unique_pairs[key].update(contexts)
                elapsed_time = time.time() - start_time
                self.stdout.write(f"Contexts collection time: {elapsed_time:.2f} seconds")

            except Exception as e:
                self.stderr.write(f"Error processing {filename}: {e}")

        start_time = time.time()
        self.stdout.write(f"\nSaving results to {output_file}...")
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(['abbreviation', 'description', 'contexts'])
            
            for (abb, desc), contexts_set in sorted(unique_pairs.items()):
                contexts_str = ' '.join(contexts_set)
                writer.writerow([abb, desc, contexts_str])
        elapsed_time = time.time() - start_time
        self.stdout.write(f"File writing time: {elapsed_time:.2f} seconds")

        total_pairs = len(unique_pairs)
        total_contexts = sum(len(ctx_set) for ctx_set in unique_pairs.values())
        
        self.stdout.write(self.style.SUCCESS(
            f"\nExtracted {total_pairs} abbreviations "
            f"with {total_contexts} total contexts"
        ))
        self.stdout.write(
            f"Results saved to {output_file}"
        )