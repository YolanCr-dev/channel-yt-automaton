import os
import re
import requests
import subprocess
from moviepy.editor import VideoFileClip
from lib.utility import sanitize_files, sanitize_filename
from pytube import YouTube
from pytube.innertube import _default_clients
from upload.upload_video import YouTubeUploader

from dotenv import load_dotenv
load_dotenv('.env.local') # Load environment variables from .env file

import pickle

from PIL import Image
from moviepy.editor import VideoFileClip, concatenate_videoclips

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

def trim_video(input_path, trim_start=0, trim_end=0):
    # Load the video clip
    video_clip = VideoFileClip(input_path)

    # Define the duration to trim from the start and end
    if trim_end is None:
        trim_end = video_clip.duration - 1.0

    # Trim the video clip
    trimmed_clip = video_clip.subclip(trim_start, trim_end)

    # Close the original video clip
    video_clip.reader.close()

    # Get the filename without extension
    filename, _ = os.path.splitext(input_path)

    # Define the output path for the trimmed video
    output_path = filename + "_trimmed.mp4"

    # Write the trimmed clip to the output file
    trimmed_clip.write_videofile(output_path)

    # Close the trimmed video clip
    trimmed_clip.reader.close()

    # Delete the original video file
    os.remove(os.path.abspath(input_path))

    # Rename the trimmed file to match the original filename
    os.rename(output_path, os.path.abspath(input_path))

def download_from_yt(url, start_time=0, end_time=0, output_dir="ASSETS/CLIPS",):
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    print("this url", url)
    # Get YouTube video
    yt = YouTube(url,
                use_oauth=True,
                allow_oauth_cache=True,
                )

    # Sanitize title for folder and filename
    title = sanitize_filename(yt.title)

    # Extract video ID from URL
    video_id = extract_video_id(url)

    # Create directory with sanitized title
    output_path = os.path.join(output_dir, title)
    os.makedirs(output_path, exist_ok=True)

    # Get streams
    streams = yt.streams.filter(progressive=True, file_extension='mp4')

    # Get highest resolution stream
    stream = yt.streams.get_highest_resolution()

    # Download the video using ffmpeg with specified start and end time
    output_file_path = os.path.join(output_path, f'{title}.mp4')
    command = ['ffmpeg', '-ss', str(start_time), '-i', stream.url, '-t', str(end_time - start_time), '-c:v', 'copy', '-c:a', 'copy', output_file_path]
    subprocess.run(command)

    print("Downloaded video")

    # Download the thumbnail
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
                clips.append(clip)
    
    # Add outro
    outro_clip = VideoFileClip("ASSETS/OUTRO/OUTRO-001.mp4")
    # Concatenate video clips  
    final_clip = concatenate_videoclips([*clips, outro_clip], method="compose")
    
    # Write final video
    output_path = f"ASSETS/VIDEOS/{topic}/{id}/{topic}_{id}.mp4"
    final_clip.write_videofile(output_path, codec="libx264", fps=24)

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
    # Extract start and end times from URL query parameters
    start_index = param.find("&start=")
    end_index = param.find("&end=")
    if start_index != -1 and end_index != -1:
        start_time_str = param[start_index + len("&start="):end_index]
        end_time_str = param[end_index + len("&end="):]
        
        start_time_secs = time_to_seconds(start_time_str)
        end_time_secs = time_to_seconds(end_time_str)
        
        return start_time_secs, end_time_secs
    else:
        return None, None

def time_to_seconds(time_str):
    # Convert time in the format mm:ss to seconds
    minutes, seconds = map(int, time_str.split(":"))
    return minutes * 60 + seconds

def main():
    while True:
        command = input("Enter command (e.g., ): ")

        if command.startswith("download"):
            # Parse command arguments
            args = command.split()
            output_dir = None
            youtube_url1 = youtube_url2 = youtube_url3 = None
            start_time1 = start_time2 = start_time3 = 0
            end_time1 = end_time2 = end_time3 = 0

            for arg in args:
                if arg.startswith("--url1="):
                    youtube_url1 = arg.split("=", 1)[1]
                    # youtube_url1 = arg.split("&")[0]
                    start_time1, end_time1 = parse_time_param(arg)
                elif arg.startswith("--url2="):
                    youtube_url2 = arg.split("&")[0]
                    start_time2, end_time2 = parse_time_param(arg)
                elif arg.startswith("--url3="):
                    youtube_url3 = arg.split("&")[0]
                    start_time3, end_time3 = parse_time_param(arg)
                elif arg.startswith("--topic="):
                    topic = arg.split("=")[1]
                    output_dir = f"ASSETS/VIDEOS/{topic}"

            if youtube_url1:
                download_from_yt(youtube_url1, start_time1, end_time1, output_dir)
            if youtube_url2:
                download_from_yt(youtube_url2, start_time2, end_time2, output_dir)
            if youtube_url3:
                download_from_yt(youtube_url3, start_time3, end_time3, output_dir)  




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
            topic = ""
            id = ""

            for arg in args:
                if arg.startswith("--topic="):
                    topic = arg.split("=")[1]
                elif arg.startswith("--id="):
                    id = arg.split("=")[1]
                
            assemble_video(topic, id)

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
