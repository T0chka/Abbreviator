import os
from django.core.management.base import BaseCommand
from abb_app.utils import split_by_language

class Command(BaseCommand):
    help = 'Test language splitting functionality with various formats'

    def handle(self, *args, **options):
        test_cases = [
            "Standard error of mean, стандартная ошибка среднего",
            "Body mass index (индекс массы тела)",
            "Magnetic resonance imaging/магнитно-резонансная томография",
            "Maximum tolerated dose / максимальная переносимая доза",
            "Blood pressure - артериальное давление",
            "Анатомо-терапевтическо-химическая классификаци",
            "Желудочно-кишечный тракт",
            "Электрокардиограмма, электрокардиографическое исследование",
            "Электрокардиограмма: электрокардиографическое исследование",
            "Something quoted «in quote» other text"
        ]

        self.stdout.write("\nTesting language splitting functionality:")
        self.stdout.write("-" * 80)

        for test in test_cases:
            russian, latin = split_by_language(test)
            self.stdout.write("\nInput:")
            self.stdout.write(f"  {test}")
            self.stdout.write("Output:")
            self.stdout.write(f"  Latin:   {latin}")
            self.stdout.write(f"  Russian: {russian}")
            self.stdout.write("-" * 80) 