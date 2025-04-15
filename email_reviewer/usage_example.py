import llama_deploy
import asyncio
from dotenv import load_dotenv
import os

load_dotenv()

EMAIL_EXAMPLE = """"Dear Team,

I am writng to inform you that the server will be down for maintenance on Saturday, 25th December 2022 from 8:00 AM to 12:00 PM. During this time, the server won't not be accessible.

We apologize for any inconvenience this may cause and appreciate your understandings.

Best regards,
John Doe
"""

async def stream_events():
    client = llama_deploy.Client(timeout=10)
    session = await client.core.sessions.create()
    task_id = await session.run_nowait(
        "email_reviewer", target_audience="technical", email=EMAIL_EXAMPLE
    )

    async for event in session.get_task_result_stream(task_id):
        if "progress" in event:
            print(f'Workflow Progress: {event["progress"]}')

    final_result = await session.get_task_result(task_id)
    print(final_result)

    await client.core.sessions.delete(session.id)

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(stream_events())
