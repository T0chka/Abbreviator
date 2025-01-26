import os
import csv
import random
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Split data into training and test sets'

    def add_arguments(self, parser):
        parser.add_argument(
            '--input-file',
            type=str,
            default=os.path.join('abb_app', 'data', 'abb_dict_cleaned.csv'),
            help='Input CSV file with abbreviations and contexts'
        )
        parser.add_argument(
            '--seed',
            type=int,
            default=0,
            help='Random seed for reproducibility'
        )
        parser.add_argument(
            '--test-size',
            type=float,
            default=0.02,
            help='Proportion of data to use for testing (0.0-1.0)'
        )
        parser.add_argument(
            '--overlap-size',
            type=int,
            default=5,
            help='Number of training examples to include in test set'
        )
        parser.add_argument(
            '--train-file',
            type=str,
            default=os.path.join('abb_app', 'data', 'train_data.csv'),
            help='Output file for training data'
        )
        parser.add_argument(
            '--test-file',
            type=str,
            default=os.path.join('abb_app', 'data', 'test_data.csv'),
            help='Output file for test data'
        )
        
    def handle(self, *args, **options):
        input_file = options['input_file']
        train_file = options['train_file']
        test_file = options['test_file']
        test_size = options['test_size']
        overlap_size = options['overlap_size']
        random.seed(options['seed'])

        if not os.path.exists(input_file):
            self.stderr.write(f"Input file not found: {input_file}")
            return

        # Read all data
        all_data = []
        with open(input_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            header = next(reader)
            for row in reader:
                if len(row) == 3:
                    all_data.append({
                        'abbreviation': row[0],
                        'description': row[1],
                        'contexts': row[2]
                    })

        total_examples = len(all_data)
        if total_examples == 0:
            self.stderr.write("No valid data found in input file")
            return

        # Shuffle and split data
        random.shuffle(all_data)
        test_count = int(total_examples * test_size)
        
        # Select test data
        test_data = [
            {**item, 'source': 'new'} 
            for item in all_data[:test_count]
        ]
        train_data = all_data[test_count:]

        # Select overlap examples from training data
        if overlap_size > 0 and len(train_data) >= overlap_size:
            overlap_examples = random.sample(train_data, overlap_size)
            test_data.extend([
                {**item, 'source': 'train'} 
                for item in overlap_examples
            ])

        # Save train data
        os.makedirs(os.path.dirname(train_file), exist_ok=True)
        with open(train_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(header)
            for item in train_data:
                writer.writerow([
                    item['abbreviation'],
                    item['description'],
                    item['contexts']
                ])

        # Save test data with source labels
        os.makedirs(os.path.dirname(test_file), exist_ok=True)
        with open(test_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(header + ['source'])  # Add source column
            for item in test_data:
                writer.writerow([
                    item['abbreviation'],
                    item['description'],
                    item['contexts'],
                    item['source']
                ])

        # Count examples by source
        train_examples = sum(1 for item in test_data if item['source'] == 'train')
        new_examples = sum(1 for item in test_data if item['source'] == 'new')

        self.stdout.write(self.style.SUCCESS(
            f"\nData split complete:\n"
            f"- Training examples: {len(train_data)}\n"
            f"- Test examples: {len(test_data)}\n"
            f"  - New examples: {new_examples}\n"
            f"  - From training: {train_examples}\n"
            f"Files saved:\n"
            f"- Training data: {train_file}\n"
            f"- Test data: {test_file}"
        )) 