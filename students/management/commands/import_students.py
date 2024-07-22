import csv
from django.core.management.base import BaseCommand
from django.db.utils import IntegrityError
from students.models import Studentlist

class Command(BaseCommand):
    help = 'Import students from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_filename', type=str)

    def handle(self, *args, **options):
        with open(options['csv_filename'], newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            next(reader)  # Skip the header row if your CSV has one
            for row in reader:
                try:
                    student, created = Studentlist.objects.get_or_create(
                        name=row[0],
                        student_id=row[1],
                        sis_id=row[2],
                        email=row[3],
                        section_name=row[4]
                    )
                    if created:
                        self.stdout.write(self.style.SUCCESS(f'Successfully added student: {student.name}'))
                    else:
                        self.stdout.write(self.style.WARNING(f'Student already exists: {student.name}'))
                except IntegrityError as e:
                    self.stdout.write(self.style.ERROR(f'Error importing student: {e}'))
                except IndexError as e:
                    self.stdout.write(self.style.ERROR(f'Malformed row: {row} - Error: {e}'))
