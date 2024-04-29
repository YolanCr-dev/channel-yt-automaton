from oauth2client.client import flow_from_clientsecrets

class YoutubeConnection:
    def __init__(self, client_secrets_file):
        self.CLIENT_SECRETS_FILE = client_secrets_file
        
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
