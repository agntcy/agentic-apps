from agp import AGP


def on_message_received(message: bytes):
    # Decode the message from bytes to string
    decoded_message = message.decode("utf-8")
    print(f"Received message: {decoded_message}")


async def main():
    # Instantiate the AGP class
    agp = AGP(
        agp_endpoint="http://localhost:12345",
        local_id="localid",
        shared_space="chat",
    )

    await agp.init()

    # Connect to the AGP server and start receiving messages
    await agp.receive(callback=on_message_received)

    # Publish a message to the AGP server
    await agp.publish(msg="Hello, this is a test message!".encode("utf-8"))


if __name__ == "__main__":
    import asyncio

    # Run the main function
    asyncio.run(main())
