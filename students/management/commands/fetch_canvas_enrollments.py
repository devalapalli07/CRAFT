import os
import logging
from logging.handlers import RotatingFileHandler
import requests
import pandas as pd
from ast import literal_eval
from datetime import datetime

from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Fetches and cleans Canvas enrollment data, saves both raw and cleaned Excel files'

    def handle(self, *args, **kwargs):
        # === CONFIGURATION ===
        base_dir = settings.BASE_DIR
        log_dir = os.path.join(base_dir, "log")
        output_dir = os.path.join(base_dir, "data_exports")
        os.makedirs(log_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        log_file = os.path.join(log_dir, 'canvas_api.log')
        raw_file = os.path.join(output_dir, 'enrollments_raw.xlsx')
        cleaned_file = os.path.join(output_dir, 'cleaned_enrollments_data.xlsx')

        api_url = "https://usflearn.instructure.com/api/v1/courses/1930464/enrollments"
        bearer_token = "13~WE6aXzRMrPTheVDUVn6cfQtV2VP7EtvDvfPJkt9fDEH9h9MY8JAJQQtB7a786mWu"
        headers = {"Authorization": f"Bearer {bearer_token}"}

        # === Logging Setup ===
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        file_handler = RotatingFileHandler(log_file, maxBytes=100000, backupCount=3)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(file_handler)

        # === Fetch Data ===
        def get_all_data(api_url, headers):
            all_data = []
            api_calls = 0
            while True:
                response = requests.get(api_url, headers=headers)
                api_calls += 1
                if response.status_code == 200:
                    data = response.json()
                    all_data.extend(data)
                    if 'next' in response.links:
                        api_url = response.links['next']['url']
                    else:
                        logging.info("No more records to retrieve.")
                        break
                else:
                    logging.error(f"Failed to fetch data. Status code: {response.status_code}")
                    break
            logging.info(f"Total API calls made: {api_calls}")
            return all_data

        # === Clean Data ===
        def clean_data(df):
            df['last_activity_at'] = pd.to_datetime(df['last_activity_at'], errors='coerce').dt.tz_localize(None)
            current_date = pd.to_datetime('today').tz_localize(None)

            df['inactive_days'] = (current_date - df['last_activity_at']).dt.days
            df['inactive_days'] = df['inactive_days'].apply(lambda x: max(x, 0) if pd.notnull(x) else None)
            df['total_activity_time(in_hrs)'] = df['total_activity_time'] / 3600

            columns_to_keep = [
                'user_id', 'type', 'role', 'last_activity_at', 'inactive_days',
                'total_activity_time(in_hrs)', 'sis_course_id', 'sis_section_id', 'sis_user_id', 'grades'
            ]
            df = df.loc[:, [col for col in columns_to_keep if col in df.columns]].copy()

            df.rename(columns={'user_id': 'Student ID'}, inplace=True)

            if 'grades' in df.columns:
                # Ensure 'grades' column is a dictionary
                def parse_grade(value):
                    if isinstance(value, dict):
                        return value
                    elif isinstance(value, str):
                        try:
                            return literal_eval(value)
                        except:
                            return {}
                    else:
                        return {}

                df['grades'] = df['grades'].apply(parse_grade)

                grade_components = [
                    'current_grade', 'current_score', 'final_grade', 'final_score',
                    'unposted_current_score', 'unposted_current_grade',
                    'unposted_final_score', 'unposted_final_grade'
                ]

                for component in grade_components:
                    df[component] = df['grades'].apply(
                        lambda x: f"{x.get(component):.2f}" if isinstance(x.get(component), (int, float)) else ""
                    )

                df.drop('grades', axis=1, inplace=True)

            return df

        # === Main Process ===
        logging.info("Starting data fetch from Canvas API...")
        all_data = get_all_data(api_url, headers)

        if all_data:
            df_raw = pd.DataFrame(all_data)
            df_raw.to_excel(raw_file, index=False)
            logging.info(f"Raw data saved to: {raw_file}")

            df_cleaned = clean_data(df_raw)
            df_cleaned.to_excel(cleaned_file, index=False)
            logging.info(f"Cleaned data saved to: {cleaned_file}")

            self.stdout.write(self.style.SUCCESS(f"✅ Raw file saved: {raw_file}"))
            self.stdout.write(self.style.SUCCESS(f"✅ Cleaned file saved: {cleaned_file}"))
        else:
            logging.warning("No data was fetched from the API.")
            self.stdout.write(self.style.WARNING("⚠️ No data fetched from API."))
