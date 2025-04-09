from agp import AGP

agp = AGP(
    agp_endpoint="http://localhost:12345",
    local_id="localid",
    shared_space="chat",
)

def command_callback(response):
    # This function will be called with the response from agp.sendmessage
    # print("Response from command:", response)
    decoded_message = response.decode("utf-8")
    print(f"Received message: {decoded_message}")
    prompt_for_command()

async def prompt_for_command():
    command = input("Enter command: ").strip().lower()

    if command == "quit":
        print("Exiting the application. Goodbye!")
        return
    else:
        await agp.publish(msg=command.encode("utf-8"))
        # Send the command using the agp library, with the command_callback as the callback function
        # agp.sendmessage(command, command_callback)

async def main():
    print("Welcome to the NoA! Type your command. Type 'quit' to exit.")
    # agp = AGP(
    #     agp_endpoint="http://localhost:12345",
    #     local_id="localid",
    #     shared_space="chat",
    # )

    await agp.init()

    # Connect to the AGP server and start receiving messages
    await agp.receive(callback=command_callback)
    prompt_for_command()

if __name__ == "__main__":
    main()