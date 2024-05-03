import os
import re
import requests
import subprocess
from datetime import datetime
import shutil
import pickle

from moviepy.editor import VideoFileClip
from lib.utility import sanitize_files, sanitize_filename
from pytube import YouTube
from pytube.innertube import _default_clients
from upload.upload_video import YouTubeUploader

from dotenv import load_dotenv
load_dotenv('.env.local') # Load environment variables from .env file


from PIL import Image
from moviepy.editor import VideoFileClip, concatenate_videoclips
from moviepy.video.fx.all import resize

# Upload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


_default_clients["ANDROID_MUSIC"] = _default_clients["ANDROID_CREATOR"]

# Set up YouTube Data API service
def get_youtube_service():
    # Load client secrets from file
    flow = InstalledAppFlow.from_client_secrets_file(
        'client_secrets.json', scopes=['https://www.googleapis.com/auth/youtube.force-ssl'])
    creds = flow.run_local_server(port=0)

    # Save the credentials for later use
    with open('token.pickle', 'wb') as token:
        pickle.dump(creds, token)

    # Build the YouTube Data API service
    youtube = build('youtube', 'v3', credentials=creds)
    return youtube

# Retrieve English captions for the video
def get_english_captions(video_id):
    youtube = get_youtube_service()
    request = youtube.captions().list(
        part='snippet',
        videoId=video_id
    )
    response = request.execute()
    for item in response['items']:
        if item['snippet']['language'] == 'en':
            return item['id']
    return None

# Download captions as SRT file
def download_captions(video_id, captions_id, output_path):
    if captions_id:
        youtube = get_youtube_service()
        request = youtube.captions().download(
            id=captions_id,
            tfmt='srt'
        )
        response = request.execute()
        with open(output_path, 'wb') as f:
            f.write(response)
        print("Downloaded captions:", output_path)
    else:
        print("No English captions found for this video.")

def extract_video_id(url):
    # Use regular expression to find video ID in URL
    match = re.search(r'(?<=v=)[^&]+', url)
    video_id = match.group() if match else None
    return video_id

def crop_image(image_path):
    # Get the absolute path of the directory containing the script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Construct the absolute path to the image
    abs_image_path = os.path.join(script_dir, image_path)
    
    # Open the image
    img = Image.open(abs_image_path)
    
    # Crop the image to 16:9 aspect ratio
    width, height = img.size
    aspect_ratio = 16 / 9
    if width / height > aspect_ratio:
        # Crop horizontally
        new_width = int(height * aspect_ratio)
        left = (width - new_width) / 2
        right = left + new_width
        img = img.crop((left, 0, right, height))
    else:
        # Crop vertically
        new_height = int(width / aspect_ratio)
        top = (height - new_height) / 2
        bottom = top + new_height
        img = img.crop((0, top, width, bottom))
    
    # Resize the cropped image to 1280x720
    img = img.resize((1280, 720), Image.ANTIALIAS)
    
    # Save the scaled image
    img.save(abs_image_path, format='JPEG')

def trim_video(input_path, trim_start=0, trim_end=None):
    # Load the video clip
    video_clip = VideoFileClip(input_path)

    # Define the duration of the video as a float
    duration = float(video_clip.duration)

    # Set default trim_end to the end of the video
    if trim_end is None:
        trim_end = duration
    else:
        trim_end = duration - trim_end
        

    # Ensure trim_start and trim_end are within the duration of the video
    trim_start = min(max(float(trim_start), 0), duration)
    trim_end = min(max(float(trim_end), 0), duration)

    # Check if the trim operation results in a non-negative duration
    if trim_start >= trim_end:
        print("Error: Invalid trim parameters. Trim end time should be greater than trim start time.")
        return

    # Trim the video clip
    trimmed_clip = video_clip.subclip(trim_start, trim_end)

    # Define the output path for the trimmed video
    output_path = input_path.replace(".mp4", "_trimmed.mp4")

    # Write the trimmed clip to the output file
    trimmed_clip.write_videofile(output_path)

    # Close the video clips
    video_clip.close()
    trimmed_clip.close()

    # Optionally, you may delete or rename the original video file here

    return output_path

