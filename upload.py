import os
import json
import random
from datetime import datetime, timedelta

CLIPS_DIR = "../../EXPORT/CLIPSIM/READY"
SCHEDULE_LOG = "../../EXPORT/CLIPSIM/00_schedule.json"
SCHEDULED_DIR = "../../EXPORT/CLIPSIM/SCHEDULED"
UPLOADED_DIR = "../../EXPORT/CLIPSIM/UPLOADED"
UPLOAD_TIMES = [
    "6:00 AM",
    "8:00 AM",
    "10:00 AM",
    "12:00 PM",
    "2:00 PM",
    "4:00 PM",
    "6:00 PM",
    "8:00 PM",
]

def move_files_to_scheduled_folder(date_string):
    # Create folder if it doesn't exist
    folder_path = os.path.join(SCHEDULED_DIR, date_string)
    os.makedirs(folder_path, exist_ok=True)
    
    try:
        # Randomly select 8 clips
        clips = random.sample([file for file in os.listdir(CLIPS_DIR) if file.endswith('.mp4')], 8)
    except ValueError as e:
        # Handle the case where there are not enough clips available
        num_available_clips = len([file for file in os.listdir(CLIPS_DIR) if file.endswith('.mp4')])
        print(f"There are only {num_available_clips}/8 CLIPS available. Please add {8 - num_available_clips} CLIPS in order to schedule a new day.")
        exit(1)  # Exit the script

    for clip in clips:
        # Move clip and corresponding txt file
        clip_path = os.path.join(CLIPS_DIR, clip)
        txt_path = os.path.splitext(clip_path)[0] + ".txt"
        os.rename(clip_path, os.path.join(folder_path, clip))
        os.rename(txt_path, os.path.join(folder_path, os.path.basename(txt_path)))

def update_schedule_log(date_string, clips_info):
    with open(SCHEDULE_LOG, 'r+') as file:
        schedule_data = json.load(file)
        
        # Update scheduled days
        schedule_data['scheduled_days'].append({
            "date": date_string,
            "clips": clips_info
        })
        
        # Rewind the file pointer to overwrite the file
        file.seek(0)
        json.dump(schedule_data, file, indent=4)
        file.truncate()

def main():
    # Load schedule log
    with open(SCHEDULE_LOG, 'r') as file:
        schedule_data = json.load(file)
    
    # Get the last scheduled day
    last_scheduled_day = schedule_data['scheduled_days'][-1]['date']
    
    # Get next day
    next_day = datetime.strptime(last_scheduled_day, '%Y%m%d') + timedelta(days=1)
    next_day_string = next_day.strftime('%Y%m%d')
    
    # Move files to scheduled folder
    move_files_to_scheduled_folder(next_day_string)
    
    # Update schedule log
    clips_info = []
    folder_path = os.path.join(SCHEDULED_DIR, next_day_string)
    upload_times_index = 0  # Keep track of the index for upload times
    for file_name in os.listdir(folder_path):
        if file_name.endswith('.txt'):
            with open(os.path.join(folder_path, file_name), 'r', encoding='utf-8') as txt_file:
                title = txt_file.readline().strip()
                description = txt_file.read().strip()
                description = description.replace('memezar', 'popcorn-clips-and-chill')
                if 'follow' not in description.lower():
                    description = f"🎬⭐Follow us for more Popcorn, Clips & Chill.\n\n{description}"
                clips_info.append({
                    "time": UPLOAD_TIMES[upload_times_index],  # Use upload times sequentially
                    "title": title,
                    "description": description
                })
                upload_times_index += 1  # Move to the next upload time
        
    update_schedule_log(next_day_string, clips_info)

if __name__ == "__main__":
    main()
