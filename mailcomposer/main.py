# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
import json

from dotenv import load_dotenv, find_dotenv

load_dotenv(dotenv_path=find_dotenv(usecwd=True))
from mailcomposer.mailcomposer import graph, AgentState, OutputState
from mailcomposer.state import Message, Type as MsgType

def main():
    output = OutputState(
        messages=[],
        final_email=None
    )
    while(True) :
        if output.messages and len(output.messages) > 0:
            m = output.messages[-1]
            print(f"[Assistant] \t\t>>> {m.content}")
        if output.final_email:
            break
        message = input("YOU [Type OK when you are happy with the email proposed] >>> ")

        nextinput = AgentState(
            messages = (output.messages or []) + [Message(content=message, type=MsgType.human)]
        )
        if message == "OK":
            nextinput.is_completed = True
        out = graph.invoke(nextinput, {"configurable": {"thread_id": "foo"}})
        output: OutputState = OutputState.model_validate(out)

    print("Final email is:")
    print(output.final_email)

main()
