import os
import csv
import json
import requests
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Finetune the Ollama model on abbreviation dictionary data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dict-path',
            type=str,
            help='Path to abbreviation dictionary CSV file',
            default=os.path.join('abb_app', 'data', 'abb_dict.csv')
        )
        parser.add_argument(
            '--model-name',
            type=str,
            help='Name for the finetuned model',
            default='llama3.2-medical'
        )
        parser.add_argument(
            '--base-model',
            type=str,
            help='Base model to finetune',
            default='llama3.2'
        )
        parser.add_argument(
            '--ollama-host',
            type=str,
            help='Ollama server host (e.g., http://localhost:11434)',
            default=os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
        )

    def check_ollama_server(self, host):
        """Check if Ollama server is running and accessible"""
        try:
            print(f"Checking Ollama server at {host}")
            response = requests.post(
                f'{host}/api/create',
                json={
                    'name': 'test',
                    'modelfile': 'FROM llama3.2',
                    'stream': False
                },
                timeout=5
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            self.stderr.write(self.style.ERROR(
                f"\nOllama server is not accessible at {host}\n"
                f"Error: {str(e)}"
            ))
            return False

    def handle(self, *args, **options):
        ollama_host = options['ollama_host']
        if not self.check_ollama_server(ollama_host):
            return

        dict_path = options['dict_path']
        model_name = options['model_name']
        base_model = options['base_model']

        self.stdout.write("\n=== Loading Dictionary ===")
        if not os.path.exists(dict_path):
            self.stderr.write(f"Dictionary file not found at {dict_path}")
            return

        training_data = []
        with open(dict_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            for i, row in enumerate(reader):
                if len(row) == 2:
                    abb, desc = row[0], row[1]
                    training_data.append({
                        'abbreviation': abb,
                        'response': f'{{"description": "{desc}"}}'
                    })
                if i < 3:
                    self.stdout.write(f"Sample data {i}: {abb} -> {desc}")
        
        self.stdout.write(f"Loaded {len(training_data)} abbreviations from dictionary")
        self.stdout.write("\n=== Creating Base Modelfile ===")

        modelfile = f'''FROM {base_model}
PARAMETER temperature 0.1
PARAMETER top_p 0.3
PARAMETER num_ctx 4096

SYSTEM """Ты - эксперт по медицинской терминологии. Твоя задача - расшифровывать медицинские аббревиатуры.
Важные правила:
1. Не добавляй никакой другой текст кроме JSON
2. Расшифровка может быть написана прямов контексте, если так - используй ее
3. Расшифровка должна соответствовать каждой букве аббревиатуры
4. Если аббревиатура на русском - давай русскую расшифровку, если на английском - английскую
5. Расшифровка должна быть максимально короткой и общепринятой в медицинской документации
"""

MESSAGE user Аббревиатура: 'ЭКГ' Контекст: Пациенту была проведена ЭКГ для оценки работы сердца
MESSAGE assistant {{"description": "электрокардиография"}}

MESSAGE user Аббревиатура: 'ЧСС' Контекст: ЧСС в норме, 72 удара в минуту
MESSAGE assistant {{"description": "частота сердечных сокращений"}}
'''
        # Add dictionary examples
        examples_added = 0
        
        for row in training_data:
            modelfile += f'''

MESSAGE user Аббревиатура: '{row['abbreviation']}' Контекст: Документация для клинических исследований
MESSAGE assistant {row["response"]}'''
            examples_added += 1
        self.stdout.write(f"Added {examples_added} dictionary examples")

        self.stdout.write("\n=== Saving and Validating Modelfile ===")
        # modelfile_path = 'Modelfile'
        # with open(modelfile_path, 'w', encoding='utf-8', newline='\n') as f:
        #     f.write(modelfile)
            
        # with open(modelfile_path, 'r', encoding='utf-8') as f:
        #     self.stdout.write("\nFirst 15 lines of Modelfile:")
        #     for i, line in enumerate(f):
        #         if i < 15:
        #             self.stdout.write(f"Line {i+1}: {line.rstrip()}")
            
        #     f.seek(0, os.SEEK_END)
        #     file_size = f.tell() / 1024  # Size in KB
        #     self.stdout.write(f"\nModelfile size: {file_size:.2f} KB")

        self.stdout.write("\n=== Creating Model via API ===")

        try:
            self.stdout.write("Sending request to Ollama API...")
            response = requests.post(
                f'{ollama_host}/api/create',
                json={
                    'name': model_name,
                    'modelfile': modelfile,
                    'stream': False
                }
            )
            
            self.stdout.write(f"API Response Status: {response.status_code}")
            
            try:
                response_json = response.json()
                self.stdout.write("API Response Body:")
                self.stdout.write(json.dumps(response_json, indent=2))
            except json.JSONDecodeError:
                self.stdout.write("Raw API Response:")
                self.stdout.write(response.text)
            
            response.raise_for_status()
            
            self.stdout.write(self.style.SUCCESS(
                f'Successfully created model {model_name}'
            ))
            
        except requests.exceptions.RequestException as e:
            self.stderr.write(self.style.ERROR(f"\nFailed to create model: {e}"))
            if hasattr(e, 'response') and e.response is not None:
                self.stderr.write("Error Response:")
                self.stderr.write(e.response.text)
        # finally:
        #     if os.path.exists(modelfile_path):
        #         print(f"Modelfile: {modelfile_path}")
        #         os.remove(modelfile_path)
        #         self.stdout.write("Cleaned up Modelfile") 