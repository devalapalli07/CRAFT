from django.core.management.base import BaseCommand
import pandas as pd
from students.models import Enrollment,Studentlist
from django.utils.dateparse import parse_datetime
import datetime

class Command(BaseCommand):
    help = 'Imports enrollment data from an Excel file'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='The path to the Excel file to import')

    def handle(self, *args, **options):
        file_path = options['file_path']
        self.stdout.write(self.style.SUCCESS(f'Starting to import data from {file_path}'))
        df = pd.read_excel(file_path,na_values=['', ' '],parse_dates=['last_activity_at'])
        df['last_activity_at'] = df['last_activity_at'].dt.tz_localize('EST')
        filtered_df = df[df['type'] == 'StudentEnrollment']
        for _, row in filtered_df.iterrows():
            student_id = row['Student ID']
            student, created = Studentlist.objects.get_or_create(student_id=student_id)  # Ensure the student exists

            Enrollment.objects.create(
        student=student,  # Assign the Studentlist instance
        type=row['type'],
        role=row['role'],
        last_activity_at=parse_datetime(row['last_activity_at'].isoformat() if isinstance(row['last_activity_at'], datetime.datetime) else row['last_activity_at']),
        total_activity_time=row.get('total_activity_time(in_hrs)', None),
        sis_course_id=row.get('sis_course_id', None),
        sis_section_id=row.get('sis_section_id', None),
        sis_user_id=row['sis_user_id'],
        inactive_days=row.get('inactive_days', None),
        current_grade=row.get('current_grade', None),
        current_score=row.get('current_score', None),
        final_grade=row.get('final_grade', None),
        final_score=row.get('final_score', None),
        unposted_current_score=row.get('unposted_current_score', None),
        unposted_current_grade=row.get('unposted_current_grade', None),
        unposted_final_score=row.get('unposted_final_score', None),
        unposted_final_grade=row.get('unposted_final_grade', None),
    )