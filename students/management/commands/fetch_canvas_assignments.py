import os
import csv
import json
import logging
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import ast
from django.core.management.base import BaseCommand
from django.conf import settings
from logging.handlers import RotatingFileHandler
import openpyxl
import csv
from datetime import datetime

class Command(BaseCommand):
    help = 'Fetches Canvas assignment data for students and saves raw + cleaned output'

    def handle(self, *args, **kwargs):
        # === CONFIGURATION ===
        base_dir = settings.BASE_DIR
        log_dir = os.path.join(base_dir, "log")
        output_dir = os.path.join(base_dir, "data_exports")
        os.makedirs(log_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        log_file = os.path.join(log_dir, 'assignments_api.log')
        raw_json_file = os.path.join(output_dir, 'assignments_raw.json')
        excel_file = os.path.join(output_dir, 'assignments_cleaned.xlsx')

        # Canvas API
        token = "13~WE6aXzRMrPTheVDUVn6cfQtV2VP7EtvDvfPJkt9fDEH9h9MY8JAJQQtB7a786mWu"
        base_url = "https://usflearn.instructure.com/api/v1/courses/1930464/analytics/users/{}/assignments?per_page=100"

        roster_path = os.path.join(base_dir, "data_exports", "StudentRoster.csv")

        # === LOGGING SETUP ===
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
        file_handler = RotatingFileHandler(log_file, maxBytes=100000, backupCount=3)
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logging.getLogger().addHandler(file_handler)

        def fetch_assignment_data(student_id):
            headers = {"Authorization": f"Bearer {token}"}
            url = base_url.format(student_id)
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                return student_id, response.json()
            except requests.exceptions.RequestException as e:
                logging.error(f"Failed to fetch data for student {student_id}: {e}")
                return student_id, None

        def fetch_student_ids_from_roster(roster_path):
            student_ids = []
            try:
                with open(roster_path, newline='', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)
                    for row in reader:
                        student_id = row.get('Student ID')
                        if student_id:
                            student_ids.append(student_id.strip())
            except Exception as e:
                logging.error(f"Error reading roster: {e}")
            return student_ids

        def fetch_all_data_concurrently(student_ids):
            results = {}
            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_id = {executor.submit(fetch_assignment_data, sid): sid for sid in student_ids}
                for future in as_completed(future_to_id):
                    sid = future_to_id[future]
                    student_id, data = future.result()
                    results[student_id] = data
            return results

        def clean_assignment_data(json_data):
            rows = []
            for student_id, assignments in json_data.items():
                if not assignments:
                    continue
                for item in assignments:
                    submission = item.get("submission", {})
                    rows.append({
                        "Student ID": student_id,
                        "assignment_id": item.get("assignment_id"),
                        "title": item.get("title"),
                        "points_possible": item.get("points_possible"),
                        "due_at": item.get("due_at"),
                        "status": item.get("status"),
                        "score": submission.get("score"),
                        "submitted_at": submission.get("submitted_at"),
                    })
            return pd.DataFrame(rows)


        import ast  # safer than eval

        def extract_transform_load(file_path):
            df = pd.read_excel(file_path)

            assignments_csv = file_path.replace(".xlsx", "_assignments.csv")
            submissions_csv = file_path.replace(".xlsx", "_submissions.csv")

            assignments_seen = set()

            with open(assignments_csv, mode='w', newline='', encoding='utf-8') as assignments_file, \
                open(submissions_csv, mode='w', newline='', encoding='utf-8') as submissions_file:

                assignments_writer = csv.writer(assignments_file)
                submissions_writer = csv.writer(submissions_file)

                assignments_writer.writerow(['id', 'title', 'due_date'])
                submissions_writer.writerow(['student_id', 'assignment_id', 'submitted_at', 'score', 'status'])

                for _, row in df.iterrows():
                    student_id = row.get('Student ID')
                    assignment_id = row.get('assignment_id')
                    title = row.get('title')
                    due_at = row.get('due_at')
                    status = row.get('status')

                    # Write assignment only once
                    if assignment_id not in assignments_seen:
                        assignments_writer.writerow([assignment_id, title, due_at])
                        assignments_seen.add(assignment_id)

                    

                    submitted_at = row.get('submitted_at')
                    score = row.get('score')

                    submissions_writer.writerow([student_id, assignment_id, submitted_at, score, status])

            print(f"ETL complete. Files saved as:\n📄 {assignments_csv}\n📄 {submissions_csv}")

                # === MAIN EXECUTION ===
        logging.info("Reading student IDs from StudentRoster.csv...")
        student_ids = fetch_student_ids_from_roster(roster_path)
        if not student_ids:
            self.stdout.write(self.style.ERROR("No student IDs found in StudentRoster.csv."))
            return

        logging.info(f"Fetching assignments for {len(student_ids)} students...")
        all_data = fetch_all_data_concurrently(student_ids)

        with open(raw_json_file, 'w') as f:
            json.dump(all_data, f, indent=2)
        logging.info(f"Raw assignment data saved to {raw_json_file}")

        df = clean_assignment_data(all_data)
        df.to_excel(excel_file, index=False)
        logging.info(f"Cleaned assignment data saved to {excel_file}")

        # Run ETL on the cleaned Excel file
        extract_transform_load(excel_file)

        self.stdout.write(self.style.SUCCESS(f"✅ Raw JSON saved to: {raw_json_file}"))
        self.stdout.write(self.style.SUCCESS(f"✅ Cleaned Excel saved to: {excel_file}"))

