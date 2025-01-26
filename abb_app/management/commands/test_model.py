import os
import csv
import re
import json
from django.core.management.base import BaseCommand, CommandError
from abb_app.model_integration.client import ModelClient

class Command(BaseCommand):
    help = 'Test model performance on test data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-file',
            type=str,
            default=os.path.join('abb_app', 'data', 'test_data.csv'),
            help='Input CSV file with test data'
        )
        parser.add_argument(
            '--ollama-host',
            type=str,
            default=os.environ.get('OLLAMA_HOST', 'http://192.168.1.165:11434'),
            help='Ollama server host'
        )
        parser.add_argument(
            '--model-name',
            type=str,
            default='medical',
            help='Model name to test'
        )
        parser.add_argument(
            '--temperature',
            type=float,
            default=0.6,
            help='Model temperature (0.0-1.0)'
        )
        parser.add_argument(
            '--top-p',
            type=float,
            default=0.6,
            help='Model top_p sampling (0.0-1.0)'
        )
        parser.add_argument(
            '--json-output',
            type=str,
            default='',
            help='Path to JSON file for saving test results'
        )

    def normalize_text(self, text):
        """Normalize text for comparison by removing punctuation and extra spaces"""
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'ё', 'е', text)
        return text.strip()

    def handle(self, *args, **options):
        test_file = options['test_file']
        model_name = options['model_name']
        temperature = options['temperature']
        top_p = options['top_p']
        json_output = options['json_output']
        if not os.path.exists(test_file):
            self.stderr.write(f"Test file not found: {test_file}")
            return

        # Initialize model client
        client = ModelClient(
            host=options['ollama_host'],
            model=model_name,
            temperature=temperature,
            top_p=top_p
        )

        # Print test configuration
        self.stdout.write(self.style.SUCCESS(
            f"\nTest Configuration:\n"
            f"Model: {model_name}\n"
            f"Temperature: {temperature}\n"
            f"Top-p: {top_p}\n"
            f"Test file: {test_file}\n"
        ))

        results = []
        stats = {
            'total': 0,
            'correct': 0,
            'total_new': 0,
            'correct_new': 0,
            'total_train': 0,
            'correct_train': 0
        }

        # Read test data
        with open(test_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            
            for row in reader:
                if len(row) != 4:  # abb, desc, contexts, source
                    continue
                    
                abb, expected_desc, contexts, source = row
                stats['total'] += 1
                
                self.stdout.write(f"\nTesting abbreviation: {abb} [{source.upper()}]")
                self.stdout.write(f"Expected: {expected_desc}")
                
                try:
                    prompt = (
                        "Вспомни важные правила:\n"
                        "1. Расшифровка должна быть максимально короткой и общепринята в медицинской документации.\n"
                        "2. Слова в расшифровке должны соответствовать буквам аббревиатуры "
                        "(например, для аббревиатуры 'АБС' расшифровка должна содержать три слова, "
                        "первое из которых начинается с буквы 'А', второе с буквы 'Б', третье с буквы 'С').\n"
                        "3. Язык расшифровки должен соответствовать языку аббревиатуры.\n"
                        "4. Если не уверен, что расшифровка правильная, то отвечай 'не знаю'.\n"
                        "Следуя этим правилам, расшифруй аббревиатуру: "
                        f"'{abb}', использованную в контексте: '{contexts}'."
                    )
                    predicted_desc = client.generate_response(prompt)
                    
                    # Compare predictions (normalized)
                    expected_norm = self.normalize_text(expected_desc)
                    predicted_norm = self.normalize_text(predicted_desc)
                    is_correct = predicted_norm == expected_norm
                    
                    # Update statistics
                    if source == 'train':
                        stats['total_train'] += 1
                        if is_correct:
                            stats['correct_train'] += 1
                    else:
                        stats['total_new'] += 1
                        if is_correct:
                            stats['correct_new'] += 1
                    
                    if is_correct:
                        stats['correct'] += 1
                        
                    result = {
                        'abbreviation': abb,
                        'expected': expected_desc,
                        'predicted': predicted_desc,
                        'expected_norm': expected_norm,
                        'predicted_norm': predicted_norm,
                        'correct': is_correct,
                        'context': contexts,
                        'source': source
                    }
                    results.append(result)
                    
                    # Print result
                    status = "✓" if is_correct else "✗"
                    result_msg = f"Predicted: {predicted_desc} {status}"
                    self.stdout.write(
                        self.style.SUCCESS(result_msg) if is_correct 
                        else self.style.ERROR(result_msg)
                    )
                    
                except Exception as e:
                    self.stderr.write(f"Error processing {abb}: {str(e)}")

        # Calculate accuracies
        train_acc = (
            stats['correct_train'] / stats['total_train'] * 100 
            if stats['total_train'] else 0
        )
        new_acc = (
            stats['correct_new'] / stats['total_new'] * 100 
            if stats['total_new'] else 0
        )
        total_acc = (
            stats['correct'] / stats['total'] * 100 
            if stats['total'] else 0
        )

        # Prepare results
        test_results = {
            'accuracy': total_acc,
            'train_accuracy': train_acc,
            'new_accuracy': new_acc
        }

        # Print summary with model info
        self.stdout.write(self.style.SUCCESS(
            f"\nTest Results for {model_name} (temp={temperature}, top_p={top_p}):\n"
            f"Training examples:\n"
            f"  Total: {stats['total_train']}\n"
            f"  Correct: {stats['correct_train']}\n"
            f"  Accuracy: {train_acc:.2f}%\n"
            f"\nNew examples:\n"
            f"  Total: {stats['total_new']}\n"
            f"  Correct: {stats['correct_new']}\n"
            f"  Accuracy: {new_acc:.2f}%\n"
            f"\nOverall:\n"
            f"  Total examples: {stats['total']}\n"
            f"  Correct predictions: {stats['correct']}\n"
            f"  Accuracy: {total_acc:.2f}%\n"
        ))

        if json_output:
            try:
                with open(json_output, 'w', encoding='utf-8') as jf:
                    json.dump(test_results, jf, ensure_ascii=False, indent=2)
            except Exception as e:
                raise CommandError(f"Failed to write JSON output: {e}")