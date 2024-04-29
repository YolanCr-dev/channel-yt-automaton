import os
import re
import requests
from moviepy.editor import VideoFileClip
from lib.utility import sanitize_files, sanitize_filename
from pytube import YouTube
from pytube.innertube import _default_clients
from upload.upload_video import YouTubeUploader

from dotenv import load_dotenv
load_dotenv() # Load environment variables from .env file


# Upload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


_default_clients["ANDROID_MUSIC"] = _default_clients["ANDROID_CREATOR"]

# Set up YouTube Data API service
def get_youtube_service():
    api_key = os.getenv('YOUTUBE_API')  # Replace with your API key
    youtube = build('youtube', 'v3', developerKey=api_key)
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

def download_from_yt(url, output_dir="ASSETS/CLIPS"):
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

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

    # Select the highest resolution stream
    stream = yt.streams.get_highest_resolution()

    # Download the video
    temp_file_path = stream.download(output_path=output_path)

    # Get the filename from the temp file path
    temp_filename = os.path.basename(temp_file_path)

    # Print the new filename without actually renaming it
    new_filename = title + "." + temp_filename.split(".")[-1]
    new_file_path = os.path.join(output_path, new_filename)
    print("Downloaded", new_filename)

    # Download the thumbnail
    thumbnail_url = yt.thumbnail_url
    thumbnail_filename = title + "_thumbnail.jpg"
    thumbnail_path = os.path.join(output_path, thumbnail_filename)
    with open(thumbnail_path, 'wb') as thumbnail_file:
        thumbnail_file.write(requests.get(thumbnail_url).content)

   # Check if video ID is extracted successfully
    if video_id:
        captions_id = get_english_captions(video_id)
        output_path = 'captions.srt'
        download_captions(video_id, captions_id, output_path)
    else:
        print("Invalid YouTube URL. Please provide a valid URL.")

    # Download English subtitles (if available) as SRT file
    # subtitles = yt.captions.get_by_language_code('en')
    # if subtitles:
    #     subtitles_file_path = os.path.join(output_path, title + "_subtitles.srt")
    #     with open(subtitles_file_path, 'w', encoding='utf-8') as subtitles_file:
    #         subtitles_file.write(subtitles.generate_srt_captions())

    #     print("Downloaded subtitles:", subtitles_file_path)
    # else:
    #     print("No English subtitles found for this video.")

def upload_to_youtube(video_path, title, description, tags, privacy_status):

        
    # Example usage:
    # upload_to_youtube(
    #     video_path='ASSETS/CLIPS/your_video.mp4',
    #     title='Your Video Title',
    #     description='Your video description',
    #     tags=['tag1', 'tag2', 'tag3'],
    #     privacy_status='private'  # 'private', 'public', or 'unlisted'
    # )


    # Load credentials from client_secrets.json (you need to create this file with your client secrets)
    flow = InstalledAppFlow.from_client_secrets_file(
        'client_secrets.json',
        scopes=['https://www.googleapis.com/auth/youtube.upload']
    )
    credentials = flow.run_local_server()

    # Build the YouTube service
    youtube = build('youtube', 'v3', credentials=credentials)

    # Upload video
    request_body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags
        },
        'status': {
            'privacyStatus': privacy_status
        }
    }

    media_file = MediaFileUpload(video_path)

    response = youtube.videos().insert(
        part='snippet,status',
        body=request_body,
        media_body=media_file
    ).execute()

    print("Video uploaded successfully! Video ID:", response['id'])

def main():
    while True:
        command = input("Enter command (e.g., ): ")

        if command.startswith("download"):
            args = command[len("download"):].strip().split()
            if len(args) == 1:
                print("arg 1", args)
                youtube_url = args[0]
                download_from_yt(youtube_url)
            elif len(args) == 2:
                type, url = args
                if (type.lower() == "quote"):
                    download_from_yt(url, "../../ASSETS/QUOTES/")
                elif (type.lower() == "clip"):
                    download_from_yt(url, "../../ASSETS/CLIPS/")
                # https://www.youtube.com/watch?v=3p6qW7CBxxA
        
        elif command.startswith("upload"):            
            uploader = YouTubeUploader("client_secrets.json")
            args = command.split()

            options = {}
            for arg in args:
                if arg.startswith("--"):
                    key, value = arg.split("=")
                    options[key[2:]] = value.strip("'")

            required_args = ["file", "title", "description", "category", "keywords", "privacyStatus"]
            missing_args = [arg for arg in required_args if arg not in options]

            if missing_args:
                for arg in missing_args:
                    default_value = getattr(uploader, f"DEFAULT_{arg.upper()}", None)
                    
                    # Inside the loop where missing arguments are handled
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

            else:
                uploader.initialize_upload(options)

            print("go upload")
            uploader.initialize_upload(options)

        else:
            print("Invalid command")
            continue

        response = input("Do you want to continue? (y/n): ")
        if response.lower() == 'n':
            break


if __name__ == "__main__":
    main()
