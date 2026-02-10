# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import asyncio
import datetime
import time
from typing import Coroutine

import slim_bindings
import logging

log = logging.getLogger(__name__)

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
        self.local_name = slim_bindings.PyName(self.local_organization, self.local_namespace, self.local_agent)

        # Split the remote IDs into their respective components
        self.remote_organization, self.remote_namespace, self.shared_space = (
            "company",
            "namespace",
            shared_space,
        )
        self.remote_name = slim_bindings.PyName(self.remote_organization, self.remote_namespace, self.shared_space)

        self.session_info: slim_bindings.PySessionInfo = None
        self.participant: slim_bindings.Slim = None
        self.slim_endpoint = slim_endpoint

    async def init(self):
        provider = slim_bindings.PyIdentityProvider.SharedSecret(
            identity=self.local_agent,
            shared_secret="secret",
            )
        verifier = slim_bindings.PyIdentityVerifier.SharedSecret(
            identity=self.local_agent,
            shared_secret="secret",
        )
        self.participant = await slim_bindings.Slim.new(self.local_name, provider, verifier)

        # Connect to gateway server
        _ = await self.participant.connect({"endpoint": self.slim_endpoint, "tls": {"insecure": True}})

        log.debug(f"Connected to slim endpoint!, local_name is {self.local_name}")

        # The moderator creates the session and invite everybody else
        if self.local_agent == "noa-moderator":
            # create pubsub session. A pubsub session is a just a bidirectional
            # streaming session, where participants are both sender and receivers
            self.session_info = await self.participant.create_session(
                slim_bindings.PySessionConfiguration.Streaming(
                    slim_bindings.PySessionDirection.BIDIRECTIONAL,
                    topic=self.remote_name, # Name of the shared channel
                    max_retries=5,
                    moderator=True,
                    timeout=datetime.timedelta(seconds=5),
                )
            )
            log.debug(f"remote_name: {self.remote_name}")

            # Wait for all the other agents to be up
            # Hack for now
            time.sleep(10)
            for agent_name in ["noa-file-assistant", "noa-math-assistant", "noa-user-proxy", "noa-web-surfer-assistant"]:
                participant_name = slim_bindings.PyName(self.local_organization, self.local_namespace, agent_name)
                log.debug(f"Sending invite to {agent_name} : {participant_name}")
                await self.participant.set_route(participant_name)
                await self.participant.invite(self.session_info, participant_name)
            # Give time to the invitation to be processed
            time.sleep(10)

    async def receive(
        self,
        callback: Coroutine,
    ):
        # define the background task
        async def background_task():
            async with self.participant:
                if self.local_agent != "noa-moderator":
                    # Not the moderator, wait for the session info to be sent out first
                    self.session_info, _ = await self.participant.receive()
                    log.debug(f"Received session info {self.session_info}")
                while True:
                    try:
                        # receive message from session
                        recv_session, msg_rcv = await self.participant.receive(session=self.session_info.id)
                        # call the callback function
                        await callback(msg_rcv)
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        log.error(f"Error receiving message: {e}")
                        break

        self.receive_task = asyncio.create_task(background_task())

    async def publish(self, msg: bytes):
        await self.participant.publish(
            self.session_info,
            msg,
            self.remote_name,
#            self.remote_organization,
#            self.remote_namespace,
#            self.shared_space,
        )
