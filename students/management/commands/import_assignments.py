import pandas as pd
from django.core.management.base import BaseCommand
from students.models import Assignment

class Command(BaseCommand):
    help = 'Import assignments from an Excel file'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='The path to the Excel file')

    def handle(self, *args, **kwargs):
        file_path = kwargs['file_path']
        data = pd.read_excel(file_path)

        for _, row in data.iterrows():
            student_id=row['Student ID']
            title = row['title']  # Adjust the column name here
            status = row['status']  # Adjust the column name here
            #section = row['Assignment Section']  # Adjust the column name here

            # Create or update the assignment entry
            assignment, created = Assignment.objects.get_or_create(
                student_id=student_id,
                title=title,
                defaults={'status': status}
            )
            
            if not created:
                assignment.status = status
                assignment.save()

        self.stdout.write(self.style.SUCCESS('Successfully imported assignments'))
