#!/usr/bin/python

import httplib2
import os
import random
import sys
import time
import argparse

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
        self.DEFAULT_PRIVACY_STATUS = "private"

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

        tags = options.get("keywords", self.DEFAULT_KEYWORDS).split(",")
        title = options.get("title", "Your Video Title")
        description = options.get("description", "Your video description")
        category = options.get("category", self.DEFAULT_CATEGORY)
        privacy_status = options.get("privacyStatus", self.DEFAULT_PRIVACY_STATUS)

        body = dict(
            snippet=dict(
                title=title,
                description=description,
                tags=tags,
                categoryId=category
            ),
            status=dict(
                privacyStatus=privacy_status
            )
        )

        insert_request = youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=MediaFileUpload(options["file"], chunksize=-1, resumable=True)
        )

        # print("will insert request with body")
        # print(body)
        # print(options["file"])
        self.resumable_upload(insert_request)

    def resumable_upload(self, insert_request):
        response = None
        error = None
        retry = 0

        while response is None:
            try:
                print("Uploading file...")
                status, response = insert_request.next_chunk()

                if response is not None:
                    if 'id' in response:
                        print("Video id '%s' was successfully uploaded." % response['id'])
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