def download_from_yt(url, start_time=0, end_time=0, output_dir="ASSETS/CLIPS",):
    os.makedirs(output_dir, exist_ok=True)
    yt = YouTube(url, use_oauth=True, allow_oauth_cache=True)
    title = sanitize_filename(yt.title)
    output_path = os.path.join(output_dir, title)
    os.makedirs(output_path, exist_ok=True)

    stream = yt.streams.get_highest_resolution()
    output_file_path = os.path.join(output_path, f'{title}.mp4')

    # Set start_time to 0 if it is None
    start_time = 0 if start_time is None else start_time

    # Get the duration of the video in seconds
    duration = yt.length

    # If end_time is None, set it to the duration of the video
    print(end_time)
    if end_time is None:
        end_time = duration

    command = ['ffmpeg', '-ss', str(start_time), '-i', stream.url, '-t', str(end_time - start_time), '-c:v', 'copy', '-c:a', 'copy', output_file_path]
    subprocess.run(command)

    thumbnail_url = yt.thumbnail_url
    thumbnail_filename = "thumbnail.jpg"
    thumbnail_path = os.path.join(output_path, thumbnail_filename)
    with open(thumbnail_path, 'wb') as thumbnail_file:
        thumbnail_file.write(requests.get(thumbnail_url).content)
    crop_image(thumbnail_path)

    # Prompt the user if they want to upload the file
    upload_choice = input("Do you want to upload this file? (y/n): ").lower()
    
    while True:
        # Prompt the user if they want to upload the file
        upload_choice = input("Do you want to upload this file? (y/n): ").lower()

        if upload_choice == 'y':
            upload_to_youtube(output_file_path)
            break  # Exit the loop if 'y' is entered
        elif upload_choice == 'n':
            print("File not uploaded.")
            break  # Exit the loop if 'n' is entered
        else:
            print("Invalid choice. Please enter 'y' or 'n'.")



    # Check if video ID is extracted successfully
    # print("going to download the captions")
    # if video_id:
    #     captions_id = get_english_captions(video_id)
    #     output_path = 'captions.srt'
    #     download_captions(video_id, captions_id, output_path)
    # else:
    #     print("Invalid YouTube URL. Please provide a valid URL.")

def upload_to_youtube(video_path, title='', description='', tags='', category='', privacy_status=''):

    # Initialize YouTubeUploader
    uploader = YouTubeUploader("client_secrets.json")

    # Construct options dictionary
    options = {
        "file": video_path,
        "title": title,
        "description": description,
        "keywords": tags,
        "category": category,
        "privacyStatus": privacy_status
    }

    # Prompt for missing arguments
    required_args = ["file", "title", "description", "category", "keywords", "privacyStatus"]
    # Prompt for missing or empty arguments
    missing_or_empty_args = [arg for arg in required_args if arg not in options or not options[arg]]

    if missing_or_empty_args:
        for arg in missing_or_empty_args:
            default_value = getattr(uploader, f"DEFAULT_{arg.upper()}", None)
            if arg == "file":
                while True:
                    value = input(f"Enter {arg.capitalize()} (default: {default_value}): ")
                    value = value.strip() or default_value
                    if os.path.exists(value):
                        options[arg] = value
                        break
                    else:
                        print("ERROR: File does not exist. Please enter a valid file path.")
            else:
                value = input(f"Enter {arg.capitalize()} (default: {default_value}): ").strip()
                options[arg] = value if value else default_value

    # Upload the video
    # print(options)
    print("Uploading video...")
    uploader.initialize_upload(options)
    print("Video uploaded successfully.")

