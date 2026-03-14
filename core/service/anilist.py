import atexit
import json
import logging
import threading
import urllib
import webbrowser
from collections import defaultdict
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from socket import socket
from typing import Callable, Tuple, Union, cast, Type, List, Dict
from urllib.parse import urlparse, parse_qs

import urllib3
from devlog import log_on_start, log_on_end, log_on_error
from sqlalchemy.orm import Session
from sqlalchemy.sql.operators import gt

import env
from core.error.service.anilist import AnilistUserNoMediaCollectionError, AnilistUserNotFoundError, AnilistMediaNotFoundError, AnilistNoUserError, \
    AnilistNoRefreshUserError
from core.error.server import ServerRunningError, ClientSecretNotProvidedError, ServerFailedToStartError
from core.error.http import HTTPRequestError
from core.helper.misc import sort_dict, TokenContainer
from core.interfaces.database.const.anilist import QueryNames
from core.interfaces.database.const.service import ServiceName
from core.interfaces.database.models.Media import AnilistMedia
from core.interfaces.database.models.Service import ServiceCreds, AnilistUserEntry
from core.interfaces.database.types.anilist.enums import AnilistMediaType, AnilistMediaSeason
from core.interfaces.database.types.anilist.fields import TokenResponse, TransformedTokenResponse, AnilistCredsInfo, \
    PageInfo, DefaultMediaFields, DefaultUserEntryFields


_anilist_session = urllib3.PoolManager()


