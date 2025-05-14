# Network Of Assistants

## Problem

Each Cisco product has its own specialized agent assistant. It is complex to create
a single assistant that can answer questions on different products. Each question
coming from the users needs to be routed to right agent, and some questions might
require knowledge/collaboration of multiple assistants.

## Solution

Exploit AGP multicast communication to create a “chat room” where multiple assistants
can cooperate. The chat history is visible to all the agents in the chat without requiring
central storage. A moderator agent coordinates the discussion among agents and the user in the chat.
The moderator can discover agents and invite them to join the chat when they are needed.
User and assistants are members of the same chat, instead of a hierarchal structure through
a supervisor, allowing user and product assistants to directly interact.

## Components

- AGP – Used to facilitate communication between the agents
- OASF – Used to declare the Assistants capabilities
- PDF Assistant – A simple assistant which can answer questions on a given set of PDFs, an example of a native NoA assistant.
- Moderator – A agent which moderates the chat between the user and the agents.
- User Proxy – A NoA agent which proxies to the user instead of an LLM

## Communication between Agents

<img width="704" alt="image" src="https://github.com/user-attachments/assets/83ec5302-0e2a-4536-808c-5097066d928d" />

---

<img width="725" alt="image" src="https://github.com/user-attachments/assets/ae1508ed-896c-4222-bbdd-f06cb4aa726d" />

---

<img width="724" alt="image" src="https://github.com/user-attachments/assets/cd10157f-e9c5-4d65-a6b3-c7fe6fa519f9" />

---

<img width="723" alt="image" src="https://github.com/user-attachments/assets/80e2eba6-617c-4f8b-a0fd-b3e5ededb4f1" />

---

<img width="710" alt="image" src="https://github.com/user-attachments/assets/bd7fee89-f6cc-4edd-91a9-322ec5e7dc5f" />

---

<img width="718" alt="image" src="https://github.com/user-attachments/assets/91cb9349-5640-4eac-b68f-463e3beab8cf" />

---

<img width="848" alt="image" src="https://github.com/user-attachments/assets/58cf6258-58a4-4d25-9f1b-39c60913c82b" />

---

<img width="723" alt="image" src="https://github.com/user-attachments/assets/f3e394b7-2c9a-4af8-a13b-9b2f85269490" />

---

<img width="709" alt="image" src="https://github.com/user-attachments/assets/ab5c47aa-8c8f-48ff-9b32-3f40fafaf7b6" />

---

<img width="738" alt="image" src="https://github.com/user-attachments/assets/0db10c88-42a1-425e-87ab-ca4fab8fca7c" />

---

<img width="779" alt="image" src="https://github.com/user-attachments/assets/69dee228-f23e-4133-b118-b8e4baabbd5c" />
