from django.core.management.base import BaseCommand
import pandas as pd
from students.models import Student, Assignment, Performance

class Command(BaseCommand):
    help = 'Import data from an Excel file'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str)

    def handle(self, *args, **kwargs):
        file_path = kwargs['file_path']
        df = pd.read_excel(file_path)
        for _, row in df.iterrows():
            student, _ = Student.objects.get_or_create(name=row['Student Name'], email=row['Email'])
            assignment, _ = Assignment.objects.get_or_create(title=row['Assignment Title'])
            Performance.objects.create(student=student, assignment=assignment, grade=row['Grade'])
        self.stdout.write(self.style.SUCCESS('Successfully imported data'))