class AnilistAuthClient:
    """
    This class provides methods for authenticating with the Anilist API using OAuth 2.0.

    Methods:
        set_client_id(cls, client_id: str) -> None:
            Sets the client ID for OAuth authentication.

        set_client_secret(cls, client_secret: str) -> None:
            Sets the client secret for OAuth authentication.

        set_redirect_uri(cls, redirect_uri: str) -> None:
            Sets the redirect URI for OAuth authentication.

        generate_auth_url(cls, auth_code: bool = True) -> str:
            Generates the authorization URL to which the user should be redirected.

        start_auth_server(cls, code_callback: Callable[[str], None]) -> threading.Thread:
            Starts a local server to listen for the OAuth callback and extract the authorization code.

        _make_handler(cls, code_callback: Callable[[str], None]) -> Callable:
            Creates a request handler for the local server that processes the OAuth callback.

        fetch_token(cls, code: str) -> dict:
            Exchanges the authorization code for an access token.

    Attributes:
        CLIENT_ID (str): The client ID for OAuth authentication, loaded from environment variables.
        CLIENT_SECRET (str): The client secret for OAuth authentication, loaded from environment variables.
        REDIRECT_URI (str): The redirect URI for OAuth authentication, loaded from environment variables.
        AUTH_URL (str): The URL to initiate OAuth authorization.
        TOKEN_URL (str): The URL to exchange the authorization code for an access token.

    Exceptions:
        RuntimeError: Raised if an instance of the server is already running or if the local server fails to start.
        ValueError: Raised if the client secret is not provided when required.

    Returns:
        The methods of this class return various types depending on their function, including None, str, threading.Thread, and dict.
    """
    CLIENT_ID = env.ANILIST_CLIENT_ID
    CLIENT_SECRET = env.ANILIST_CLIENT_SECRET
    REDIRECT_URI = env.ANILIST_REDIRECT_URI
    AUTH_URL = 'https://anilist.co/api/v2/oauth/authorize'
    TOKEN_URL = 'https://anilist.co/api/v2/oauth/token'

    _server_instance: Union[HTTPServer, None] = None
    _server_lock = threading.Lock()

    @classmethod
    def set_client_id(cls, client_id):
        cls.CLIENT_ID = client_id

    @classmethod
    def set_client_secret(cls, client_secret):
        cls.CLIENT_SECRET = client_secret

    @classmethod
    def set_redirect_uri(cls, redirect_uri):
        cls.REDIRECT_URI = redirect_uri

    @classmethod
    def generate_auth_url(cls, auth_code: bool = True):
        """
        Generates an authentication URL with necessary parameters.

        This method constructs an URL for authentication based on the client ID and
        the response type required. It can generate URLs for both authorization code
        flow and implicit token flow.

        Parameters:
            auth_code (bool): A flag to determine the type of authentication flow.
                              If True, it uses the authorization code flow ('code'),
                              otherwise, it uses the implicit token flow ('token').

        Returns:
            str: A formatted authentication URL with encoded parameters.
        """
        auth_params = {
            'client_id': cls.CLIENT_ID,
            'response_type': 'code' if auth_code else 'token'
        }
        encoded_params = urllib.parse.urlencode(auth_params)
        auth_url = f"{cls.AUTH_URL}?{encoded_params}"

        return auth_url

    @classmethod
    @log_on_start(logging.INFO, "Starting AniList auth server...")
    @log_on_error(logging.ERROR, "AniList auth server failed: {error!r}",
                  sanitize_params={"client_secret", "code"})
    def start_auth_server(cls, code_callback: Callable[[str], None]) -> threading.Thread:
        """
        Starts a local server to listen for the OAuth callback and extract the authorization code.

        Parameters:
            code_callback: Callable[[str], None]
                A callback function that takes the authorization code as an argument.

        Returns:
            threading.Thread:
                The thread on which the local server is running.

        Raises:
            ServerRunningError:
                If an instance of the server is already running or if the local server fails to start.
            ClientSecretNotProvidedError:
                If the CLIENT_SECRET is not set, which is necessary for the Authorization Code Grant.
            ServerFailedToStartError:
                If the local server fails to start.
        """

        with cls._server_lock:
            if cls._server_instance:
                raise ServerRunningError("An instance of the server is already running")

            if not cls.CLIENT_SECRET:
                raise ClientSecretNotProvidedError("Client Secret not provided. Cannot use Authorization Code Grant.")

            server_error = None
            server_started = threading.Event()

            def run_server():
                try:
                    parsed_uri = urlparse(cls.REDIRECT_URI)
                    server_address = (parsed_uri.hostname, parsed_uri.port)
                    httpd = HTTPServer(server_address, cls._make_handler(code_callback))
                    cls._server_instance = httpd
                    server_started.set()
                    httpd.serve_forever()
                except Exception as e:
                    nonlocal server_error
                    server_error = e
                finally:
                    cls._server_instance = None

            server_thread = threading.Thread(target=run_server, daemon=False)
            server_thread.start()

            if not server_started.wait(timeout=5):
                if server_error:
                    raise ServerFailedToStartError(f"Failed to start the local server: {server_error}")
                else:
                    raise ServerFailedToStartError("Failed to start the local server due to an unknown error.")
            return server_thread

    @classmethod
    def shutdown_auth_server(cls):
        """
        Shuts down the authentication server in a thread-safe manner.

        This method safely shuts down the HTTP server used for authentication. It checks if the server instance is
        an HTTPServer and then initiates its shutdown in a separate thread to prevent deadlocks. The server is then
        closed, and the instance is set to None.

        Note:
            This method assumes that the server is an instance of HTTPServer or None. It uses threading to avoid
            deadlocks that may occur due to waiting for the server to shut down.

        """
        with cls._server_lock:
            if isinstance(cls._server_instance, HTTPServer):
                # Don't wait for the server to shut down, just set the instance to None
                # Otherwise it will cause a deadlock
                threading.Thread(target=cls._server_instance.shutdown).start()
                cls._server_instance.server_close()
                cls._server_instance = None

    @classmethod
    def _make_handler(cls, code_callback: Callable[[str], None]):
        """
        Creates a factory for request handlers to process OAuth authentication callbacks.

        This method generates a factory function that returns a custom HTTP request handler.
        The handler is designed to intercept GET requests, extract an authorization code
        from the query parameters, and execute a callback function with this code.

        Parameters:
            code_callback (Callable[[str], None]): A callback function that takes the
                                                   authorization code as an argument.

        Returns:
            A factory function that produces a RequestHandler instance when called
            with a request, client address, and server instance.
        """

        def handler_factory(request: socket, client_address: Tuple[str, int], server: HTTPServer):
            class RequestHandler(BaseHTTPRequestHandler):
                def do_GET(self):  # noqa
                    # Parse the query string for the authorization code
                    query = urlparse(self.path).query
                    params = parse_qs(query)
                    code = params.get('code', [None])[0]

                    if code:
                        code_callback(code)

                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html')
                    self.end_headers()
                    self.wfile.write("Authentication successful. You may now close this window.".encode('utf-8'))

                    threading.Thread(target=self.server.shutdown).start()

            return RequestHandler(request, client_address, server)

        return handler_factory

    @classmethod
    @log_on_error(logging.ERROR, "Failed to fetch AniList token: {error!r}",
                  sanitize_params={"code", "client_secret"})
    def fetch_token(cls, code: str) -> TokenResponse:
        """
        Exchanges the authorization code for an access token.

        HTTPRequestError:
            If the request to fetch the token fails.
        """
        token_params = {
            'client_id': cls.CLIENT_ID,
            'client_secret': cls.CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'redirect_uri': cls.REDIRECT_URI,
            'code': code
        }
        response = _anilist_session.request("POST", cls.TOKEN_URL, fields=token_params)
        if response.status != 200:
            raise HTTPRequestError(response)

        return response.json()


atexit.register(AnilistAuthClient.shutdown_auth_server)


