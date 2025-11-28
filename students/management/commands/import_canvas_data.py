import os
import csv
import pandas as pd
from datetime import datetime
from django.utils.timezone import make_aware, is_naive
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction
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

        # === Preflight: ensure files exist ===
        for required_path in [student_roster_file, enrollment_file, assignments_file, submissions_file]:
            if not os.path.exists(required_path):
                raise CommandError(f"Required file missing: {required_path}")

        # === Load inputs first (fail fast before wiping DB) ===
        with open(student_roster_file, newline='', encoding='utf-8') as f:
            roster_reader = csv.DictReader(f)
            roster_rows = list(roster_reader)
        if not roster_rows:
            raise CommandError("StudentRoster.csv is empty or unreadable.")
        required_student_cols = {"Student Name", "Student ID", "Student SIS ID", "Email", "Section Name"}
        if not required_student_cols.issubset(set(roster_rows[0].keys())):
            raise CommandError(f"StudentRoster.csv missing required columns: {required_student_cols}")

        enrollments_df = pd.read_excel(enrollment_file)
        # Normalize column names to resilient snake_case for attribute access
        enrollments_df = enrollments_df.rename(
            columns=lambda c: str(c)
            .strip()
            .lower()
            .replace(" ", "_")
            .replace("(", "")
            .replace(")", "")
            .replace("/", "_")
        )
        if "student_id" not in enrollments_df.columns:
            raise CommandError("Enrollment file missing required 'Student ID' column.")

        with open(assignments_file, newline='', encoding='utf-8') as f:
            assignments_reader = list(csv.DictReader(f))
        if not assignments_reader:
            raise CommandError("Assignments CSV is empty or unreadable.")

        with open(submissions_file, newline='', encoding='utf-8') as f:
            submissions_reader = list(csv.DictReader(f))

        # === Clear + import inside a transaction ===
        with transaction.atomic():
            self.stdout.write("⚠️ Deleting existing records...")
            Submission.objects.all().delete()
            Assignment.objects.all().delete()
            Enrollment.objects.all().delete()
            Studentlist.objects.all().delete()
            self.stdout.write(self.style.WARNING("✅ All existing data cleared."))

            # === Import Students ===
            self.stdout.write("📥 Importing Student Roster...")
            students = [
                Studentlist(
                    name=row["Student Name"],
                    student_id=row["Student ID"],
                    sis_id=row["Student SIS ID"],
                    email=row["Email"],
                    section_name=row["Section Name"]
                )
                for row in roster_rows
            ]
            Studentlist.objects.bulk_create(students)
            self.stdout.write(self.style.SUCCESS(f"✅ Imported {len(students)} students."))

            # === Import Enrollments ===
            self.stdout.write("📥 Importing Enrollments...")
            enrollments = []
            batch_size = int(os.getenv("IMPORT_BATCH_SIZE", "2000"))
            count = 0

            students_map = {s.student_id: s for s in Studentlist.objects.all()}

            def _safe_val(val):
                return val if pd.notna(val) else None

            for row in enrollments_df.itertuples(index=False, name="EnrollRow"):
                raw_id = getattr(row, "student_id", None)
                student_id = str(raw_id).strip() if raw_id is not None else ""
                student = students_map.get(student_id)
                if not student:
                    continue

                last_active = make_safe_aware(getattr(row, "last_activity_at", None))
                inactive_days_val = getattr(row, "inactive_days", None)
                inactive_days = int(inactive_days_val) if pd.notna(inactive_days_val) else None

                enrollments.append(Enrollment(
                    student=student,
                    type=_safe_val(getattr(row, "type", None)),
                    role=_safe_val(getattr(row, "role", None)),
                    last_activity_at=last_active,
                    total_activity_time=_safe_val(getattr(row, "total_activity_time_in_hrs", None)),
                    sis_course_id=_safe_val(getattr(row, "sis_course_id", None)),
                    sis_section_id=_safe_val(getattr(row, "sis_section_id", None)),
                    sis_user_id=_safe_val(getattr(row, "sis_user_id", None)),
                    inactive_days=inactive_days,
                    current_grade=_safe_val(getattr(row, "current_grade", None)),
                    current_score=_safe_val(getattr(row, "current_score", None)),
                    final_grade=_safe_val(getattr(row, "final_grade", None)),
                    final_score=_safe_val(getattr(row, "final_score", None)),
                    unposted_current_score=_safe_val(getattr(row, "unposted_current_score", None)),
                    unposted_current_grade=_safe_val(getattr(row, "unposted_current_grade", None)),
                    unposted_final_score=_safe_val(getattr(row, "unposted_final_score", None)),
                    unposted_final_grade=_safe_val(getattr(row, "unposted_final_grade", None)),
                ))

                if len(enrollments) >= batch_size:
                    Enrollment.objects.bulk_create(enrollments, batch_size=batch_size)
                    count += len(enrollments)
                    self.stdout.write(f"✅ Inserted {count} enrollments so far...")
                    enrollments = []

            if enrollments:
                Enrollment.objects.bulk_create(enrollments, batch_size=batch_size)
                count += len(enrollments)

            self.stdout.write(self.style.SUCCESS(f"✅ Imported {count} enrollments."))

            # === Import Assignments ===
            self.stdout.write("📥 Importing Assignments...")
            assignments = []
            for row in assignments_reader:
                try:
                    assignment_id = int(row["id"])
                except (ValueError, TypeError):
                    self.stdout.write(self.style.ERROR(f"Invalid assignment ID in CSV: {row.get('id')}"))
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
            self.stdout.write("📥 Importing Submissions...")
            
            # Preload lookups to avoid N+1 queries
            students_map = {s.student_id: s for s in Studentlist.objects.all()}
            assignments_map = {a.id: a for a in Assignment.objects.all()}
            
            submissions = []
            batch_size = int(os.getenv("IMPORT_BATCH_SIZE", "2000"))
            count = 0
            
            for row in submissions_reader:
                # Resolve student quickly
                student = students_map.get(row.get("student_id"))
                if not student:
                    self.stdout.write(self.style.WARNING(f"❌ Student not found: {row.get('student_id')}"))
                    continue
        
                # Resolve assignment quickly
                try:
                    assignment_id = int(row.get("assignment_id"))
                except (ValueError, TypeError):
                    self.stdout.write(self.style.ERROR(f"❌ Invalid assignment ID: {row.get('assignment_id')}"))
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
