# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import asyncio
import datetime
from typing import Coroutine

import slim_bindings


class SLIM:
    def __init__(self, slim_endpoint: str, local_id: str, shared_space: str, opentelemetry_endpoint):
        # init tracing

        if opentelemetry_endpoint is not None:
            slim_bindings.init_tracing(
                {
                    "log_level": "info",
                    "opentelemetry": {
                        "enabled": True,
                        "grpc": {
                            "endpoint": opentelemetry_endpoint,
                        },
                    },
                }
            )
        else:
            slim_bindings.init_tracing({"log_level": "info", "opentelemetry": {"enabled": False}})

        # Split the local IDs into their respective components
        self.local_organization, self.local_namespace, self.local_agent = (
            "company",
            "namespace",
            local_id,
        )

        # Split the remote IDs into their respective components
        self.remote_organization, self.remote_namespace, self.shared_space = (
            "company",
            "namespace",
            shared_space,
        )

        self.session_info: slim_bindings.PySessionInfo = None
        self.participant: slim_bindings.Slim = None
        self.slim_endpoint = slim_endpoint

    async def init(self):
        self.participant = await slim_bindings.Slim.new(self.local_organization, self.local_namespace, self.local_agent)

        # Connect to gateway server
        _ = await self.participant.connect({"endpoint": self.slim_endpoint, "tls": {"insecure": True}})

        # set route for the chat, so that messages can be sent to the other participants
        await self.participant.set_route(self.remote_organization, self.remote_namespace, self.shared_space)

        # Subscribe to the producer topic
        await self.participant.subscribe(self.remote_organization, self.remote_namespace, self.shared_space)

        # create pubsubb session. A pubsub session is a just a bidirectional
        # streaming session, where participants are both sender and receivers
        self.session_info = await self.participant.create_session(
            slim_bindings.PySessionConfiguration.Streaming(
                slim_bindings.PySessionDirection.BIDIRECTIONAL,
                topic=slim_bindings.PyAgentType(self.remote_organization, self.remote_namespace, self.shared_space),
                max_retries=5,
                timeout=datetime.timedelta(seconds=5),
            )
        )

    async def receive(
        self,
        callback: Coroutine,
    ):
        # define the background task
        async def background_task():
            async with self.participant:
                while True:
                    try:
                        # receive message from session
                        recv_session, msg_rcv = await self.participant.receive(session=self.session_info.id)
                        # call the callback function
                        await callback(msg_rcv)
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        print(f"Error receiving message: {e}")
                        break

        self.receive_task = asyncio.create_task(background_task())

    async def publish(self, msg: bytes):
        await self.participant.publish(
            self.session_info,
            msg,
            self.remote_organization,
            self.remote_namespace,
            self.shared_space,
        )
