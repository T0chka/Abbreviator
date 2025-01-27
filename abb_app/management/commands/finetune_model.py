import os
import csv
import json
import re
import requests
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Finetune the Ollama model on abbreviation dictionary data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ollama-host',
            type=str,
            help='Ollama server host (e.g., http://localhost:11434)',
            default=os.environ.get('OLLAMA_HOST', 'http://192.168.1.165:11434')
        )
        parser.add_argument(
            '--train-file',
            type=str,
            help='Path to training data CSV file',
            default=os.path.join('abb_app', 'data', 'train_data.csv')
        )
        parser.add_argument(
            '--base-model',
            type=str,
            help='Base model to finetune',
            default= 'deepseek-r1:32b' #'llama3.2'
        )
        parser.add_argument(
            '--new-model-name',
            type=str,
            help='Name for the finetuned model',
            default='medical'
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

    def clean_context(self, text):
        """Clean context by replacing punctuation with spaces and normalizing whitespace"""
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def handle(self, *args, **options):
        ollama_host = options['ollama_host']
        if not self.check_ollama_server(ollama_host):
            return

        train_file = options['train_file']
        model_name = options['new_model_name']
        base_model = options['base_model']

        if not os.path.exists(train_file):
            self.stderr.write(f"Training data file not found at {train_file}")
            return

        training_data = []
        with open(train_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            for i, row in enumerate(reader):
                if len(row) == 3:
                    abb, desc, contexts = row[0], row[1], row[2]
                    # Clean contexts before adding to training data
                    cleaned_contexts = self.clean_context(contexts)
                    training_data.append({
                        'abbreviation': abb,
                        'response': f'{{"description": "{desc}"}}',
                        'contexts': cleaned_contexts
                    })
        
        self.stdout.write(f"Loaded {len(training_data)} training examples")
        
        modelfile = f'''FROM {base_model}
PARAMETER temperature 0.6
PARAMETER top_p 0.6
PARAMETER num_ctx 4096

SYSTEM """Ты - эксперт по медицинской терминологии. Твоя задача - расшифровывать аббревиатуры из медицинской документации.
Строгие правила расшифровки:
1. Расшифровка должна соответствовать контексту.
2. Слова в расшифровке должны совпадать с аббревиатурой по первой букве:
- Для 'FDA': F -> Food, D -> Drug, A -> Administration.
- Для 'ЧСС': Ч -> частота, С -> сердечных, С -> сокращений.
3. Расшифровка должна быть короткой, без лишних слов.

Пример правильного ответа:
 - Аббревиатура: 'ФЖЕЛ'
 - Правильная расшифровка: 'форсированная жизненная емкость легких'
Пример неправильного ответа:
 - 'функция жёлчного желёзного энзимно-лизосомального комплекса' (не соответствует контексту)
 
 Следуй этим правилам безукоснительно.
"""

MESSAGE user Следуя правилам, расшифруй аббревиатуру: 'ЧСС', использованную в контексте: 'при этом средняя ЧСС была 72 уд/мин'
MESSAGE assistant {{"description": "частота сердечных сокращений"}}

MESSAGE user Следуя правилам, расшифруй аббревиатуру: 'ИМТ', использованную в контексте: 'в то время как ИМТ пациента в норме'
MESSAGE assistant {{"description": "индекс массы тела"}}

MESSAGE user Следуя правилам, расшифруй аббревиатуру: 'BMI', использованную в контексте: 'while BMI is normal'
MESSAGE assistant {{"description": "body mass index"}}

MESSAGE user Следуя правилам, расшифруй аббревиатуру: 'ATP', использованную в контексте: 'influence metabolism by increasing ATP level'
MESSAGE assistant {{"description": "adenosine triphosphate"}}
'''
        # Add training examples
        examples_added = 0
        
        for row in training_data:
            modelfile += f'''
MESSAGE user Следуя правилам, расшифруй аббревиатуру: '{row['abbreviation']}', использованную в контексте: '{row['contexts']}'
MESSAGE assistant {row['response']}
'''
            examples_added += 1
        self.stdout.write(f"Added {examples_added} examples to Modelfile")

        modelfile_path = 'Modelfile'
        with open(modelfile_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(modelfile)

        file_size = os.path.getsize(modelfile_path) / 1024
        self.stdout.write(f"Modelfile size: {file_size:.2f} KB.")
        self.stdout.write("Sending request to create model...")

        try:
            response = requests.post(
                f'{ollama_host}/api/create',
                json={
                    'name': model_name,
                    'modelfile': modelfile,
                    'stream': False
                }
            )
            
            response.raise_for_status()
            
            self.stdout.write(self.style.SUCCESS(
                f'Successfully created model {model_name}'
            ))
            
        except requests.exceptions.RequestException as e:
            self.stderr.write(self.style.ERROR(f"\nFailed to create model: {e}"))
            if hasattr(e, 'response') and e.response is not None:
                self.stderr.write("Error Response:")
                self.stderr.write(e.response.text)
        finally:
            if os.path.exists(modelfile_path):
                os.remove(modelfile_path)
                self.stdout.write("Temporary Modelfile removed.") 