# SLIM Cross-Transport Demo

A self-contained demo of SLIM cross-transport messaging in the browser. It runs **three browser
participants** (WASM bindings over WebSocket via `@agntcy/slim-bindings-react-native`), **two native WebSocket clients**,
and **two native gRPC clients** against a **single dual-transport SLIM node** -
all on one set of channels. The browser is the moderator and can create multiple
sessions at once (multicast or unicast, MLS or plaintext), so a single
participant can be in two sessions simultaneously.

This README is the source of truth for running the demo. It uses this demo's own
node config: WebSocket on `:46357` and gRPC on `:46358`.

```
┌───────────────────────────┐
│ Browser participants      │
│ • browser-a (moderator)   │──── WebSocket ────┐
│ • browser-b               │                   │
│ • browser-c               │                   │
└───────────────────────────┘                   │
                                                ▼
┌───────────────────────────┐       ┌───────────────────────────┐
│ Native WebSocket clients  │       │ SLIM node                 │
│ • native-ws-1             │──────>│ • WebSocket :46357        │
│ • native-ws-2             │  WS   │ • gRPC :46358             │
└───────────────────────────┘       │ • Shared routing fabric   │
                                    └───────────────────────────┘
                                                ▲
┌───────────────────────────┐                   │
│ Native gRPC clients       │                   │
│ • native-grpc-1           │────── gRPC ───────┘
│ • native-grpc-2           │
└───────────────────────────┘
```