def assemble_video(topic, id): 
    # Get video clips from each folder
    clips = []
    for i in range(1, 4):  # Assuming 3 folders
        folder_path = f"ASSETS/VIDEOS/{topic}/{id}/{i}"
        # Assuming random_file_names are all .mp4
        video_files = os.listdir(folder_path)
        for video_file in video_files:
            if video_file.endswith(".mp4"):
                clip = VideoFileClip(os.path.join(folder_path, video_file))
                # Resize the clip to 1920x1080
                clip = clip.resize((1920, 1080))
                clips.append(clip)
    
    # Add outro
    outro_clip = VideoFileClip("ASSETS/OUTRO/OUTRO-001.mp4")
    # Resize the outro clip to 1920x1080
    outro_clip = outro_clip.resize((1920, 1080))
    # Concatenate video clips  
    final_clip = concatenate_videoclips([*clips, outro_clip], method="compose")
    
    # Write final video
    output_path = f"ASSETS/VIDEOS/{topic}/{id}/{topic}_{id}.mp4"
    final_clip.write_videofile(output_path, fps=24)

    while True:
        # Prompt the user if they want to upload the file
        upload_choice = input("Do you want to upload this file? (y/n): ").lower()

        if upload_choice == 'y':
            upload_to_youtube(output_path)
            break  # Exit the loop if 'y' is entered
        elif upload_choice == 'n':
            print("File not uploaded.")
            break  # Exit the loop if 'n' is entered
        else:
            print("Invalid choice. Please enter 'y' or 'n'.")

def parse_time_param(param):
    print(param)
    start_index = param.find("&start=")
    end_index = param.find("&end=")
    print(end_index)
    if start_index != -1 and end_index != -1:
        start_time_str = param[start_index + len("&start="):end_index]
        end_time_str = param[end_index + len("&end="):]
        
        start_time_secs = time_to_seconds(start_time_str)
        end_time_secs = time_to_seconds(end_time_str)
        
        return start_time_secs, end_time_secs
    else:
        return None, None

def time_to_seconds(time_str):
    minutes, seconds = map(int, time_str.split(":"))
    return minutes * 60 + seconds

def assemble_videos(topic, assembly_folder):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    new_folder_path = os.path.join("ASSETS/VIDEOS", topic, timestamp)
    os.makedirs(new_folder_path, exist_ok=True)

    for i, folder_name in enumerate(sorted(os.listdir(assembly_folder))):
        src_folder = os.path.join(assembly_folder, folder_name)
        dst_folder = os.path.join(new_folder_path, str(i + 1))
        os.makedirs(dst_folder, exist_ok=True)
        
        # Counter to keep track of the number of files moved
        file_count = 0
        
        for filename in os.listdir(src_folder):
            src_file_path = os.path.join(src_folder, filename)
            dst_file_path = os.path.join(dst_folder, filename)
            
            # Move the file only if the file count is less than 3
            if file_count < 3:
                shutil.move(src_file_path, dst_file_path)  # Use shutil.move to move files
                file_count += 1
            else:
                break  # Break out of the loop if three files are already moved
        
        os.rmdir(src_folder)  # Remove the old folder

    assemble_video(topic, timestamp)
    
