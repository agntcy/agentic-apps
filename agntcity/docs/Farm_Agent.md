# Adding Farm Agents (or Sub-Agents) to Lungo (Auction Supervisor Flow Only)

This document defines the **minimum configuration** and a **common contract** for adding new “farm” agents that can be supervised by the Lungo Auction Supervisor.

The current supervisor implementation uses the **A2A protocol** over **SLIM/NATS** transports (via the app-sdk transport layer).

## Minimum Configuration to Register a New Farm

In the current codebase, “registering a farm” means that the supervisor can create an A2A client that can route messages to the farm using an **AgentCard**.

## Supervisor-Side Registration and Messaging

Supervisor updates:
- `agents/supervisors/auction/graph/tools.py`:
  - Import the new farm `AGENT_CARD`.
  - Update `get_farm_card()`.
  - Add the farm to the broadcast recipients list in `get_all_farms_yield_inventory()` and `get_all_farms_yield_inventory_streaming()`.
- `agents/supervisors/auction/graph/graph.py`:
  - Add the farm to supervisor-side routing (single-farm detection and the list of known farms).

Messaging:
- Unicast: send to `A2AProtocol.create_agent_topic(AgentCard)`.
- Broadcast: send on `FARM_BROADCAST_TOPIC` with a recipients list.

### 1) Transport & Routing Config

The supervisor uses these environment variables (see `config/config.py`):

```env
DEFAULT_MESSAGE_TRANSPORT=NATS            # or SLIM
TRANSPORT_SERVER_ENDPOINT=nats://localhost:4222 # or http://localhost:46357
FARM_BROADCAST_TOPIC=farm_broadcast_topic_name
```

### 2) An AgentCard for the Farm

Each farm is represented by an `AgentCard` (see current examples under `agents/farms/<farm>/card.py`).

Minimum fields you should provide:

- **`name`**: a stable, human-readable name (e.g., `Kenya Coffee Farm`).
- **`id`**: a stable, unique ID (see existing `*-farm-agent` IDs).
- **`description`**: a brief description of what the farm can do.
- **`version`**: the card version.
- **`defaultInputModes`** / **`defaultOutputModes`**: `"text"`.
- **`capabilities`**: e.g., streaming.
- **`skills`**: at least an “inventory/yield” skill.

The supervisor currently expects new farms to be wired into:

- A new card module: `agents/farms/<new_farm>/card.py` exporting `AGENT_CARD`.
- Import the new farm card in `agents/supervisors/auction/graph/tools.py` and add it to `get_farm_card()`.
- The broadcast recipients list in `agents/supervisors/auction/graph/tools.py` (see the `farm_names = [...]` list used by `get_all_farms_yield_inventory()` / `get_all_farms_yield_inventory_streaming()`).
- The supervisor router in `agents/supervisors/auction/graph/graph.py` (the `_supervisor_node` prompt currently hard-codes the known farms: Brazil, Colombia, Vietnam).

### 3) Farm A2A Server (Topics + Reply Contract)

Your farm runs an A2A server (see existing `agents/farms/<farm>/farm_server.py`) that:

- Accepts A2A `SendMessageRequest` requests.
- Replies with a response whose first part is text (`result.parts[0].text`).
- Subscribes to both of these transport topics (two `AppContainer`s in a single app session):
  - **Unicast (personal)**: `A2AProtocol.create_agent_topic(AGENT_CARD)`
  - **Broadcast**: `FARM_BROADCAST_TOPIC`

In practice, the supervisor sends:

- **Unicast** requests to the personal topic when querying a single farm.
- **Broadcast** requests on `FARM_BROADCAST_TOPIC` when querying all farms (the broadcast includes an explicit recipients list of farm personal topics).

The supervisor currently expects responses to be in **plain text**.

If you have identity verification enabled, the supervisor verifies identity by matching the farm's identity app name against `AgentCard.name` (see `verify_farm_identity()` in `agents/supervisors/auction/graph/tools.py`).


## The Common Farm Agent Contract

Regardless of the internal framework, each farm should implement the same **external contract**.

### Inputs

The supervisor sends natural-language messages. In practice, they fall into these categories:

