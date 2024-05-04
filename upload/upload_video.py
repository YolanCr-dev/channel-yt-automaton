#!/usr/bin/python

import httplib2
import os
import random
import sys
import time
import argparse
from datetime import datetime

from apiclient.discovery import build
from apiclient.errors import HttpError
from apiclient.http import MediaFileUpload
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow


class YouTubeUploader:
    def __init__(self, client_secrets_file):
        self.CLIENT_SECRETS_FILE = client_secrets_file
        self.YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
        self.YOUTUBE_API_SERVICE_NAME = "youtube"
        self.YOUTUBE_API_VERSION = "v3"

        self.MAX_RETRIES = 10
        self.RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError)
        self.RETRIABLE_STATUS_CODES = [500, 502, 503, 504]
        self.VALID_PRIVACY_STATUSES = ("public", "private", "unlisted")

        self.DEFAULT_KEYWORDS = "movie clip, cinema, popular"
        self.DEFAULT_CATEGORY = "24"
        self.DEFAULT_PRIVACYSTATUS = "private"

    def get_authenticated_service(self):
        flow = flow_from_clientsecrets(
            self.CLIENT_SECRETS_FILE,
            scope=self.YOUTUBE_UPLOAD_SCOPE
        )

        storage = Storage("oauth2.json")
        credentials = storage.get()

        if credentials is None or credentials.invalid:
            credentials = run_flow(flow, storage)

        return build(self.YOUTUBE_API_SERVICE_NAME, self.YOUTUBE_API_VERSION, http=credentials.authorize(httplib2.Http()))

    def initialize_upload(self, options):
        youtube = self.get_authenticated_service()
        
        title = options.get("title", "Your Video Title")
        description = options.get("description", "Your video description")
        description_tail = f'''🎬Fair use.
        Copyright Disclaimer Under Section 107 of the Copyright Act 1976, allowance is made for "fair use" for purposes such as criticism, comment, news reporting, teaching, scholarship, and research. Fair use is a use permitted by copyright statute that might otherwise be infringing. Non-profit, educational or personal use tips the balance in favor of fair use. No copyright infringement intended.'''
        full_description = f"{description}\n\n{description_tail}"
        tags = options.get("keywords", self.DEFAULT_KEYWORDS).split(",")
        category = options.get("category", self.DEFAULT_CATEGORY)
        privacy_status = options.get("privacyStatus", self.DEFAULT_PRIVACYSTATUS)
        set_thumbnail = options.get("set_thumbnail", self.DEFAULT_PRIVACYSTATUS)
        # Extracting schedule date and time from options
        schedule_date_time_str = options.get("scheduleDateTime", None)
        schedule_date_time = None
        if schedule_date_time_str:
            schedule_date_time = datetime.strptime(schedule_date_time_str, "%Y-%m-%dT%H:%M:%SZ")

        body = dict(
            snippet=dict(
                title=title,
                description=full_description,
                tags=tags,
                categoryId=category
            ),
            status=dict(
                privacyStatus=privacy_status
            )
        )

        # If schedule date and time is provided, add it to the request body
        if schedule_date_time:
            body["status"]["publishAt"] = schedule_date_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        insert_request = youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=MediaFileUpload(options["file"], chunksize=-1, resumable=True)
        )

        file_dir = os.path.dirname(options["file"])
        self.resumable_upload(insert_request, file_dir, set_thumbnail)

    def set_thumbnail(self, file_dir, video_id):
        youtube = self.get_authenticated_service()

        # Check if thumbnail file exists
        thumbnail_path = os.path.join(file_dir, "thumbnail.jpg")
        while not os.path.exists(thumbnail_path):
            print(f"Thumbnail file 'thumbnail.jpg' not found in the same folder as the video file.")
            choice = input(f"Upload the thumbnail to this folder '{file_dir}' and press Enter to continue, enter 'y' for manual input, enter 'n' to skip (y/n): ")
            if choice.lower() == 'y':
                thumbnail_path = input("Enter the path to the thumbnail file: ")
                continue
            elif choice.lower() == 'n':
                break

        print("Great! I found the thumbnail.")

        # Upload thumbnail
        if os.path.exists(thumbnail_path):
            print("Uploading thumbnail...")
            thumbnail_upload_request = youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path)
            )
            response = thumbnail_upload_request.execute()
            print("Thumbnail uploaded successfully.")

    def resumable_upload(self, insert_request, file_dir, set_thumbnail):
        response = None
        error = None
        retry = 0

        while response is None:
            try:
                print("Uploading file...")
                status, response = insert_request.next_chunk()

                if response is not None:
                    if 'id' in response:
                        video_id = response['id']
                        print("Video id '%s' was successfully uploaded." % video_id)

                        # Write the video ID to a text file
                        with open('yt_upload.txt', 'w') as f:
                            f.write(f"id={video_id}\n")

                        if set_thumbnail:
                            self.set_thumbnail(file_dir, video_id)

                    else:
                        exit("The upload failed with an unexpected response: %s" % response)

            except HttpError as e:
                if e.resp.status in self.RETRIABLE_STATUS_CODES:
                    error = "A retriable HTTP error %d occurred:\n%s" % (e.resp.status, e.content)
                else:
                    raise
            except self.RETRIABLE_EXCEPTIONS as e:
                error = "A retriable error occurred: %s" % e

            if error is not None:
                print(error)
                retry += 1

                if retry > self.MAX_RETRIES:
                    exit("No longer attempting to retry.")

                max_sleep = 2 ** retry
                sleep_seconds = random.random() * max_sleep
                print("Sleeping %f seconds and then retrying..." % sleep_seconds)
                time.sleep(sleep_seconds)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Upload video to YouTube')
    parser.add_argument("--file", required=True, help="Video file to upload")
    parser.add_argument("--title", help="Video title", default="Test Title")
    parser.add_argument("--description", help="Video description", default="Test Description")
    parser.add_argument("--category", default="22", help="Numeric video category.")
    parser.add_argument("--keywords", help="Video keywords, comma separated", default="")
    parser.add_argument("--privacyStatus", choices=("public", "private", "unlisted"), default="private", help="Video privacy status.")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        exit("Please specify a valid file using the --file parameter.")

    options = {
        "video_path": args.file,
        "title": args.title,
        "description": args.description,
        "keywords": args.keywords,
        "category": args.category,
        "privacy_status": args.privacyStatus  # 'private', 'public', or 'unlisted'
    }

    uploader = YouTubeUploader("client_secrets.json")
    uploader.initialize_upload(args)