def main():
    while True:
        command = input("Enter command (e.g., ): ")

        if command.startswith("download"):
            args = command.split()
            output_dir = None
            youtube_urls = []
            start_times = []
            end_times = []
            topic = None

            for i, arg in enumerate(args):
                if arg.startswith("--url"):
                    # Check if there are enough elements in the list
                    print("arg starts with url", arg)
                    if i < len(args):
                        start_index = arg.find("=") + 1  # Find the index of the first '=' sign and add 1 to exclude it
                        end_index = arg.find("&") if "&" in arg else len(arg)  # Find the index of the first '&' sign
                        youtube_url = arg[start_index:end_index]
                        youtube_urls.append(youtube_url)
                        start_time, end_time = parse_time_param(arg)  # Parse time parameters from the same argument
                        start_times.append(start_time)
                        end_times.append(end_time)
                        print("start_time", start_time)
                        print("end_time", end_time)
                    else:
                        print("Error: Insufficient arguments for URL.")
                        break  # Exit the loop if there are insufficient arguments
                elif arg.startswith("--topic="):
                    topic = arg.split("=")[1]
                    output_dir = f"ASSETS/VIDEOS/{topic}"

            if topic == None:
                output_dir = f"ASSETS/CLIPS"

            if output_dir:
                # Create the output directory if it doesn't exist
                os.makedirs(output_dir, exist_ok=True)
                
                for i, url in enumerate(youtube_urls):
                    assembly_folder = os.path.join(output_dir, "assembly")
                    os.makedirs(assembly_folder, exist_ok=True)  # Create the 'assembly' folder if it doesn't exist
                    download_from_yt(url, start_times[i], end_times[i], assembly_folder)
                
                    assembly_folder = os.path.abspath(assembly_folder)
                    num_folders = len([name for name in os.listdir(assembly_folder) if os.path.isdir(os.path.join(assembly_folder, name))])

                    if num_folders == 3:
                        assemble_videos(topic, assembly_folder)

        elif command.startswith("trim"):
            # Parse command arguments
            args = command.split()

            # Extract parameters from command
            path = ""
            trim_start = 0
            trim_end = 0

            for arg in args:
                if arg.startswith("--path="):
                    path = arg.split("=")[1]
                elif arg.startswith("--trim_start="):
                    trim_start = arg.split("=")[1]
                elif arg.startswith("--trim_end="):
                    trim_end = arg.split("=")[1]
            
            trim_video(path, trim_start, trim_end)

        elif command.startswith("connect"):
            yt = get_youtube_service()
            print(yt)

        elif command.startswith("assemble"):
            # Parse command arguments
            args = command.split()

            # Extract parameters from command
            topic = None
            id = ""

            for arg in args:
                if arg.startswith("--topic="):
                    topic = arg.split("=")[1]
                elif arg.startswith("--id="):
                    id = arg.split("=")[1]
                
            if topic:
                output_dir = f"ASSETS/VIDEOS/{topic}"
                assembly_folder = os.path.abspath(os.path.join(output_dir, "assembly"))
                assemble_videos(topic, assembly_folder)
                # assemble_video(topic, id)

        elif command.startswith("upload"):            
            # Parse command arguments
            args = command.split()

            # Extract parameters from command
            video_path = ""
            title = ""
            description = ""
            tags = ""
            category = ""
            privacy_status = ""
            topic = ""
            id = ""

            for arg in args:
                if arg.startswith("--video_path="):
                    video_path = arg.split("=")[1]
                elif arg.startswith("--title="):
                    title = arg.split("=")[1]
                elif arg.startswith("--description="):
                    description = arg.split("=")[1]
                elif arg.startswith("--tags="):
                    tags = arg.split("=")[1]
                elif arg.startswith("--category="):
                    category = arg.split("=")[1]
                elif arg.startswith("--privacy_status="):
                    privacy_status = arg.split("=")[1]
                elif arg.startswith("--topic="):
                    topic = arg.split("=")[1]
                elif arg.startswith("--id="):
                    id = arg.split("=")[1]

            if not video_path and topic and id:
                directory = os.path.join("ASSETS", "VIDEOS", topic, id)
                # Assuming the first MP4 file is what you want
                for file_name in os.listdir(directory):
                    if file_name.endswith(".mp4"):
                        video_path = os.path.join(directory, file_name)
                        break  # Stop after finding the first MP4 file

            # Call upload_to_youtube function
            upload_to_youtube(video_path, title, description, tags, category, privacy_status)


        else:
            print("Invalid command")
            continue

        response = input("Do you want to continue? (y/n): ")
        if response.lower() == 'n':
            break


if __name__ == "__main__":
    main()