#### A) Inventory / Yield / Availability Queries

Examples:

- `"How much coffee does the Kenya farm have?"`
- `"What is your current yield?"`
- Broadcast variant: `"What yield do the farms have?"`

#### B) Order Creation

The supervisor’s tool sends a message of the form:

- `"Create an order with price <price> and quantity <quantity>"`

The farm should interpret this as an order request and return a confirmation message.

### Outputs (Expected by the Supervisor)

The supervisor expects the A2A response to contain a **first text part**.

#### A) Inventory Response Format

Return only the yield/inventory value with a unit.

Example:

```text
5000 lbs
```

#### B) Order Response Format

Return plain text that includes an `order_id:` line.

Example:
```text
order_id: 54321
```

## Reusable Prompt Template for Farm Agents

Use this as the **system prompt** for any farm agent, regardless of internal implementation.

> **Note:** Might need to tweak the prompt slightly for different frameworks/models.

```text
You are a coffee farm manager in {FARM_COUNTRY} who delegates farm cultivation and global sales.

Based on the user's message, determine whether it is related to 'inventory' or 'orders'.
- Respond with 'inventory' if the message is about checking yield, stock, product availability, or specific coffee item details.
- Respond with 'orders' if the message is about checking order status, placing an order, or modifying an existing order.
- If unsure, respond with 'general'.

Inventory behavior:
- Return a random yield estimate for the coffee farm in {FARM_COUNTRY}.
- Make sure the estimate is a reasonable value and in pounds.
- Respond with only the yield estimate.
- If the user asked in lbs or pounds, respond in pounds.
- If the user asked in kg or kilograms, convert to kg and respond with that value.

Orders behavior:
- You are an order assistant. Based on the user's question and the following order data, provide a concise and helpful response.
- If they ask about a specific order number, provide its status.
- If they ask about placing an order, generate a random order ID and tracking number.

Output rules:
- Output must be plain text.
- For inventory, return a single line like: "5000 lbs".
- For order creation, include an order ID line like: "order_id: 54321".

```

## Adding Farm Agents by Framework

You can implement a farm with different frameworks, as long as it produces the same **plain-text** outputs for inventory and order creation.

When adding a new farm, you can copy an existing farm directory as a starting point and adjust:
- `agent.py`
- `agent_executor.py`
- `farm_server.py`
- `card.py`

### Adding Tracing Support

Add tracing support to the farm server using `ioa-observe-sdk`. To do this, follow the pattern used by existing farms:

```python
from ioa_observe_sdk.decorators import agent, graph, tool

@graph(name="farm_graph")
def build_graph():
    ...

@agent(name="farm_agent")
def run_agent(...):
    ...

@tool(name="some_tool")
def some_tool_fn(...):
    ...
```

### LangGraph Farm

Where to look:
- `agents/farms/<farm>/agent.py`

Pattern:
- Route to two paths:
  - `inventory` (yield/availability)
  - `orders` (create order)
- Reuse a consistent prompt for inventory and another for order creation following the reusable prompt template above.
- Add tracing support to the farm server using `ioa-observe-sdk`.

### LlamaIndex farm

Where to look:
- `agents/farms/<farm>/agent.py`

Pattern:
- Use LlamaIndex internally (tools / retrieval / workflows) to implement:
  - inventory/yield responses
  - order creation responses
- Use the reusable prompt template above.
- Add a simple router (inventory vs orders) and return a single **plain-text** response.
- Add tracing support to the farm server using `ioa-observe-sdk`.

### Adding a new framework

You can use any agent framework as long as the farm keeps the same outward contract:
- Implement the farm logic in `agents/farms/<farm>/agent.py`.
- Support two request types:
  - Inventory/yield (messages like `"How much coffee does the Kenya farm have?"` or `"What yield do the farms have?"`)
  - Order creation (messages like `"Create an order with price <price> and quantity <quantity>"`)
- Use the reusable prompt template above.
- Always return a single plain-text response (the supervisor reads the first text part).
- Keep the farm discoverable by the supervisor via the farm `AgentCard` wiring.
- Add tracing support to the farm server using `ioa-observe-sdk`.
