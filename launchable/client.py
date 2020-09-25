import os

import requests


def _read_version(file):
    return open(os.path.join(os.path.dirname(__file__), file)).read().replace('\n', '')

class LaunchableClientFactory:
    BASE_URL_KEY = "NOSE_LAUNCHABLE_BASE_URL"
    API_TOKEN_KEY = "NOSE_LAUNCHABLE_API_TOKEN"

    DEFAULT_BASE_URL = "https://api.mercury.launchableinc.com"

    @classmethod
    def prepare(cls):
        url, org, wp, token = cls._parse_options()

        return LaunchableClient(url, org, wp, token, requests)

    @classmethod
    def _parse_options(cls):
        user, token = os.environ[cls.API_TOKEN_KEY].split(":", 1)
        org, workplace = user.split("/", 1)

        return cls._get_base_url(), org, workplace, token

    @classmethod
    def _get_base_url(cls):
        return os.getenv(cls.BASE_URL_KEY) or cls.DEFAULT_BASE_URL



class LaunchableClient:
    # TODO: Stop using a fictitious id once the server starts dynamic reordering
    FICTITIOUS_ID = "1"
    CLIENT_NAME = "nose-launchable"
    CLIENT_VERSION = _read_version('../version')

    def __init__(self, base_url, org_name, workspace_name, token, http):
        self.base_url = base_url
        self.org_name = org_name
        self.workspace_name = workspace_name
        self.token = token
        self.http = http

    def infer(self, test):
        url = "{}/intake/organizations/{}/workspaces/{}/inference".format(
            self.base_url,
            self.org_name,
            self.workspace_name
        )

        headers = {
            'Content-Type': 'application/json',
            'X-Client-Name': self.CLIENT_NAME,
            'X-Client-Version': self.CLIENT_VERSION,
            'Authorization': 'Bearer {}'.format(self.token)
        }
        body = self._request_body(test)

        res = self.http.post(url, headers=headers, json=body)
        res.raise_for_status()

        return res.json()

    def _request_body(self, test):
        return {
            "test": test,
            "session": {"id": self.FICTITIOUS_ID, "subject": self.FICTITIOUS_ID, "flavors": {}},
        }


