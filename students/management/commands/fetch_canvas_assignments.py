
import os
import csv
import json
import logging
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import ast
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from logging.handlers import RotatingFileHandler
import openpyxl
from datetime import datetime
import glob
import re
import zlib
import time
from collections import defaultdict

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

        # Tunables (env-configurable)
        REQUEST_TIMEOUT = float(os.getenv("CANVAS_TIMEOUT", "30"))
        RETRY_LIMIT = int(os.getenv("CANVAS_RETRIES", "3"))
        BACKOFF_SECONDS = float(os.getenv("CANVAS_BACKOFF", "0.5"))
        MAX_WORKERS = int(os.getenv("CANVAS_WORKERS", "10"))
        LOG_LEVEL = os.getenv("CANVAS_LOG_LEVEL", "INFO").upper()

        token = os.getenv("CANVAS_API_TOKEN") or getattr(settings, "CANVAS_API_TOKEN", "")
        if not token:
            raise CommandError("CANVAS_API_TOKEN not configured")

        def _get_course_ids():
            raw = os.getenv("CANVAS_COURSE_IDS") or getattr(settings, "CANVAS_COURSE_IDS", "")
            if isinstance(raw, (list, tuple)):
                ids = [str(c).strip() for c in raw if str(c).strip()]
            else:
                ids = [cid.strip() for cid in str(raw).split(",") if cid.strip()]
            if not ids:
                raise CommandError("CANVAS_COURSE_IDS not configured or empty")
            return ids

        course_ids = _get_course_ids()
        base_url_template = "https://usflearn.instructure.com/api/v1/courses/{}/analytics/users/{}/assignments?per_page=100"

        # === LOGGING SETUP ===
        logger = logging.getLogger(__name__)
        logger.setLevel(LOG_LEVEL)
        logger.handlers = []  # reset to avoid duplicate handlers on repeated runs
        fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(fmt)
        file_handler = RotatingFileHandler(log_file, maxBytes=100000, backupCount=3)
        file_handler.setFormatter(fmt)
        logger.addHandler(stream_handler)
        logger.addHandler(file_handler)

        def fetch_assignment_data(course_id, student_id):
            """
            Fetch all pages of assignment analytics for a student with retry/backoff.
            """
            headers = {"Authorization": f"Bearer {token}"}
            url = base_url_template.format(course_id, student_id)
            attempts = 0
            results = []

            while url:
                try:
                    resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
                    if resp.status_code == 429:
                        # rate limited; backoff and retry same page
                        attempts += 1
                        if attempts > RETRY_LIMIT:
                            logger.error(f"Rate limit exceeded for student {student_id} course {course_id}; giving up.")
                            return student_id, results or None
                        time.sleep(BACKOFF_SECONDS * attempts)
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    if isinstance(data, list):
                        results.extend(data)
                    else:
                        logger.warning(f"Unexpected response shape for student {student_id} course {course_id}")
                    # handle pagination
                    url = resp.links.get("next", {}).get("url")
                    attempts = 0  # reset attempts after success
                except requests.exceptions.RequestException as e:
                    attempts += 1
                    if attempts > RETRY_LIMIT:
                        logger.error(f"Failed to fetch data for student {student_id} in course {course_id}: {e}")
                        return student_id, results or None
                    time.sleep(BACKOFF_SECONDS * attempts)
            return student_id, results or None
            
        def merge_student_rosters(output_dir):
            roster_files = glob.glob(os.path.join(output_dir, '*_StudentRoster.csv'))
            if not roster_files:
                logger.warning("No *_StudentRoster.csv files found.")
                return None

            merged_df = pd.concat([pd.read_csv(file) for file in roster_files], ignore_index=True)
            merged_df.drop_duplicates(inplace=True)
            merged_path = os.path.join(output_dir, "StudentRoster.csv")
            merged_df.to_csv(merged_path, index=False)
            logger.info(f"Merged {len(roster_files)} roster files into {merged_path}")
            return merged_df

        def fetch_all_data_concurrently(course_id, student_ids):
            results = {}
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                future_to_id = {executor.submit(fetch_assignment_data, course_id, sid): sid for sid in student_ids}
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

        # def extract_transform_load(file_path):
        #     df = pd.read_excel(file_path)
        #     assignments_csv = file_path.replace(".xlsx", "_assignments.csv")
        #     submissions_csv = file_path.replace(".xlsx", "_submissions.csv")

        #     assignments_seen = set()
        #     with open(assignments_csv, mode='w', newline='', encoding='utf-8') as assignments_file, \
        #          open(submissions_csv, mode='w', newline='', encoding='utf-8') as submissions_file:

        #         assignments_writer = csv.writer(assignments_file)
        #         submissions_writer = csv.writer(submissions_file)

        #         assignments_writer.writerow(['id', 'title', 'due_date'])
        #         submissions_writer.writerow(['student_id', 'assignment_id', 'submitted_at', 'score', 'status'])

        #         for _, row in df.iterrows():
        #             student_id = row.get('Student ID')
        #             assignment_id = row.get('assignment_id')
        #             title = row.get('title')
        #             due_at = row.get('due_at')
        #             status = row.get('status')
        #             submitted_at = row.get('submitted_at')
        #             score = row.get('score')

        #             if assignment_id not in assignments_seen:
        #                 assignments_writer.writerow([assignment_id, title, due_at])
        #                 assignments_seen.add(assignment_id)

        #             submissions_writer.writerow([student_id, assignment_id, submitted_at, score, status])

        #     print(f"ETL complete. Files saved as:\n {assignments_csv}\n {submissions_csv}")
        def extract_transform_load(file_path, group_by_due_date=False):
            """
            group_by_due_date=False  -> de-dupe purely by title (recommended)
            group_by_due_date=True   -> de-dupe by (title, date-only(due_at))
            """
            df = pd.read_excel(file_path)
            assignments_csv = file_path.replace(".xlsx", "_assignments.csv")
            submissions_csv = file_path.replace(".xlsx", "_submissions.csv")

            def _normalize_title(t: str) -> str:
                if not t:
                    return ""
                return re.sub(r"\s+", " ", t).strip().lower()

            def _date_only(x):
                if pd.isna(x):
                    return ""
                dt = pd.to_datetime(x, errors="coerce")
                if pd.isna(dt):
                    return ""
                return dt.strftime("%Y-%m-%d")

            def _canon_id(title, due_at):
                key = _normalize_title(title)
                if group_by_due_date:
                    key = f"{key}|{_date_only(due_at)}"
                # stable 32-bit positive int for Django PK
                return zlib.crc32(key.encode("utf-8")) & 0xffffffff

            # maps canonical_id -> (title, chosen_due_at)
            canon_rows = {}
            with open(assignments_csv, mode='w', newline='', encoding='utf-8') as assignments_file, \
                open(submissions_csv, mode='w', newline='', encoding='utf-8') as submissions_file:

                assignments_writer = csv.writer(assignments_file)
                submissions_writer = csv.writer(submissions_file)

                assignments_writer.writerow(['id', 'title', 'due_date'])
                submissions_writer.writerow(['student_id', 'assignment_id', 'submitted_at', 'score', 'status'])

                for _, row in df.iterrows():
                    student_id   = row.get('Student ID')
                    title        = row.get('title')
                    due_at       = row.get('due_at')
                    status       = row.get('status')
                    submitted_at = row.get('submitted_at')
                    score        = row.get('score')

                    canon = _canon_id(title, due_at)

                    # keep first title as display; choose earliest non-null due date
                    if canon not in canon_rows:
                        canon_rows[canon] = [canon, title, due_at]
                    else:
                        prev_due = canon_rows[canon][2]
                        if pd.isna(prev_due) and not pd.isna(due_at):
                            canon_rows[canon][2] = due_at
                        elif not pd.isna(prev_due) and not pd.isna(due_at):
                            if pd.to_datetime(due_at) < pd.to_datetime(prev_due):
                                canon_rows[canon][2] = due_at

                    # every submission now points to canonical assignment id
                    submissions_writer.writerow([student_id, canon, submitted_at, score, status])

                # write unique assignments once
                for row_out in canon_rows.values():
                    assignments_writer.writerow(row_out)

            print(f"ETL complete. Files saved as:\n {assignments_csv}\n {submissions_csv}")


        # === MAIN EXECUTION ===
        logger.info("Merging student rosters...")
        merged_roster = merge_student_rosters(output_dir)
        if merged_roster is None:
            raise CommandError("No student roster files found to derive student IDs.")
        student_ids = merged_roster["Student ID"].astype(str).dropna().unique().tolist()
        if not student_ids:
            self.stdout.write(self.style.ERROR("No student IDs found in StudentRoster.csv."))
            return

        all_data = {}
        summary = defaultdict(lambda: {"students": 0, "ok": 0, "failed": 0})
        for course_id in course_ids:
            logger.info(f"Fetching assignments for {len(student_ids)} students in course {course_id}...")
            course_data = fetch_all_data_concurrently(course_id, student_ids)
            # for sid, data in course_data.items():
            #     if sid not in all_data or not all_data[sid]:
            #         all_data[sid] = data
            for sid, data in course_data.items():
                summary[course_id]["students"] += 1
                if not data:
                    summary[course_id]["failed"] += 1
                    continue
                if sid not in all_data or not all_data[sid]:
                    all_data[sid] = list(data)  # make a copy
                else:
                    all_data[sid].extend(data)
                summary[course_id]["ok"] += 1
        with open(raw_json_file, 'w') as f:
            json.dump(all_data, f, indent=2)
        logger.info(f"Raw assignment data saved to {raw_json_file}")

        df_cleaned = clean_assignment_data(all_data)
        df_cleaned.to_excel(excel_file, index=False)
        logger.info(f"Cleaned assignment data saved to {excel_file}")

        extract_transform_load(excel_file)

        self.stdout.write(self.style.SUCCESS(f"Raw JSON saved to: {raw_json_file}"))
        self.stdout.write(self.style.SUCCESS(f"Cleaned Excel saved to: {excel_file}"))
        # emit summary
        for course_id, stats in summary.items():
            logger.info(
                f"[course {course_id}] students:{stats['students']} ok:{stats['ok']} failed:{stats['failed']}"
            )