The browser UI depends on
[`@agntcy/slim-bindings-react-native@2.0.0`](https://www.npmjs.com/package/@agntcy/slim-bindings-react-native/v/2.0.0).
The `/web` entry point and prebuilt `index_bg.wasm` ship in that package.

---

## Prerequisites

| Tool | Version / notes |
| --- | --- |
| [Node.js](https://nodejs.org/) | 18 or later |
| [Rust](https://rustup.rs/) | 1.70 or later (for the SLIM node and native clients) |
| [Task](https://taskfile.dev/) | task runner for orchestrating demo processes |

---

## Step 1 — Clone the repositories

Create a workspace folder and clone **agentic-apps** and **slim** as siblings:

```bash
mkdir -p ~/slim-workspace && cd ~/slim-workspace

git clone https://github.com/agntcy/agentic-apps.git
git clone https://github.com/agntcy/slim.git
```

Layout:

```
slim-workspace/
├── agentic-apps/
│   └── slim-cross-transport/     ← this demo
└── slim/                         ← SLIM node + native client examples
```

---

## Step 2 — Install the demo app

```bash
cd ~/slim-workspace/agentic-apps/slim-cross-transport
npm install
```

This pulls [`@agntcy/slim-bindings-react-native@2.0.0`](https://www.npmjs.com/package/@agntcy/slim-bindings-react-native/v/2.0.0) from npm, including the browser WASM binary.

**Optional — confirm WASM is present:**

```bash
test -f node_modules/@agntcy/slim-bindings-react-native/generated/web/wasm-bindgen/index_bg.wasm && echo "WASM OK"
```

---

## Step 3 — Run the demo

Each long-running process needs its **own terminal**. All commands below run from `agentic-apps/slim-cross-transport`.

### Terminal 1 — SLIM node (dual transport)

```bash
task node
```

Starts the SLIM data-plane node with:

- WebSocket on `ws://0.0.0.0:46357` (browser + native WebSocket clients)
- gRPC on `0.0.0.0:46358` (native gRPC clients)

### Terminals 2–5 — Native participants

```bash
task native:grpc-1   # terminal 2
task native:grpc-2   # terminal 3
task native:ws-1     # terminal 4
task native:ws-2     # terminal 5
```

Wait until **each** terminal prints:

```
connection established (conn …)
CLIENT: Entering message receive loop
```

before creating a session in the browser.

### Terminal 6 — Browser UI

```bash
task ui
```

Serves the Vite dev server at **http://127.0.0.1:5173**.

---

## Step 4 — Use the browser UI

Open **three tabs** at http://127.0.0.1:5173.

In every tab:

| Field | Value |
| --- | --- |
| **WebSocket endpoint** | `ws://127.0.0.1:46357` (prefilled) |
| **Shared secret** | `test-shared-secret-value-0123456789abcdef` (prefilled) |

Set **Mode** and **Local name** per tab:

| Tab | Mode | Local name |
| --- | --- | --- |
| 1 | Moderator | `org/default/browser-a` |
| 2 | Participant | `org/default/browser-b` |
| 3 | Participant | `org/default/browser-c` |

Click **Connect** in all three tabs. Participants auto-accept incoming sessions; the moderator creates them.

To run a cross-transport multicast session from the moderator tab:

1. Delivery: **Multicast (group)**
2. Channel: `org/default/room-1`
3. Invitees (one per line): `org/default/browser-b`, `org/default/native-ws-1`, `org/default/native-grpc-1`
4. Click **Create session**, then send a message from the session card

---

## Quick reference — Task commands

| Task | Purpose |
| --- | --- |
| `task node` | Start dual-transport SLIM node |
| `task native:ws-1` / `native:ws-2` | Native WebSocket participants |
| `task native:grpc-1` / `native:grpc-2` | Native gRPC participants |
| `task ui` | Vite dev server for the browser UI |
| `task native:chat-ws` | Interactive native WebSocket chat (optional) |
| `task native:chat-grpc` | Interactive native gRPC chat (optional) |

---

## Demo files

| Path | Purpose |
| --- | --- |
| `configs/server-config.yaml` | Dual-transport node (`:46357` ws + `:46358` gRPC) |
| `configs/native-ws-client.yaml` | Native WebSocket client transport |
| `configs/native-grpc-client.yaml` | Native gRPC client transport |
| `Taskfile.yaml` | Orchestration tasks for node, clients, UI |
| `src/main.ts` | Connect / create+invite / listen flow |
| `src/session-card.ts` | Per-session UI (send, roster, close) |
| `index.html` | Multi-session browser shell |

---

## Recording script

1. **Intro.** All seven participants are up: three browser tabs, two native
   gRPC clients, two native WebSocket clients, one SLIM node.
2. **Multicast + MLS across transports.** In the moderator tab (`browser-a`),
   keep **Multicast**, leave **Enable MLS** on, channel `org/default/room-1`,
   invitees `browser-b`, `native-ws-1`, `native-grpc-1`. Click **Create
   session**. A card appears; send a message. It fans out to the browser tab and
   both native transports (watch the native terminals). The node only sees
   ciphertext.
3. **A second session, no MLS.** Still in the moderator tab, without closing
   room-1: switch to channel `org/default/room-2`, turn **Enable MLS** off,
   invitees `browser-c`, `native-ws-2`, `native-ws-1`. Click **Create session**.
   The moderator now shows **two active session cards at once**, and
   `native-ws-1` is a member of both room-1 and room-2 - the "one participant,
   two sessions" moment.
4. **One participant, two sessions (browser).** In the `browser-b` tab (already
   in room-1 as an invitee), switch delivery to Multicast, channel
   `org/default/room-2b`, invitees `browser-c`, and click **Create session**.
   `browser-b` now has two session cards too - a participant that is also
   moderating its own second session.
5. **Unicast, optional.** In `browser-b` choose **Unicast**, remote
   `org/default/browser-c`, enable MLS, and create a point-to-point session with
   `browser-c`.
6. **Wrap up.** Send messages in different cards to show they are independent,
   then **Close session** on each card and **Disconnect**.

---

## UI reference

| Control | Purpose |
| --- | --- |
| Mode | `Moderator` creates sessions; `Participant` auto-accepts incoming sessions on connect |
| WebSocket endpoint | `ws://` (or `wss://`) address of the node's WebSocket listener |
| Local name | Any three-component SLIM application name you choose (`org/namespace/name`) |
| Shared secret | Common end-to-end identity secret (>= 32 chars) |
| Auth token | Only for auth-enabled servers (WebSocket query token) |
| Auto-accept incoming sessions | Runs a loop that accepts every invitation as a new card |
| Delivery / Enable MLS | Session type and per-session end-to-end encryption |
| Channel / Participants | Multicast destination and invitees |
| Remote participant | Unicast destination |
| Create session | Installs upstream routes, creates the session, invites participants |
| Invite (session card) | On a group session you moderate, add a new participant mid-session (routes then invites them) |
| Session card | Independent send box, message log, participant roster, and Close |

---

## Notes and limitations

- The browser is the **moderator**. The native [`client`](../../slim/crates/examples/src/client/main.rs)
  example is a passive participant (accepts sessions, sends its one `--message`);
  it cannot create/invite. Native-moderated flows would need a new native
  example.
- Transport is selected by endpoint scheme: `ws://`/`wss://` = WebSocket, bare
  `host:port` / `http://` = gRPC.
- Invitations target three-component **application** names (e.g.
  `org/default/native-ws-1`), not instance names like `org/default/native-ws/1`.

---

## Troubleshooting

- **`403 Forbidden` for `index_bg.wasm`** — run via `task ui` at http://127.0.0.1:5173/, not by opening `index.html` directly. Re-run `npm install` if the WASM file is missing from `node_modules`.
- **`Cannot find module '@agntcy/slim-bindings-react-native/web'`** — run `npm install` in this folder.
- **Invite times out / participant never joins** — check in order:
  1. **Endpoint** — every browser tab uses `ws://127.0.0.1:46357`
  2. **Names** — invited names match each participant's Local name exactly (e.g. `org/default/native-ws-1`)
  3. **Secret** — same shared secret everywhere
  4. **Native clients** — all four running and showing `connection established` before Create session
  5. **MLS** — if invites time out with MLS on, retry once with **Enable MLS** off
- **Native clients do not join** — confirm the node listens on `:46357` (ws) and `:46358` (grpc)
- **HTTPS page cannot connect** — use a `wss://` endpoint on a TLS-terminated node

---

## End-to-end checklist

```bash
# 1. Layout
ls ~/slim-workspace/agentic-apps/slim-cross-transport
ls ~/slim-workspace/slim

# 2. Demo deps (includes npm WASM bindings)
cd ~/slim-workspace/agentic-apps/slim-cross-transport && npm install
test -f node_modules/@agntcy/slim-bindings-react-native/generated/web/wasm-bindgen/index_bg.wasm

# 3. Run (separate terminals)
task node
task native:grpc-1 && task native:grpc-2 && task native:ws-1 && task native:ws-2
task ui
```

Then open http://127.0.0.1:5173 and connect three browser tabs as described in Step 4.
