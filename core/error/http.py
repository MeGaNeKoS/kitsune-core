from urllib3 import BaseHTTPResponse


class HTTPRequestError(Exception):
    def __init__(self, response: BaseHTTPResponse, *args):
        super().__init__(*args)
        self.status_code = response.status
        self.response = response

    def __str__(self):
        return f"HTTPRequestError: Status code {self.status_code}, Response body: {self.response.data.decode('utf-8')}"