class AnilistClient:
    QUERY_URL = 'https://graphql.anilist.co'

    _get_user_view = '''
    {
        Viewer {
            id
            name
            avatar {
                large
                medium
            }
            bannerImage
            options {
                titleLanguage
                displayAdultContent
            }
            mediaListOptions {
                scoreFormat
                rowOrder
                animeList {
                    sectionOrder
                    splitCompletedSectionByFormat
                    customLists
                    advancedScoring
                    advancedScoringEnabled
                }
                mangaList {
                    sectionOrder
                    splitCompletedSectionByFormat
                    customLists
                    advancedScoring
                    advancedScoringEnabled
                }
            }
        }
    }
    '''.strip()

    _get_user_media_list = f'''
    query ($id: Int, $type: MediaType) {{
      MediaListCollection(userId: $id, type: $type) {{
        lists {{
          entries {{
            ...{QueryNames.MediaListFragmentName.value}
          }}
        }}
      }}
    }}
    {AnilistUserEntry.fragment()}
    '''.strip()

    _delete_media_entry = f'''
    mutation ($id: Int) {{
        DeleteMediaListEntry(id: $id) {{
            deleted
        }}
    }}
    '''.strip()

    _get_media_entry = f'''
    query ($ids: [Int], $page: Int, $perPage: Int, $season: MediaSeason, $seasonYear: Int) {{
        Page(page: $page, perPage: $perPage) {{
            pageInfo {{
                total
                currentPage
                perPage
                hasNextPage
            }}
            media(id_in: $ids, season: $season, seasonYear: $seasonYear) {{
                ...{QueryNames.MediaFragmentName.value}
            }}
        }}
    }}
    {AnilistMedia.fragment()}
    '''.strip()

    _save_media_list_entries = f'''
    mutation (
        $id: Int, 
        $status: MediaListStatus, 
        $score: Float, 
        $scoreRaw: Int, 
        $progress: Int, 
        $progressVolumes: Int, 
        $repeat: Int, 
        $priority: Int,
        $private: Boolean,
        $notes: String,
        $hiddenFromStatusLists: Boolean,
        #customLists: [String],
        $advancedScores: [Float],
        $startedAt: FuzzyDateInput, 
        $completedAt: FuzzyDateInput
        ) {{
        SaveMediaListEntry(
            id: $id, 
            status: $status,
            score: $score,
            scoreRaw: $scoreRaw,
            progress: $progress,
            progressVolumes: $progressVolumes,
            repeat: $repeat,
            priority: $priority,
            private: $private,
            notes: $notes,
            hiddenFromStatusLists: $hiddenFromStatusLists,
            #customLists: $customLists,
            advancedScores: $advancedScores,
            startedAt: $startedAt,
            completedAt: $completedAt
            ) {{
            ...{QueryNames.MediaListFragmentName.value}
        }}
    }}
    {AnilistUserEntry.fragment()}
    '''.strip()

    _update_media_list_entries = f'''
    mutation (
        $ids: [Int], 
        $status: MediaListStatus, 
        $score: Float, 
        $scoreRaw: Int, 
        $progress: Int, 
        $progressVolumes: Int, 
        $repeat: Int, 
        $priority: Int,
        $private: Boolean,
        $notes: String,
        $hiddenFromStatusLists: Boolean,
        $advancedScores: [Float],
        $startedAt: FuzzyDateInput, 
        $completedAt: FuzzyDateInput
        ) {{
        UpdateMediaListEntries(
            ids: $ids, 
            status: $status,
            score: $score,
            scoreRaw: $scoreRaw,
            progress: $progress,
            progressVolumes: $progressVolumes,
            repeat: $repeat,
            priority: $priority,
            private: $private,
            notes: $notes,
            hiddenFromStatusLists: $hiddenFromStatusLists,
            advancedScores: $advancedScores,
            startedAt: $startedAt,
            completedAt: $completedAt
            ) {{
            ...{QueryNames.MediaListFragmentName.value}
        }}
    }}
    {AnilistUserEntry.fragment()}
    '''.strip()

    @classmethod
    def _categorize_entries(cls, entries: List[Type[AnilistUserEntry]]) -> Tuple[
        Dict[str, List[Type[AnilistUserEntry]]],
        List[Type[AnilistUserEntry]]
    ]:
        """
        Categorizes a list of AnilistUserEntry objects into groups for bulk updating and identifies deleted entries.

        This method iterates over the given list of entries. If an entry is marked as deleted,
        it is added to the list of deleted entries. Otherwise, it is categorized into a group
        for bulk update based on the fields that were updated. The grouping is done using a
        frozenset of the updated fields and their values.

        Parameters:
            entries (List[Type[AnilistUserEntry]]): A list of AnilistUserEntry objects to be categorized.

        Returns:
            Tuple[Dict[frozenset, List[Type[AnilistUserEntry]]], List[Type[AnilistUserEntry]]]:
            A tuple containing a dictionary for bulk update groups and a list of deleted entries.
            The dictionary's keys are stringifies of updated field items, and values are lists of entries.
            The second element of the tuple is a list of entries marked as deleted.
        """

        bulk_update_groups = defaultdict(list)
        deleted_entries = []

        for entry in entries:
            if entry.is_deleted:
                deleted_entries.append(entry)
                continue

            update_key = json.dumps(sort_dict(entry.updated_fields), sort_keys=True)
            bulk_update_groups[update_key].append(entry)

        return bulk_update_groups, deleted_entries

    @classmethod
    def _delete_entry(cls, access_token: str, entry_id: int) -> bool:
        """
        Class method to delete a media list entry on Anilist.

        Sends a GraphQL request to Anilist to delete a specific media list entry
        identified by 'entry_id'. Utilize the provided 'access_token' for
        authentication.

        Parameters:
            access_token (str): The access token for authenticating the GraphQL request.
            entry_id (int): The unique identifier of the media list entry to be deleted.

        Returns:
            bool: True if the deletion was successful, otherwise an exception is raised.

        Raises:
            AnilistUserNoMediaCollectionError: If the deletion fails due to reasons like
                                               the entry not existing or issues with the
                                               request.


        """
        response = cls._send_graphql_request(access_token, cls._delete_media_entry, {
            'id': entry_id
        })
        if (not response.get("data") or
                not response["data"].get("DeleteMediaListEntry") or
                not response["data"]["DeleteMediaListEntry"].get("deleted")):
            raise AnilistUserNoMediaCollectionError("Failed to delete user media list entry.")
        return response["data"]["DeleteMediaListEntry"]["deleted"]

    @classmethod
    def _ensure_access_token(cls, session: Session, token_data: TransformedTokenResponse):
        """
        Ensures that a valid access token is available for the AnilistClient.

        This method checks if the current token data is valid. If not, it attempts to
        refresh the token using a refresh token present in the token data. The new token
        is then saved and updated in the session.

        Parameters:
            session (Session): The session object where the new token will be saved if refreshed.
            token_data (dict): A dictionary containing the current token information.

        Returns:
            str: A valid access token.

        Raises:
            AnilistNoRefreshUserError: If the refresh token is not found in the token_data,
                                       indicating that the token cannot be refreshed.
            HTTPRequestError:
                If the request to fetch the token fails.
                If the response status code is not 200, indicating a failed request.
            AnilistUserNotFoundError: If the request fails or the user data is not found
                                      in the response.

        """
        if not cls._validate_token_data(token_data):
            refresh_token = token_data.get("refresh_token")
            if not refresh_token:
                raise AnilistNoRefreshUserError("Refresh token not found.")

            token = AnilistAuthClient.fetch_token(refresh_token)
            creds = cls.save_token(session, token)
            token_data = cast(AnilistCredsInfo, creds.additional_info).get("token_data")

        return token_data.get('access_token')

    @classmethod
    def _fetch_entries_to_update(cls, session: Session, user_id: str) -> list[Type[AnilistUserEntry]]:
        """
        Retrieves a list of AnilistUserEntry objects that require updating.

        This method queries the database for all entries associated with the given user_id
        where the local_updated_at timestamp is greater than the updated_at timestamp,
        indicating that the local entry is more recent and needs to be updated.

        Parameters:
            session (Session): The SQLAlchemy session to be used for the database query.
            user_id (str): The user ID to filter the entries.

        Returns:
            List[Type[AnilistUserEntry]]: A list of AnilistUserEntry instances that need to be updated.
        """
        return session.query(AnilistUserEntry).filter_by(
            user_id=user_id).where(
            gt(AnilistUserEntry.local_updated_at, AnilistUserEntry.updated_at)
        ).all()

    @classmethod
    def _get_token_data(cls, creds: ServiceCreds):
        """
        Retrieves the token data from the provided ServiceCreds object.

        This method extracts and returns the token data stored within the 'additional_info'
        field of a ServiceCreds object. The token data is expected to be an instance of
        AnilistCredsInfo.

        Parameters:
            creds (ServiceCreds): The ServiceCreds object containing the Anilist credentials
                                  and additional token information.

        Returns:
            dict: A dictionary containing the token data.

        Raises:
            AnilistNoUserError: If the token data is not found in the provided ServiceCreds
                                object.
        """
        token_data = cast(AnilistCredsInfo, creds.additional_info).get("token_data")
        if not token_data:
            raise AnilistNoUserError("Token data not found.")
        return token_data

    @classmethod
    def _get_user_data(cls, access_token: str):
        """
        Retrieves the user data from Anilist using the provided access token.

        Sends a GraphQL request to Anilist's API to fetch the 'Viewer' data,
        which contains the information of the currently authenticated user.

        Parameters:
            access_token (str): The access token used to authenticate the GraphQL request.

        Returns:
            dict: A dictionary containing the user's data if the request is successful.

        Raises:
            AnilistUserNotFoundError: If the request fails or the user data is not found
                                      in the response.
            HTTPRequestError: If the response status code is not 200, indicating a failed request.
        """
        response = cls._send_graphql_request(access_token, cls._get_user_view, {})
        if not response.get("data") or not response["data"].get("Viewer"):
            raise AnilistUserNotFoundError("Failed to fetch user data.")
        return response["data"]["Viewer"]

    @classmethod
    def _process_bulk_updates(cls, session: Session,
                              bulk_update_groups: Dict[str, List[Type[AnilistUserEntry]]],
                              access_token: str):
        """
         Processes bulk updates of Anilist user entries.

         This method iterates over groups of updates, deciding whether to process
         each as individual updates or as bulk updates based on specific criteria.
         It updates both the remote entries on Anilist and the local database entries.

         Parameters:
             session (Session): The session for the local database operations.
             bulk_update_groups (Dict[str, List[Type[AnilistUserEntry]]]):
                 A dictionary mapping update keys to lists of AnilistUserEntry objects.
             access_token (str): The access token used for authenticating the update requests.

        Raises:
            AnilistUserNoMediaCollectionError: If the update operation fails or the response does not contain
                                               the expected data.
            HTTPRequestError: If the response status code is not 200, indicating a failed request.
         """
        for update_key, entries in bulk_update_groups.items():
            if len(entries) == 1:
                response = cls._update_individual_entry(access_token, update_key, entries[0].id)
                cls._update_local_entry(session, entries[0], response)
            elif "customLists" in update_key:
                for entry in entries:
                    response = cls._update_individual_entry(access_token, update_key, entry.id)
                    cls._update_local_entry(session, entry, response)
            else:
                response = cls._update_bulk_entries(access_token, update_key, [e.id for e in entries])
                for entry in entries:
                    response_entry = next((r for r in response if r['id'] == entry.id), None)
                    cls._update_local_entry(session, entry, response_entry)

    @classmethod
    def _process_deleted_entries(cls, session: Session,
                                 deleted_entries: List[Type[AnilistUserEntry]],
                                 access_token: str):
        """
        Processes and removes deleted entries from both Anilist and the local database.

        This method iterates over a list of AnilistUserEntry objects that are marked for
        deletion. Each entry is deleted from Anilist using its ID and the provided access
        token. If the deletion on Anilist is successful, the corresponding entry is also
        removed from the local database session.

        Parameters:
            session (Session): The session for the local database operations.
            deleted_entries (List[Type[AnilistUserEntry]]): A list of AnilistUserEntry objects
                                                            to be deleted.
            access_token (str): The access token used for authenticating the deletion requests.
        Raises:
            AnilistUserNoMediaCollectionError: If the deletion fails due to reasons like
                                               the entry not existing or issues with the
                                               request.
        """
        for entry in deleted_entries:
            if cls._delete_entry(access_token, entry.id):
                session.delete(entry)

    @classmethod
    def _update_local_entry(cls, session, entry_data, entry: DefaultUserEntryFields):
        """
        Updates a local database entry with the new data from Anilist.

        This method synchronizes a local entry with its updated version on Anilist.
        It updates various fields of the local entry, including the 'updated_at'
        timestamp, and resets the 'is_deleted' flag and 'updated_fields' dictionary.
        The updated entry data is then merged into the current database session.

        Parameters:
            session (Session): The session associated with the local database.
            entry_data: The local database entry to be updated.
            entry (DefaultUserEntryFields): The updated entry data from Anilist.
        """
        updated_at = entry["updatedAt"]

        entry_data.updated_at = updated_at
        entry_data.local_updated_at = updated_at
        entry_data.is_deleted = False
        entry_data.updated_fields = {}
        session.merge(entry_data)

    @classmethod
    def _save_token_data(cls, session: Session, user_id: str, combined_data: AnilistCredsInfo):
        """
        Saves or updates Anilist token data in the local database for a specific user.

        This method creates a new ServiceCreds object with the user's ID, the service name
        (Anilist), and the token data. It then merges this new object with the existing data
        in the database session. If an entry for the user already exists, it is updated;
        otherwise, a new entry is created.

        Parameters:
            session (Session): The session for the local database operations.
            user_id (str): The user's identifier.
            combined_data (AnilistCredsInfo): The token data to be saved.

        Returns:
            ServiceCreds: The saved or updated ServiceCreds object in the database.
        """
        new_creds = ServiceCreds(
            identifier=user_id,
            service_name=ServiceName.ANILIST,
            additional_info=combined_data
        )

        existing_creds = session.merge(new_creds)

        return existing_creds

    @classmethod
    @log_on_error(logging.ERROR, "GraphQL request failed: {error!r}",
                  sanitize_params={"access_token"})
    def _send_graphql_request(cls, access_token: str, query: str, variables: dict):
        """
        Sends a GraphQL request to the Anilist API.

        This method prepares and sends a POST request to Anilist's GraphQL endpoint
        with the specified query and variables. It includes an authorization header
        if an access token is provided.

        Parameters:
            access_token (str): The access token for authenticating the request.
            query (str): The GraphQL query string.
            variables (dict): A dictionary of variables required for the query.

        Returns:
            dict: The JSON response from the Anilist API.

        Raises:
            HTTPRequestError: If the response status code is not 200, indicating a failed request.
        """
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            **({'Authorization': f"Bearer {access_token}"} if access_token else {})
        }

        payload = {
            'query': query,
            'variables': variables
        }
        response = _anilist_session.request("POST", cls.QUERY_URL, headers=headers, body=json.dumps(payload))

        if response.status != 200:
            raise HTTPRequestError(response)

        return response.json()

    @staticmethod
    def _transform_token_data(token_data: TokenResponse) -> TransformedTokenResponse:
        """
        Transforms raw token data into a more structured and usable format.

        This method calculates the expiration time of the access token and structures
        the token data, including access and refresh tokens, token type, and the
        calculated expiration timestamp.

        Parameters:
            token_data (TokenResponse): The raw token data received from the authentication service.

        Returns:
            TransformedTokenResponse: A dictionary with structured and additional token information.

        The method enhances the token data usability by providing a clear expiration
        timestamp and organizing the data into a consistent format.
        """
        expired_in = token_data.get('expires_in', 0)
        # Subtract 1 minute from the expiration time to account for latency, and make sure we always have a valid token
        expired_at = datetime.now() + timedelta(seconds=expired_in) - timedelta(minutes=1) if expired_in else None
        return {
            'access_token': token_data.get('access_token'),
            'refresh_token': token_data.get('refresh_token'),
            'token_type': token_data.get('token_type'),
            'expired_at': expired_at.timestamp()
        }

    @classmethod
    def _update_bulk_entries(cls,
                             access_token: str,
                             entry_data: str,
                             entry_ids: list[int]) -> List[DefaultUserEntryFields]:
        """
        Updates multiple Anilist user entries in a single bulk operation.

        This method sends a GraphQL request to update a batch of media list entries on Anilist.
        It combines the provided entry data with the list of entry IDs to form the GraphQL
        variables. If the update is unsuccessful, it raises an exception.

        Parameters:
            access_token (str): The access token for authenticating the request.
            entry_data (str): A set of tuples representing the entry data to be updated.
            entry_ids (list[int]): A list of entry IDs to be updated.

        Returns:
            List[DefaultUserEntryFields]: A list containing the updated entry fields.

        Raises:
            AnilistUserNoMediaCollectionError: If the update operation fails or the response does not contain
                                               the expected data.
            HTTPRequestError: If the response status code is not 200, indicating a failed request.
        """
        variables = json.loads(entry_data)
        variables['ids'] = entry_ids

        response = cls._send_graphql_request(access_token, cls._update_media_list_entries, variables)
        if not response.get("data") or not response["data"].get("UpdateMediaListEntries"):
            raise AnilistUserNoMediaCollectionError("Failed to update user media list.")
        return response["data"]["UpdateMediaListEntries"]

    @classmethod
    def _update_individual_entry(cls, access_token: str, update_key: str,
                                 entry_id: int) -> DefaultUserEntryFields:

        """
        Updates a single Anilist user entry.

        This method constructs the variables for a GraphQL request to update a specific
        media list entry on Anilist. It combines the provided update key with the entry ID,
        then sends a request. If the update is unsuccessful, it raises an exception.

        Parameters:
            access_token (str): The access token for authenticating the request.
            update_key (str): A set of tuples representing the data to be updated.
            entry_id (int): The ID of the entry to be updated.

        Returns:
            DefaultUserEntryFields: The updated entry fields from Anilist.

        Raises:
            AnilistUserNoMediaCollectionError: If the update operation fails or the response does not contain
                                               the expected data.
            HTTPRequestError: If the response status code is not 200, indicating a failed request.
        """
        # This need to be calculated at runtime!
        variables = json.loads(update_key)
        variables['id'] = entry_id

        response = cls._send_graphql_request(access_token, cls._save_media_list_entries, variables)
        if not response.get("data") or not response["data"].get("SaveMediaListEntry"):
            raise AnilistUserNoMediaCollectionError("Failed to update user media list.")
        return response["data"]["SaveMediaListEntry"]

    @classmethod
    def _validate_token_data(cls, token_data: TransformedTokenResponse):
        """
        Validates the token data by checking if the token has expired.

        This method examines the 'expired_at' field in the token data to determine
        if the current time is before the expiration time. It returns True if the
        token is still valid (i.e., not expired), and False otherwise.

        Parameters:
            token_data (TransformedTokenResponse): A dictionary containing the transformed
                                                   token data, including the expiration timestamp.

        Returns:
            bool: True if the token is valid (not expired), False otherwise.
        """
        expired_at = token_data.get('expired_at')
        if expired_at:
            try:
                return datetime.now() < datetime.fromtimestamp(expired_at)
            except ValueError:
                return False

        return False

    @classmethod
    @log_on_start(logging.INFO, "Starting AniList user authentication...")
    @log_on_error(logging.ERROR, "AniList authentication failed: {error!r}",
                  sanitize_params={"access_token", "code"})
    def authenticate_user(cls, auth_url: str) -> Tuple[threading.Thread, TokenContainer]:
        """
        Initiates the user authentication process for Anilist.

        This method starts a server thread to handle the OAuth callback and opens the
        authentication URL in the user's web browser. It uses a TokenContainer object
        to store the token once it's received from the callback.

        Parameters:
            auth_url (str): The URL for the Anilist OAuth authentication page.

        Returns:
            Tuple[threading.Thread, TokenContainer]: A tuple containing the server thread and
                                                     the TokenContainer object.

        Raises:
            HTTPRequestError:
                If the request to fetch the token fails.
            ServerRunningError:
                If an instance of the server is already running or if the local server fails to start.
            ClientSecretNotProvidedError:
                If the CLIENT_SECRET is not set, which is necessary for the Authorization Code Grant.
            ServerFailedToStartError:
                If the local server fails to start.
        """
        token_container = TokenContainer()

        def callback(code):
            token_container.token = AnilistAuthClient.fetch_token(code)

        server_thread = AnilistAuthClient.start_auth_server(callback)
        webbrowser.open(auth_url)

        return server_thread, token_container

    @classmethod
    def fetch_media_entry(cls, media_ids: List[int] = None,
                          season: AnilistMediaSeason = None,
                          year: int = None,
                          *,
                          page: int = 1,
                          per_page: int = 50) -> Tuple[PageInfo, List[DefaultMediaFields]]:
        """
        Fetches media entries from Anilist based on specified criteria.

        This method allows the retrieval of media entries from Anilist by IDs, season,
        year, and pagination options. It constructs the query parameters based on the
        provided arguments and sends a GraphQL request.

        Parameters:
            media_ids (List[int], optional): A list of media IDs to filter the entries.
            season (AnilistMediaSeason, optional): The season to filter the entries.
            year (int, optional): The year to filter the entries.
            page (int, default=1): The page number for pagination.
            per_page (int, default=50): The number of entries per page.

        Returns:
            Tuple[PageInfo, List[DefaultMediaFields]]: A tuple containing page information and
                                                       a list of media entries.

        Raises:
            HTTPRequestError:
                If the response status code is not 200, indicating a failed request.
            AnilistMediaNotFound:
                If the media entries could not be fetched.
        """
        query_params = {
            'page': page,
            'perPage': per_page
        }
        if media_ids:
            query_params['ids'] = media_ids
        if season:
            query_params['season'] = season
        if year:
            query_params['seasonYear'] = year

        response = cls._send_graphql_request("", cls._get_media_entry, query_params)

        if response.get("data") and response["data"].get("Page"):
            page_info = response["data"]["Page"]["pageInfo"]
            media = response["data"]["Page"]["media"]
            return page_info, media
        else:
            raise AnilistMediaNotFoundError("Failed to fetch media entry.")

    @classmethod
    def fetch_user_media_list(cls,
                              session: Session,
                              access_token: str,
                              user_id: str,
                              media_type: AnilistMediaType) -> List[Tuple[AnilistUserEntry, Type[AnilistUserEntry]]]:
        """
        Fetches a user's media list from Anilist and updates the local database.

        This method sends a GraphQL request to Anilist to retrieve a user's media list
        based on the specified media type. It then updates the local database with this
        information, identifying any conflicts between the remote and local data.

        Parameters:
            session (Session): The database session used for querying and updating records.
            access_token (str): The access token for authenticating the request.
            user_id (str): The Anilist user ID.
            media_type (AnilistMediaType): The type of media to retrieve (e.g., ANIME, MANGA).

        Returns:
            List[Tuple[AnilistUserEntry, Type[AnilistUserEntry]]]: A list of tuples representing
                                                                   conflicts between fetched
                                                                   and existing records.

        Raises:
            HTTPRequestError:
                If the response status code is not 200, indicating a failed request.
            AnilistUserNoMediaCollectionError:
                If the media list could not be fetched.
        """
        data = cls._send_graphql_request(access_token, cls._get_user_media_list, {
            "id": int(user_id),
            "type": media_type.value
        })

        if (not data.get('data') or
                not data['data'].get('MediaListCollection') or
                not data['data']['MediaListCollection'].get('lists')):
            raise AnilistUserNoMediaCollectionError("Failed to fetch user media list.")

        ids = set()
        flatten_data = []

        for lists in data.get('data', {}).get('MediaListCollection', {}).get('lists', []):
            for entry in lists.get('entries', []):
                parsed_entry = AnilistUserEntry.parse_data(entry)
                flatten_data.append(parsed_entry)
                ids.add(parsed_entry.id)

        existing_records = session.query(AnilistUserEntry).filter(AnilistUserEntry.id.in_(ids)).all()  # noqa
        existing_records_dict = {record.id: record for record in existing_records}

        conflicts = []

        for row in flatten_data:
            existing_record: Type[AnilistUserEntry] = existing_records_dict.get(row.id)
            if existing_record:
                if existing_record.updated_at != existing_record.local_updated_at or existing_record.is_deleted:
                    conflicts.append((row, existing_record))
                else:
                    session.merge(row)
            else:
                session.add(row)

        return conflicts

    @classmethod
    def refresh_user(cls,
                     session: Session,
                     creds: ServiceCreds) -> List[Tuple[AnilistUserEntry, Type[AnilistUserEntry]]]:
        """
        Refreshes the Anilist data for a user.

        This method first checks the validity of the provided credentials and token data.
        If the token is valid, it fetches the user's data and their media list. If the token
        is invalid but a refresh token is available, it refreshes the token and then proceeds
        to fetch the user's data and media list. In case of missing or invalid credentials,
        appropriate errors are raised.

        Parameters:
            session (Session): The database session for operations.
            creds (ServiceCreds): Credentials of the user.

        Returns:
            List[Tuple[AnilistUserEntry, Type[AnilistUserEntry]]]: A list of tuples representing
                                                                   conflicts between fetched
                                                                   and existing records.

        Raises:
            HTTPRequestError:
                If the request to fetch the token fails.
                If the response status code is not 200, indicating a failed request.
            AnilistUserNotFoundError:
                If credentials are not found or invalid.
            AnilistNoUserError:
                If token data is not found.
            AnilistNoRefreshUserError:
                If the refresh token is not available.
            AnilistUserNoMediaCollectionError:
                If the media list could not be fetched.
        """
        if not creds:
            raise AnilistUserNotFoundError("Credentials not found.")
        if creds.service_name != ServiceName.ANILIST:
            raise AnilistUserNotFoundError("Invalid service name.")

        token_data = cast(AnilistCredsInfo, creds.additional_info).get("token_data")
        if not token_data:
            raise AnilistNoUserError("Token data not found.")

        if cls._validate_token_data(token_data):
            user_data = cls._get_user_data(token_data.get('access_token'))
            if user_data:
                combined_data: AnilistCredsInfo = {'token_data': token_data, 'user_data': user_data}
                cls._save_token_data(session, str(user_data['id']), combined_data)
            anime = cls.fetch_user_media_list(session, token_data.get('access_token'), creds.identifier,
                                              AnilistMediaType.ANIME)
            return anime
        elif token_data.get("refresh_token"):
            token = AnilistAuthClient.fetch_token(token_data.get("refresh_token"))
            cls.save_token(session, token)
            anime = cls.fetch_user_media_list(session, token_data.get('access_token'), creds.identifier,
                                              AnilistMediaType.ANIME)
            return anime

        raise AnilistNoRefreshUserError("Refresh token not found.")

    @classmethod
    @log_on_error(logging.ERROR, "Failed to save AniList token: {error!r}",
                  sanitize_params={"token_data"})
    def save_token(cls, session: Session, token_data: TokenResponse) -> Union[ServiceCreds, None]:
        """
        Saves the transformed token data along with user data in the local database.

        This method normalizes the raw token response, fetches the user data using the
        access token, and then saves this combined information in the local database.
        If the access token or user data is not retrievable, it logs an error.

        Parameters:
            session (Session): The database session for saving the token data.
            token_data (TokenResponse): The raw token data received from the authentication service.

        Returns:
            Union[ServiceCreds, None]: The saved ServiceCreds object or None if saving fails.

        Raises:
            AnilistUserNotFoundError: If the request fails or the user data is not found
                                      in the response.
            HTTPRequestError: If the response status code is not 200, indicating a failed request.
        """
        normalized_token = cls._transform_token_data(token_data)
        access_token = normalized_token.get('access_token')
        if access_token:
            user_data = cls._get_user_data(access_token)
            if user_data:
                combined_data: AnilistCredsInfo = {'token_data': normalized_token, 'user_data': user_data}
                return cls._save_token_data(session, str(user_data['id']), combined_data)
            else:
                logging.error("Failed to fetch user data.")
        else:
            logging.error("Access token not found in token data.")

    @classmethod
    def submit_user_media_list(cls, session: Session, creds: ServiceCreds):
        """
        Submits updates to a user's media list to Anilist and processes any deletions.

        This method ensures that changes made locally to a user's media list are
        synchronized with Anilist. It fetches entries to be updated, categorizes them
        into bulk updates and deletions, and then processes these updates and deletions
        using the user's access token.

        Note:
            Make sure the entry are most up to date before calling this method.
            and resolve any conflicts before calling this method.
        Parameters:
            session (Session): The database session for querying and updating records.
            creds (ServiceCreds): Credentials of the user.

        Raises:
            AnilistUserNotFoundError:
                If the credentials do not belong to Anilist service.
                If the request fails or the user data is not found in the response.
            AnilistNoUserError:
                If the token data is not found in the provided ServiceCreds object.
            AnilistNoRefreshUserError:
                If the refresh token is not found in the token_data, indicating that the token cannot be refreshed.
            AnilistUserNoMediaCollectionError:
                If the deletion fails due to reasons like the entry not existing or issues with the request.
                If the update operation fails or the response does not contain the expected data.
            HTTPRequestError:
                If the request to fetch the token fails.
                If the response status code is not 200, indicating a failed request.

        """
        if creds.service_name != ServiceName.ANILIST:
            raise AnilistUserNotFoundError("Invalid service name.")

        entries = cls._fetch_entries_to_update(session, creds.identifier)
        if not entries:
            return

        bulk_update_groups, deleted_entries = cls._categorize_entries(entries)

        token_data = cls._get_token_data(creds)
        access_token = cls._ensure_access_token(session, token_data)

        cls._process_deleted_entries(session, deleted_entries, access_token)
        cls._process_bulk_updates(session, bulk_update_groups, access_token)
