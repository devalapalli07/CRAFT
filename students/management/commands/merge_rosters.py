
from django.core.management.base import BaseCommand
import pandas as pd
import glob
import os

# Folder where all *_StudentRoster.csv files are located
INPUT_DIR = 'data_exports'
OUTPUT_FILE = os.path.join(INPUT_DIR, 'StudentRoster.csv')

class Command(BaseCommand):
    help = 'Merges all *_StudentRoster.csv files into a single StudentRoster.csv file.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Scanning for *_StudentRoster.csv files...")
        # Step 1: Find all roster files in the folder
        roster_files = glob.glob(os.path.join(INPUT_DIR, '*_StudentRoster.csv'))

        if not roster_files:
            self.stdout.write(self.style.ERROR("No *_StudentRoster.csv files found in the directory."))
            return
        # Step 2: Load and combine all rosters
        combined_df = pd.concat([pd.read_csv(file) for file in roster_files], ignore_index=True)
        combined_df.drop_duplicates(inplace=True)
        # Step 3: Write merged file to StudentRoster.csv
        combined_df.to_csv(OUTPUT_FILE, index=False)

        self.stdout.write(self.style.SUCCESS(f"Merged {len(roster_files)} files into {OUTPUT_FILE}"))