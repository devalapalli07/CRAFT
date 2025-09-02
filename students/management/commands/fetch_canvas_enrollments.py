# Updated fetch_canvas_enrollments.py with multi-course support
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
    help = 'Fetch and merge Canvas enrollment data from multiple courses'

    def handle(self, *args, **kwargs):
        base_dir = settings.BASE_DIR
        output_dir = os.path.join(base_dir, "data_exports")
        os.makedirs(output_dir, exist_ok=True)

        final_cleaned_file = os.path.join(output_dir, 'cleaned_enrollments_data.xlsx')

        bearer_token = "13~z9rZFUBQVkNnCrHctw4KBDHauRA43DWVEuzNKrHW2Pe8EtfMZDThaLRNZu63xyDJ"
        headers = {"Authorization": f"Bearer {bearer_token}"}

        course_ids = [
            "1987936", "1995292","1995626", "1985532"
        ]

        def get_all_data(api_url, headers):
            all_data = []
            while api_url:
                response = requests.get(api_url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    all_data.extend(data)
                    api_url = response.links['next']['url'] if 'next' in response.links else None
                else:
                    logging.warning(f"Failed to fetch data. Status code: {response.status_code}")
                    break
            return all_data

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

        all_dataframes = []

        for course_id in course_ids:
            api_url = f"https://usflearn.instructure.com/api/v1/courses/{course_id}/enrollments"
            raw_file = os.path.join(output_dir, f'enrollments_raw_{course_id}.xlsx')
            cleaned_file = os.path.join(output_dir, f'enrollments_cleaned_{course_id}.xlsx')

            logging.info("Starting data fetch from Canvas API...")
            all_data = get_all_data(api_url, headers)

            if all_data:
                df_raw = pd.DataFrame(all_data)
                df_raw.to_excel(raw_file, index=False)
                logging.info(f"Raw data saved to: {raw_file}")

                df_cleaned = clean_data(df_raw)
                df_cleaned.to_excel(cleaned_file, index=False)
                logging.info(f"Cleaned data saved to: {cleaned_file}")

                all_dataframes.append(df_cleaned)
                self.stdout.write(self.style.SUCCESS(f"Raw file saved: {raw_file}"))
                self.stdout.write(self.style.SUCCESS(f"Cleaned file saved: {cleaned_file}"))
            else:
                logging.warning("No data was fetched from the API.")
                self.stdout.write(self.style.WARNING(f"No data fetched from API for course {course_id}"))

        if all_dataframes:
            final_df = pd.concat(all_dataframes, ignore_index=True)
            final_df.to_excel(final_cleaned_file, index=False)
            self.stdout.write(self.style.SUCCESS(f"Merged cleaned data saved to: {final_cleaned_file}"))
        else:
            self.stdout.write(self.style.WARNING("No data to merge into final cleaned file."))
