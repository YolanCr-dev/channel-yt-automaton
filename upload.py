import os
import json
import random
import shutil
from datetime import datetime, timedelta
from upload.upload_video import YouTubeUploader

CLIPS_DIR = "../../EXPORT/CLIPS/READY"
SCHEDULE_LOG = "../../EXPORT/CLIPS/00_schedule.json"
SCHEDULED_DIR = "../../EXPORT/CLIPS/SCHEDULED"
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADED_DIR = "../../EXPORT/CLIPS/UPLOADED"
UPLOAD_TIMES = [
    "06:00:00",
    "08:00:00",
    "10:00:00",
    "12:00:00",
    "14:00:00",
    "16:00:00",
    "18:00:00",
    "20:00:00",
]

class AutoUpload():
    def  __init__(self):
        pass

    def update_schedule(self):
        while True:
            # Load schedule log
            with open(SCHEDULE_LOG, 'r') as file:
                schedule_data = json.load(file)
            
            # Get the last scheduled day
            last_scheduled_day = schedule_data['scheduled_days'][-1]['date']
            
            # Get next day
            next_day = datetime.strptime(last_scheduled_day, '%Y%m%d') + timedelta(days=1)
            next_day_string = next_day.strftime('%Y%m%d')
            
            # Move files to scheduled folder
            self.move_files_to_scheduled_folder(next_day_string)
            
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
                            "description": description,
                            "file_name": file_name.replace(".txt", ".mp4")
                        })
                        upload_times_index += 1  # Move to the next upload time
            
            self.update_schedule_log(next_day_string, clips_info)

            # Check if there are fewer than 8 clips scheduled
            num_scheduled_clips = len(clips_info)
            if num_scheduled_clips < 8:
                print(f"Scheduled {num_scheduled_clips} clips for {next_day_string}.")
                break  # Exit the loop if there are fewer than 8 clips scheduled
            else:
                print(f"Scheduled 8 clips for {next_day_string}.")

    def move_files_to_scheduled_folder(self, date_string):
        # Create folder if it doesn't exist
        folder_path = os.path.join(SCHEDULED_DIR, date_string)
        os.makedirs(folder_path, exist_ok=True)
        
        try:
            # Randomly select 8 clips
            clips = random.sample([file for file in os.listdir(CLIPS_DIR) if file.endswith('.mp4')], 8)
        except ValueError as e:
            # Handle the case where there are not enough clips available
            num_available_clips = len([file for file in os.listdir(CLIPS_DIR) if file.endswith('.mp4')])
            raise ValueError(f"There are only {num_available_clips}/8 CLIPS available. Please add {8 - num_available_clips} CLIPS in order to schedule a new day.")

        for clip in clips:
            # Move clip and corresponding txt file
            clip_path = os.path.join(CLIPS_DIR, clip)
            txt_path = os.path.splitext(clip_path)[0] + ".txt"
            os.rename(clip_path, os.path.join(folder_path, clip))
            os.rename(txt_path, os.path.join(folder_path, os.path.basename(txt_path)))

    def update_schedule_log(self, date_string, clips_info):
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

    def upload_to_youtube(self):
        # Initialize YouTubeUploader
        uploader = YouTubeUploader("client_secrets.json")

        # Get today's date
        today = datetime.now().date()

        # Generate the "upcoming_week" of 7 days into the future including today
        upcoming_week = [(today + timedelta(days=i)).strftime("%Y%m%d") for i in range(7)]

        # Load SCHEDULE_LOG JSON
        with open(SCHEDULE_LOG, "r") as f:
            schedule_log = json.load(f)

        # Loop over upcoming_week
        for index, upcoming_day in enumerate(upcoming_week):
            print(f'upcoming day {index} {"(today)" if index == 0 else ""}{"(tomorrow)" if index == 1 else ""}({upcoming_day})')
            # Find match between upcoming_day and scheduled_day
            for scheduled_day in schedule_log["scheduled_days"]:
                if upcoming_day == scheduled_day["date"]:
                    # Loop over the clips
                    for clip_index, clip in enumerate(scheduled_day["clips"]):
                        # Check if clip has time, title, description, and file_name
                        if "time" not in clip or "title" not in clip or "description" not in clip or "file_name" not in clip:
                            # Ask for input
                            clip["time"] = input("Enter clip time: ")
                            clip["title"] = input("Enter clip title: ")
                            clip["description"] = input("Enter clip description: ")
                            clip["file_name"] = input("Enter clip file name: ")

                        # Create options object
                        scheduled_day_date = datetime.strptime(scheduled_day["date"], "%Y%m%d").strftime("%Y-%m-%d")
                        rel_file_path = f"../../EXPORT/CLIPS/SCHEDULED/{scheduled_day['date']}/{clip['file_name']}"
                        abs_file_path = os.path.abspath(os.path.join(CURRENT_DIR, rel_file_path))
                        options = {
                            "file": abs_file_path,
                            "title": clip["title"],
                            "description": f"{clip['description']}\n\n",
                            "keywords": getattr(uploader, "DEFAULT_KEYWORDS", None),
                            "category": getattr(uploader, "DEFAULT_CATEGORY", None),
                            "privacyStatus":  getattr(uploader, "DEFAULT_PRIVACYSTATUS", None),
                            "scheduleDateTime": f"{scheduled_day_date}T{clip['time']}Z",
                            "set_thumbnail": False
                        }

                        # Upload the video
                        print("Uploading video...")
                        print("options", options)
                        uploader.initialize_upload(options) #UPLOAD TO YT
                        print("Video uploaded successfully.")

                        # Update schedule_log JSON
                        # Create a new entry in uploaded_to_yt
                        uploaded_clip = clip.copy()
                        uploaded_clip["file_name"] = f"{clip['file_name']}-yt.mp4"
                        uploaded_clip["uploaded_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        # Append the uploaded clip to uploaded_to_yt
                        schedule_log["uploaded_to_yt"].append({
                            "date": scheduled_day["date"],
                            "clips": [uploaded_clip]
                        })

                        # Remove the uploaded clip from scheduled_days/day/clips array
                        scheduled_day["clips"][clip_index]
                        del scheduled_day["clips"][clip_index]

                        # Update the SCHEDULE_LOG JSON file
                        with open(SCHEDULE_LOG, "w") as f:
                            json.dump(schedule_log, f, indent=4)

                        # Move the video and text file to UPLOADED directory
                        old_video_path = os.path.join("..", "..", "EXPORT", "CLIPS", "SCHEDULED", scheduled_day["date"], clip['file_name'])
                        new_video_name = clip['file_name'].replace(".mp4", "-yt.mp4")
                        new_video_path = os.path.join("..", "..", "EXPORT", "CLIPS", "UPLOADED", scheduled_day["date"], new_video_name)

                        # Create the directory if it doesn't exist
                        new_video_dir = os.path.dirname(new_video_path)
                        if not os.path.exists(new_video_dir):
                            os.makedirs(new_video_dir)

                        shutil.move(old_video_path, new_video_path)

                        # Also move the corresponding text file if it exists
                        old_text_path = os.path.splitext(old_video_path)[0] + ".txt"
                        if os.path.exists(old_text_path):
                            new_text_name = os.path.splitext(new_video_name)[0] + ".txt"
                            new_text_path = os.path.join(new_video_dir, new_text_name)
                            shutil.move(old_text_path, new_text_path)

                        # VIDEO UPLOADED - FILES MOVED
                        # break # ONLY 1 VIDEO A DAY

def main():

    self = AutoUpload()
    
    try:
        self.update_schedule()
    except ValueError as e:
        print(str(e))
        pass
    
    self.upload_to_youtube()
    # while True:
    #     command = input("Enter command (e.g., ): ")
    #     if command.startswith("update"):
    #         self.update_schedule()
    #     elif command.startswith("upload"):
    #         self.upload_to_youtube()

if __name__ == "__main__":
    main()
