import os
import csv
import re
import json
import time
from django.core.management.base import BaseCommand, CommandError
from abb_app.model_integration.client import ModelClient
from abb_app.model_integration.chat_client import ChatModelClient

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
        parser.add_argument(
            '--chat-mode',
            action='store_true',
            help='Use chat-based interaction mode'
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
        chat_mode = options['chat_mode']
        if not os.path.exists(test_file):
            self.stderr.write(f"Test file not found: {test_file}")
            return

        # Initialize appropriate client
        client_class = ChatModelClient if chat_mode else ModelClient
        client = client_class(
            host=options['ollama_host'],
            model=model_name,
            temperature=temperature,
            top_p=top_p
        )

        # Print test configuration
        self.stdout.write(self.style.SUCCESS(
            f"\nTest Configuration:\n"
            f"Model: {model_name}\n"
            f"Mode: {'chat' if chat_mode else 'standard'}\n"
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

        rules = (
            "Важные правила:\n"
            "1. Расшифровка должна быть максимально короткой и соответствовать контексту.\n"
            "2. Слова в расшифровке должны совпадать по начальному символу:\n"
            "- Для 'FDA': F -> Food, D -> Drug, A -> Administration.\n"
            "- Для 'ЧСС': Ч -> частота, С -> сердечных, С -> сокращений.\n"
            "3. Если аббревиатура написана латиницей (FDA, BMI), ответ должен быть на английском языке.\n"
            "4. Если аббревиатура написана кириллицей (АБС, МИА), ответ должен быть на русском языке.\n"
        )

        # Read test data
        with open(test_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            
            for row in reader:
                if len(row) != 4:  # abb, desc, contexts, source
                    continue
                    
                abb, expected_desc, contexts, source = row
                stats['total'] += 1
                
                self.stdout.write(f"\nTesting abbreviation {stats['total']}: {abb} [{source.upper()}]")
                self.stdout.write(f"Expected: {expected_desc}")
                
                if re.search(r'[A-Za-z]', abb):
                    language_hint = "The abbreviation is English. The description must be in English."
                else:
                    language_hint = "Аббревиатура русская, расшифровка должна быть на русском языке."

                try:
                    if chat_mode:
                        prompt = (
                            f"Аббревиатура '{abb}', использована в контексте: '{contexts}'."
                            f"\n{language_hint}"
                        )
                        predicted_desc = client.generate_response(prompt, rules)
                    else:
                        prompt = (
                            f"Следуя правилам, расшифруй аббревиатуру '{abb}',"
                            f"использованную в контексте: '{contexts}'."
                            f"\n{language_hint}"
                        )
                        # prompt = (
                        #     "Вспомни " + rules +
                        #     "Следуя этим правилам, расшифруй аббревиатуру: " +
                        #     f"'{abb}', использованную в контексте: '{contexts}'."
                        #     f"\n{language_hint}"
                        # )
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

                    # if stats['total'] % 10 == 0:
                    #     timeout = 10
                    #     self.stdout.write(f"\n=== Cooling down for {timeout} seconds ===")
                    #     time.sleep(timeout)
                    
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