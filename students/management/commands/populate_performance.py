from django.core.management.base import BaseCommand
from students.models import Studentlist, Assignment, Performance

class Command(BaseCommand):
    help = 'Populate Performance table with sample data'

    def handle(self, *args, **kwargs):
        students = Studentlist.objects.all()
        assignments = Assignment.objects.all()

        for student in students:
            for assignment in assignments:
                performance, created = Performance.objects.get_or_create(
                    student=student,
                    assignment=assignment,
                    defaults={'grade': 0.0}  # You can set a default grade or any other field value
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f'Performance created for student {student.name} and assignment {assignment.title}'))
                else:
                    self.stdout.write(self.style.WARNING(f'Performance already exists for student {student.name} and assignment {assignment.title}'))

