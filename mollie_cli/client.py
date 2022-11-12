# SPDX-FileCopyrightText: 2022-present Tom Hendrikx <tom@whyscream.net>
#
# SPDX-License-Identifier: MIT
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import click
from mollie.api.client import Client as MollieClient
from mollie.api.error import Error as NativeMollieError
from oauthlib.oauth2.rfc6749.errors import OAuth2Error


class APIError(Exception):
    """An error has ocurred while talking to the API."""

    pass


class ClientError(Exception):
    """Something went wrong in our Client."""

    pass


class BaseAPIClient:
    def find_resource_name(self, hint):
        """Try to find a known resource by a partial name"""
        map_ = self.get_supported_resources_map()

        if hint in map_.keys():
            # Found a direct match
            return hint
        else:
            # Try to match a substring
            resources = [name for name in map_.keys() if hint in name]
            if not resources:
                raise ClientError(
                    f"No resource found for name '{hint}', "
                    f"use one of: {', '.join(map_.keys())}"
                )
            elif len(resources) > 1:
                raise ClientError(
                    f"Hint matches multiple resources: {', '.join(resources)}",
                )
            else:
                return resources[0]

    def list(self, resource_name, limit):
        """List resources by"""
        resource_name = self.find_resource_name(resource_name)

        resource = getattr(self._client, resource_name)
        params = self.get_params(limit=limit)
        try:
            result = resource.list(**params)
        except NativeMollieError as exc:
            raise APIError(exc) from exc
        except AttributeError:
            raise ClientError(
                f"Resource '{resource_name}' doesn't support listing"
            )  # noqa: E501

        return result, resource_name

    def get(self, resource_id, hint):
        if hint:
            resource_name = self.find_resource_name(hint)
        else:
            map_ = self.get_supported_resources_map()
            resource_name = None
            for name, prefix in map_.items():
                if resource_id.startswith(prefix):
                    resource_name = name
                    break

        if not resource_name:
            raise ClientError(
                f"Cannot find a resource for id '{resource_id}'",
            )
        resource = getattr(self._client, resource_name)

        params = self.get_params()
        try:
            result = resource.get(resource_id, **params)
        except NativeMollieError as exc:
            raise APIError(exc) from exc
        except AttributeError:
            raise ClientError(
                f"Resource '{resource_name}' doesn't support getting single objects",  # noqa: E501
            )

        return result, resource_name

    def get_supported_resources_map(self):
        """Generate a map of resource names and prefixes."""
        resources = {}
        for attrname in dir(self._client):
            attr = getattr(self._client, attrname)
            try:
                prefix = getattr(attr, "RESOURCE_ID_PREFIX")
                if prefix:
                    resources[attrname] = prefix
            except AttributeError:
                pass

        return resources


class APIClient(BaseAPIClient):
    def __init__(self, key, testmode=False):
        self._testmode = testmode
        self._client = MollieClient()

        if key.startswith(("test_", "live_")):
            self._client.set_api_key(key)

        elif key.startswith("access_"):
            self._client.set_access_token(key)

    def get_params(self, **params):
        if self._testmode:
            params.update({"testmode": "true"})
        return params


class OAuthAPIClient(BaseAPIClient):
    TOKEN_PATH = Path.home() / ".mollie-cli-token.json"

    SCOPE = [
        "refunds.read",
        "onboarding.read",
        "customers.read",
        "shipments.read",
        "mandates.read",
        "invoices.read",
        "profiles.read",
        "subscriptions.read",
        "orders.read",
        "organizations.read",
        "settlements.read",
        "payments.read",
    ]

    def __init__(self, client_id, client_secret, redirect_uri, testmode=False):
        self._testmode = testmode
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._client = MollieClient()

    def oauth_authorize(self):
        token = self.get_token()
        is_authorized, authorization_url = self._client.setup_oauth(
            self._client_id,
            self._client_secret,
            self._redirect_uri,
            self.SCOPE,
            token,
            self.set_token,
        )
        if not is_authorized:
            # If we have no valid OAuth token, we need to (re-)authorize
            if not (self._redirect_uri and self._client_id and self._client_secret):
                raise ClientError(
                    "OAuth authorization required, make sure to provide "
                    "Client ID, Client Secret and Redirect URI"
                )
            self.perform_authorization(authorization_url)

    def perform_authorization(self, authorization_url):
        # Start a http server in the background
        click.echo("Starting HTTP server")

        server = OAuthHTTPServer(
            ("localhost", 5000), OAuthResponseHandler, apiclient=self
        )

        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()
        click.echo("HTTP server started")

        confirm_text = f"""
            This CLI application is not authorized yet to access your Mollie
            data. Please visit the following URL to continue. Continue only
            when you have completed the Authorization flow in your browser.

            {authorization_url}
        """
        click.echo(confirm_text)

        if click.confirm("Open the URL in a brower for you?", default=False):
            click.launch(authorization_url)

        time.sleep(10)
        click.confirm("Did you complete the flow?", abort=True)

    def handle_authorization_response(self, redirect_url):
        self._client.setup_oauth_authorization_response(redirect_url)

    @classmethod
    def get_token(cls):
        if cls.TOKEN_PATH.exists():
            return json.loads(cls.TOKEN_PATH.read_text())

    @classmethod
    def set_token(cls, token):
        cls.TOKEN_PATH.write_text(json.dumps(token))

    def get_params(self, **params):
        if self._testmode:
            params.update({"testmode": "true"})
        return params


class OAuthHTTPServer(HTTPServer):
    """HTTP server that accepts an instance of the OAuth API Client."""

    def __init__(
        self,
        server_address,
        RequestHandlerClass,
        bind_and_activate=True,
        apiclient=None,
    ):
        self.apiclient = apiclient
        super().__init__(
            server_address,
            RequestHandlerClass,
            bind_and_activate,
        )


class OAuthResponseHandler(BaseHTTPRequestHandler):
    """HTTP request handler that processes the OAuth authorization response."""

    def do_GET(self):
        # Reconstruct the request url
        host = self.server.server_name
        port = self.server.server_port
        path = self.path
        # we mock https here, since it is required for OAuth2.0, but we use
        # the external ngrok server to provide it for us.
        request_uri = f"https://{host}:{port}{path}"
        try:
            self.server.apiclient.handle_authorization_response(request_uri)
        except OAuth2Error as exc:
            payload = f"""
            <h1>OAuth error: {exc}</h1>
            <p>
                If you're here to complete an Oauth authorization flow,
                this is bad news.
            </p>
            """
        else:
            payload = """
            <h1>OAuth authorization was succesful!</h1>
            """

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(payload.encode())
