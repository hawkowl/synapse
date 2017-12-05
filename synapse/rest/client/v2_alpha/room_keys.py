# -*- coding: utf-8 -*-
# Copyright 2017 New Vector Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging

from twisted.internet import defer

from synapse.http.servlet import (
    RestServlet, parse_json_object_from_request
)
from ._base import client_v2_patterns

logger = logging.getLogger(__name__)


class RoomKeysServlet(RestServlet):
    PATTERNS = client_v2_patterns(
        "/room_keys/keys(/(?P<room_id>[^/]+))?(/(?P<session_id>[^/]+))?$"
    )

    def __init__(self, hs):
        """
        Args:
            hs (synapse.server.HomeServer): server
        """
        super(RoomKeysServlet, self).__init__()
        self.auth = hs.get_auth()
        self.e2e_room_keys_handler = hs.get_e2e_room_keys_handler()

    @defer.inlineCallbacks
    def on_PUT(self, request, room_id, session_id):
        """
        Uploads one or more encrypted E2E room keys for backup purposes.
        room_id: the ID of the room the keys are for (optional)
        session_id: the ID for the E2E room keys for the room (optional)
        version: the version of the user's backup which this data is for.
        the version must already have been created via the /change_secret API.

        Each session has:
         * first_message_index: a numeric index indicating the oldest message
           encrypted by this session.
         * forwarded_count: how many times the uploading client claims this key
           has been shared (forwarded)
         * is_verified: whether the client that uploaded the keys claims they
           were sent by a device which they've verified
         * session_data: base64-encrypted data describing the session.

        Returns 200 OK on success with body {}

        The API is designed to be otherwise agnostic to the room_key encryption
        algorithm being used.  Sessions are merged with existing ones in the
        backup using the heuristics:
         * is_verified sessions always win over unverified sessions
         * older first_message_index always win over newer sessions
         * lower forwarded_count always wins over higher forwarded_count

        We trust the clients not to lie and corrupt their own backups.

        POST /room_keys/keys/!abc:matrix.org/c0ff33?version=1 HTTP/1.1
        Content-Type: application/json

        {
            "first_message_index": 1,
            "forwarded_count": 1,
            "is_verified": false,
            "session_data": "SSBBTSBBIEZJU0gK"
        }

        Or...

        POST /room_keys/keys/!abc:matrix.org?version=1 HTTP/1.1
        Content-Type: application/json

        {
            "sessions": {
                "c0ff33": {
                    "first_message_index": 1,
                    "forwarded_count": 1,
                    "is_verified": false,
                    "session_data": "SSBBTSBBIEZJU0gK"
                }
            }
        }

        Or...

        POST /room_keys/keys?version=1 HTTP/1.1
        Content-Type: application/json

        {
            "rooms": {
                "!abc:matrix.org": {
                    "sessions": {
                        "c0ff33": {
                            "first_message_index": 1,
                            "forwarded_count": 1,
                            "is_verified": false,
                            "session_data": "SSBBTSBBIEZJU0gK"
                        }
                    }
                }
            }
        }
        """
        requester = yield self.auth.get_user_by_req(request, allow_guest=False)
        user_id = requester.user.to_string()
        body = parse_json_object_from_request(request)
        version = request.args.get("version")[0]

        if session_id:
            body = {
                "sessions": {
                    session_id: body
                }
            }

        if room_id:
            body = {
                "rooms": {
                    room_id: body
                }
            }

        yield self.e2e_room_keys_handler.upload_room_keys(
            user_id, version, body
        )
        defer.returnValue((200, {}))

    @defer.inlineCallbacks
    def on_GET(self, request, room_id, session_id):
        """
        Retrieves one or more encrypted E2E room keys for backup purposes.
        Symmetric with the PUT version of the API.

        room_id: the ID of the room to retrieve the keys for (optional)
        session_id: the ID for the E2E room keys to retrieve the keys for (optional)
        version: the version of the user's backup which this data is for.
        the version must already have been created via the /change_secret API.

        Returns as follows:

        GET /room_keys/keys/!abc:matrix.org/c0ff33?version=1 HTTP/1.1
        {
            "first_message_index": 1,
            "forwarded_count": 1,
            "is_verified": false,
            "session_data": "SSBBTSBBIEZJU0gK"
        }

        Or...

        GET /room_keys/keys/!abc:matrix.org?version=1 HTTP/1.1
        {
            "sessions": {
                "c0ff33": {
                    "first_message_index": 1,
                    "forwarded_count": 1,
                    "is_verified": false,
                    "session_data": "SSBBTSBBIEZJU0gK"
                }
            }
        }

        Or...

        GET /room_keys/keys?version=1 HTTP/1.1
        {
            "rooms": {
                "!abc:matrix.org": {
                    "sessions": {
                        "c0ff33": {
                            "first_message_index": 1,
                            "forwarded_count": 1,
                            "is_verified": false,
                            "session_data": "SSBBTSBBIEZJU0gK"
                        }
                    }
                }
            }
        }
        """
        requester = yield self.auth.get_user_by_req(request, allow_guest=False)
        user_id = requester.user.to_string()
        version = request.args.get("version")[0]

        room_keys = yield self.e2e_room_keys_handler.get_room_keys(
            user_id, version, room_id, session_id
        )
        defer.returnValue((200, room_keys))

    @defer.inlineCallbacks
    def on_DELETE(self, request, room_id, session_id):
        """
        Deletes one or more encrypted E2E room keys for a user for backup purposes.

        room_id: the ID of the room whose keys to delete (optional)
        session_id: the ID for the E2E session to delete (optional)
        version: the version of the user's backup which this data is for.
        the version must already have been created via the /change_secret API.
        """

        requester = yield self.auth.get_user_by_req(request, allow_guest=False)
        user_id = requester.user.to_string()
        version = request.args.get("version")[0]

        yield self.e2e_room_keys_handler.delete_room_keys(
            user_id, version, room_id, session_id
        )
        defer.returnValue((200, {}))


def register_servlets(hs, http_server):
    RoomKeysServlet(hs).register(http_server)