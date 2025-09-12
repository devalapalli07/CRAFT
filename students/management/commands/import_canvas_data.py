import os
import csv
import pandas as pd
from datetime import datetime
from django.utils.timezone import make_aware, is_naive
from django.core.management.base import BaseCommand
from django.conf import settings
from students.models import Studentlist, Enrollment, Assignment, Submission

class Command(BaseCommand):
    help = "Wipes and imports students, enrollments, assignments, and submissions."

    def handle(self, *args, **kwargs):
        base_dir = settings.BASE_DIR
        data_dir = os.path.join(base_dir, "data_exports")

        # === File paths ===
        student_roster_file = os.path.join(data_dir, "StudentRoster.csv")
        enrollment_file = os.path.join(data_dir, "cleaned_enrollments_data.xlsx")
        assignments_file = os.path.join(data_dir, "assignments_cleaned_assignments.csv")
        submissions_file = os.path.join(data_dir, "assignments_cleaned_submissions.csv")

        # === Utility for datetime ===
        def make_safe_aware(value):
            if pd.isna(value):
                return None
            dt = pd.to_datetime(value, errors="coerce")
            if pd.isna(dt):
                return None
            return make_aware(dt) if is_naive(dt) else dt


        # === Clear existing data ===
        self.stdout.write("⚠️ Deleting existing records...")
        Submission.objects.all().delete()
        Assignment.objects.all().delete()
        Enrollment.objects.all().delete()
        Studentlist.objects.all().delete()
        self.stdout.write(self.style.WARNING("✅ All existing data cleared."))

        # === Import Students ===
        self.stdout.write("📥 Importing Student Roster...")
        with open(student_roster_file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            students = [
                Studentlist(
                    name=row["Student Name"],
                    student_id=row["Student ID"],
                    sis_id=row["Student SIS ID"],
                    email=row["Email"],
                    section_name=row["Section Name"]
                )
                for row in reader
            ]
        Studentlist.objects.bulk_create(students)
        self.stdout.write(self.style.SUCCESS(f"✅ Imported {len(students)} students."))

        # === Import Enrollments ===
        self.stdout.write("📥 Importing Enrollments...")
        enrollments_df = pd.read_excel(enrollment_file)
        enrollments = []
        for _, row in enrollments_df.iterrows():
            student = Studentlist.objects.filter(student_id=row['Student ID']).first()
            if not student:
                continue

            last_active = make_safe_aware(row.get("last_activity_at"))
            inactive_days = row.get("inactive_days")
            inactive_days = int(inactive_days) if pd.notna(inactive_days) else None

            enrollments.append(Enrollment(
                student=student,
                type=row.get("type"),
                role=row.get("role"),
                last_activity_at=last_active,
                total_activity_time=row.get("total_activity_time(in_hrs)") if pd.notna(row.get("total_activity_time(in_hrs)")) else None,
                sis_course_id=row.get("sis_course_id"),
                sis_section_id=row.get("sis_section_id"),
                sis_user_id=row.get("sis_user_id"),
                inactive_days=inactive_days,
                current_grade=row.get("current_grade") if pd.notna(row.get("current_grade")) else None,
                current_score=row.get("current_score") if pd.notna(row.get("current_score")) else None,
                final_grade=row.get("final_grade") if pd.notna(row.get("final_grade")) else None,
                final_score=row.get("final_score") if pd.notna(row.get("final_score")) else None,
                unposted_current_score=row.get("unposted_current_score") if pd.notna(row.get("unposted_current_score")) else None,
                unposted_current_grade=row.get("unposted_current_grade") if pd.notna(row.get("unposted_current_grade")) else None,
                unposted_final_score=row.get("unposted_final_score") if pd.notna(row.get("unposted_final_score")) else None,
                unposted_final_grade=row.get("unposted_final_grade") if pd.notna(row.get("unposted_final_grade")) else None,
            ))
        Enrollment.objects.bulk_create(enrollments)
        self.stdout.write(self.style.SUCCESS(f"✅ Imported {len(enrollments)} enrollments."))

        # === Import Assignments ===
        self.stdout.write("📥 Importing Assignments...")
        assignments = []
        with open(assignments_file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    assignment_id = int(row["id"])
                except (ValueError, TypeError):
                    self.stdout.write(self.style.ERROR(f"Invalid assignment ID in CSV: {row['id']}"))
                    continue

                due = pd.to_datetime(row.get("due_date"), errors='coerce')
                assignments.append(Assignment(
                    id=assignment_id,
                    title=row["title"],
                    due_date=make_safe_aware(due) if pd.notna(due) else None
                ))
        Assignment.objects.bulk_create(assignments)
        self.stdout.write(self.style.SUCCESS(f"✅ Imported {len(assignments)} assignments."))

        # === Import Submissions ===
        # self.stdout.write("📥 Importing Submissions...")
        # submissions = []
        # with open(submissions_file, newline='', encoding='utf-8') as f:
        #     reader = csv.DictReader(f)
        #     for row in reader:
        #         # Get and validate student
        #         student = Studentlist.objects.filter(student_id=row["student_id"]).first()
        #         if not student:
        #             self.stdout.write(self.style.WARNING(f"❌ Student not found: {row['student_id']}"))
        #             continue

        #         # Validate and get assignment by ID
        #         try:
        #             assignment_id = int(row["assignment_id"])
        #             assignment = Assignment.objects.filter(id=assignment_id).first()
        #         except (ValueError, TypeError):
        #             self.stdout.write(self.style.ERROR(f"❌ Invalid assignment ID: {row['assignment_id']}"))
        #             continue

        #         if not assignment:
        #             self.stdout.write(self.style.WARNING(f"❌ Assignment not found: {assignment_id}"))
        #             continue

        #         # Convert submission datetime
        #         submitted = make_safe_aware(row.get("submitted_at"))

        #         # Parse score safely
        #         # Parse score safely
        #         raw_score = row.get("score")

        #         try:
        #             # Some values might be strings like "NaN", so we coerce to float, or set None
        #             score = float(raw_score)
        #             if not pd.notna(score):  # catches float('nan'), etc.
        #                 score = None
        #         except (TypeError, ValueError):
        #             self.stdout.write(self.style.WARNING(
        #                 f"⚠️ Invalid score '{raw_score}' for student {row.get('student_id')} assignment {row.get('assignment_id')}. Setting to NULL."
        #             ))
        #             score = None



        #         # Append submission
        #         submissions.append(Submission(
        #             student=student,
        #             assignment=assignment,
        #             submitted_at=submitted,
        #             score=score,
        #             status=row.get("status") or "floating"
        #         ))

        # Submission.objects.bulk_create(submissions)
        # self.stdout.write(self.style.SUCCESS(f"✅ Imported {len(submissions)} submissions."))

        # self.stdout.write(self.style.SUCCESS("🎉 All Canvas data successfully imported."))
        
        
        # === Import Submissions ===
        self.stdout.write("📥 Importing Submissions...")
        
        # Preload lookups to avoid N+1 queries
        students_map = {s.student_id: s for s in Studentlist.objects.all()}
        assignments_map = {a.id: a for a in Assignment.objects.all()}
        
        submissions = []
        batch_size = 2000
        count = 0
        
        with open(submissions_file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Resolve student quickly
                student = students_map.get(row["student_id"])
                if not student:
                    self.stdout.write(self.style.WARNING(f"❌ Student not found: {row['student_id']}"))
                    continue
        
                # Resolve assignment quickly
                try:
                    assignment_id = int(row["assignment_id"])
                except (ValueError, TypeError):
                    self.stdout.write(self.style.ERROR(f"❌ Invalid assignment ID: {row['assignment_id']}"))
                    continue
        
                assignment = assignments_map.get(assignment_id)
                if not assignment:
                    self.stdout.write(self.style.WARNING(f"❌ Assignment not found: {assignment_id}"))
                    continue
        
                # Convert submission datetime
                submitted = make_safe_aware(row.get("submitted_at"))
        
                # Parse score safely
                raw_score = row.get("score")
                try:
                    score = float(raw_score)
                    if not pd.notna(score):  # catches NaN
                        score = None
                except (TypeError, ValueError):
                    self.stdout.write(self.style.WARNING(
                        f"⚠️ Invalid score '{raw_score}' for student {row.get('student_id')} assignment {row.get('assignment_id')}. Setting to NULL."
                    ))
                    score = None
        
                submissions.append(Submission(
                    student=student,
                    assignment=assignment,
                    submitted_at=submitted,
                    score=score,
                    status=row.get("status") or "floating"
                ))
        
                # Bulk insert in batches
                if len(submissions) >= batch_size:
                    Submission.objects.bulk_create(submissions, batch_size)
                    count += len(submissions)
                    self.stdout.write(f"✅ Inserted {count} submissions so far...")
                    submissions = []
        
        # Insert leftovers
        if submissions:
            Submission.objects.bulk_create(submissions, batch_size)
            count += len(submissions)
        
        self.stdout.write(self.style.SUCCESS(f"✅ Imported {count} submissions."))
        self.stdout.write(self.style.SUCCESS("🎉 All Canvas data successfully imported."))
