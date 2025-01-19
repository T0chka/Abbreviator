from django.core.management.base import BaseCommand
from abb_app.models import AbbreviationEntry
import csv
import os

class Command(BaseCommand):
    help = 'Import abbreviations from CSV file to database'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to CSV file')
        parser.add_argument(
            '--status',
            type=str,
            default='for_review',
            choices=['approved', 'for_review', 'rejected'],
            help='Set the status for imported entries (default: for_review)'
        )
        parser.add_argument(
            '--save-skipped',
            action='store_true',
            help='Save skipped records to a CSV file'
        )

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        status = options['status']
        save_skipped = options['save_skipped']

        if not os.path.exists(csv_file):
            self.stdout.write(self.style.ERROR(f'File {csv_file} does not exist'))
            return

        skipped_records = []
        imported = 0

        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # Skip header row
            
            for row in reader:
                if len(row) < 2:
                    skipped_records.append(row)
                    continue
                    
                abbreviation, description = row[0], row[1]
                
                # Check if this combination already exists
                if not AbbreviationEntry.objects.filter(
                    abbreviation=abbreviation,
                    description=description
                ).exists():
                    # Create new entry
                    AbbreviationEntry.objects.create(
                        abbreviation=abbreviation,
                        description=description,
                        status=status
                    )
                    imported += 1
                else:
                    skipped_records.append(row)

            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully imported {imported} entries '
                    f'(skipped {len(skipped_records)} duplicates)'
                )
            )

            # Save skipped records to a CSV file if requested
            if skipped_records and save_skipped:
                skipped_file = 'skipped_records.csv'
                with open(skipped_file, 'w', encoding='utf-8', newline='') as skipped_f:
                    writer = csv.writer(skipped_f)
                    writer.writerow(['abbreviation', 'description'])
                    writer.writerows(skipped_records)

                self.stdout.write(
                    self.style.WARNING(f'Skipped records saved to {skipped_file}')
                )