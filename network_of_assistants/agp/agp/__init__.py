import asyncio
import datetime
from typing import Callable

import agp_bindings


class AGP:
    def __init__(self, agp_endpoint: str, local_id: str, shared_space: str):
        # init tracing
        agp_bindings.init_tracing(log_level="info", enable_opentelemetry=False)

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

        self.session_info: agp_bindings.PySessionInfo = None
        self.participant: agp_bindings.Gateway = None
        self.agp_endpoint = agp_endpoint

    async def init(self):
        print(self.local_organization, self.local_namespace, self.local_agent)
        self.participant = await agp_bindings.Gateway.new(
            self.local_organization, self.local_namespace, self.local_agent
        )
        self.participant.configure(
            agp_bindings.GatewayConfig(endpoint=self.agp_endpoint, insecure=True)
        )

        # Connect to gateway server
        _ = await self.participant.connect()

        # set route for the chat, so that messages can be sent to the other participants
        await self.participant.set_route(
            self.remote_organization, self.remote_namespace, self.shared_space
        )

        # Subscribe to the producer topic
        await self.participant.subscribe(
            self.remote_organization, self.remote_namespace, self.shared_space
        )

        # create pubsubb session. A pubsub session is a just a bidirectional
        # streaming session, where participants are both sender and receivers
        self.session_info = await self.participant.create_streaming_session(
            agp_bindings.PyStreamingConfiguration(
                agp_bindings.PySessionDirection.BIDIRECTIONAL,
                topic=agp_bindings.PyAgentType(
                    self.remote_organization, self.remote_namespace, self.shared_space
                ),
                max_retries=5,
                timeout=datetime.timedelta(seconds=5),
            )
        )

    async def receive(
        self,
        callback: Callable[[bytes], None],
    ):
        # define the background task
        async def background_task():
            async with self.participant:
                while True:
                    try:
                        # receive message from session
                        recv_session, msg_rcv = await self.participant.receive(
                            session=self.session_info.id
                        )
                        # call the callback function
                        callback(msg_rcv)
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
