import asyncio
import os

from google.adk.memory import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agent import root_agent

APP_NAME = "shadi_avatar"
USER_ID = os.getenv("AVATAR_USER_ID", "local-user")
SESSION_ID = os.getenv("AVATAR_SESSION_ID", "avatar-session")


async def run_chat():
    session_service = InMemorySessionService()
    memory_service = InMemoryMemoryService()

    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )

    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
        memory_service=memory_service,
    )

    print("Avatar ready. Type 'exit' to quit.")
    while True:
        line = input("avatar> ").strip()
        if not line:
            continue
        if line in ("exit", "quit", ":exit"):
            break

        content = types.Content(role="user", parts=[types.Part(text=line)])
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=SESSION_ID,
            new_message=content,
        ):
            if event.is_final_response() and event.content and event.content.parts:
                print(event.content.parts[0].text.strip())


if __name__ == "__main__":
    asyncio.run(run_chat())
