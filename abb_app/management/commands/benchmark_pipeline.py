import os
import csv
import time
import json
from datetime import datetime
from django.core.management import call_command
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Benchmark different models and parameters using existing train/test data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--train-file',
            type=str,
            default=os.path.join('abb_app', 'data', 'train_data.csv'),
            help='Input CSV file with training data'
        )
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
            '--models',
            nargs='+',
            default=['llama3.1', 'llama3.2', 'deepseek-r1:7b', 'deepseek-r1:8b'], #, 'deepseek-r1:32b' , 'llama3.1:70b'
            help='List of base models to test'
        )
        parser.add_argument(
            '--temperatures',
            nargs='+',
            type=float,
            default=[0.1, 0,5, 1],
            help='List of temperature values to test'
        )
        parser.add_argument(
            '--top-p-values',
            nargs='+',
            type=float,
            default=[0.1, 0,5, 1],
            help='List of top-p values to test'
        )
        parser.add_argument(
            '--train-sizes',
            nargs='+',
            type=int,
            default=[50, 250, 500],
            help='List of training set sizes to test'
        )
        parser.add_argument(
            '--output-dir',
            type=str,
            default=os.path.join('abb_app', 'benchmarks'),
            help='Directory to store benchmark results'
        )
        parser.add_argument(
            '--model-timeout',
            type=int,
            default=30,
            help='Timeout in seconds between testing different models'
        )

    def _create_subset_file(self, input_file, output_file, num_examples):
        """Create a subset of the training data"""
        with open(input_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            header = next(reader)
            data = list(reader)[:num_examples]

        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(data)

    def _save_results_csv(self, results, output_dir):
        """Save results as CSV file"""
        csv_path = os.path.join(output_dir, f'benchmark_results.csv')
        
        # Define CSV headers
        headers = [
            'timestamp', 'model', 'train_size', 'temperature', 'top_p',
            'time_seconds', 'accuracy', 'train_accuracy', 'new_accuracy'
        ]
        
        # Write results
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        with open(csv_path, 'a', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            if not os.path.exists(csv_path):
                writer.writeheader()
            for r in results:
                writer.writerow(r)
        
        return csv_path

    def handle(self, *args, **options):
        start_time = time.time()
        
        # Create output directory
        os.makedirs(options['output_dir'], exist_ok=True)
        
        for model in options['models']:
            benchmark_results = []
            for train_size in options['train_sizes']:
                # Create training subset
                subset_file = os.path.join('abb_app', 'data', f'train_subset_{train_size}.csv')
                self._create_subset_file(options['train_file'], subset_file, train_size)
                
                for temp in options['temperatures']:
                    for top_p in options['top_p_values']:
                        self.stdout.write(self.style.SUCCESS(
                            f"\n========= Testing Configuration =========\n\n"
                            f"Model: {model}\n"
                            f"Training examples: {train_size}\n"
                            f"Temperature: {temp}\n"
                            f"Top-p: {top_p}"
                        ))

                        experiment_start = time.time()
                        try:
                            # Fine-tune model
                            self.stdout.write(f"\n=== Fine-tuning Model ===\n")
                            call_command(
                                'finetune_model',
                                ollama_host=options['ollama_host'],
                                train_file=subset_file,
                                base_model=model,
                                new_model_name='medical'
                            )

                            # Test model and capture output
                            self.stdout.write(f"\n=== Testing Model ===")
                            json_temp_file = os.path.join(
                                options['output_dir'],
                                'test_model_output.json'
                            )
                            call_command(
                                'test_model',
                                ollama_host=options['ollama_host'],
                                test_file=options['test_file'],
                                model_name='medical',
                                temperature=temp,
                                top_p=top_p,
                                json_output=json_temp_file
                            )
                            with open(json_temp_file, 'r', encoding='utf-8') as jf:
                                test_output = json.load(jf)

                            # Calculate time taken
                            time_taken = time.time() - experiment_start
                            
                            # Record results
                            result = {
                                'timestamp': datetime.now().isoformat(),
                                'model': model,
                                'train_size': train_size,
                                'temperature': temp,
                                'top_p': top_p,
                                'time_seconds': round(time_taken, 1),
                                'accuracy': test_output['accuracy'],
                                'train_accuracy': test_output['train_accuracy'],
                                'new_accuracy': test_output['new_accuracy']
                            }
                        except Exception as e:
                            self.stderr.write(
                                f"Error in experiment with {model}, size={train_size}: {str(e)}"
                            )
                        
                        benchmark_results.append(result)
                
                # Clean up subset file
                if os.path.exists(subset_file):
                    os.remove(subset_file)
                    os.remove(json_temp_file)

            # Save intermediate results
            csv_file = self._save_results_csv(benchmark_results, options['output_dir'])

        # Calculate total runtime
        total_time = time.time() - start_time
        
        # Print summary
        self.stdout.write(self.style.SUCCESS(
            f"\n=== Benchmark Complete ===\n"
            f"Total runtime: {total_time / 60:.1f} minutes\n"
            f"Results saved to: {csv_file}"
        ))

        # Print results
        self.stdout.write("\nResults:")
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            self.stdout.write(f.read())