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

> **Note:** The browser WASM bindings are **not published to npm yet**. This demo
> installs `@agntcy/slim-bindings-react-native` from a local `slim-bindings`
> checkout and expects you to **build the bindings manually** before running the
> UI. Follow the steps below in order.

---

## Prerequisites

Install these tools once on your machine:

| Tool | Version / notes |
| --- | --- |
| [Node.js](https://nodejs.org/) | 18 or later |
| [Rust](https://rustup.rs/) | 1.70 or later |
| Rust `wasm32` target | `rustup target add wasm32-unknown-unknown` |
| [Task](https://taskfile.dev/) | task runner used by this demo and slim-bindings |
| `wasm-bindgen-cli` | exactly **0.2.106** — installed automatically by the bindings build, or manually: `cargo install wasm-bindgen-cli --version 0.2.106` |

---

## Step 1 — Clone the repositories

Create a workspace folder and clone all three repos as **siblings**:

```bash
mkdir -p ~/slim-workspace && cd ~/slim-workspace

git clone https://github.com/agntcy/agentic-apps.git
git clone https://github.com/agntcy/slim.git
git clone https://github.com/agntcy/slim-bindings.git
```

Your directory layout must look like this (paths are relative to `~/slim-workspace`):

```
slim-workspace/
├── agentic-apps/
│   └── slim-cross-transport/     ← this demo
├── slim/                         ← SLIM node + native client examples
└── slim-bindings/
    └── react-native/             ← @agntcy/slim-bindings-react-native (built from source)
```

The demo's `package.json` links the bindings with:

```json
"@agntcy/slim-bindings-react-native": "file:../../slim-bindings/react-native"
```

That path resolves from `agentic-apps/slim-cross-transport/` up to `slim-workspace/`, then into `slim-bindings/react-native`. If your clones are not siblings, update that path or recreate the layout above.

Use a **wasm-clean branch** of `slim` (typically `main`). The WASM build compiles SLIM crates for `wasm32`; branches that pull full `tonic` transport for all targets will fail (see [Troubleshooting](#troubleshooting)).

---

## Step 2 — Build the React Native bindings (browser WASM)

The browser UI imports from `@agntcy/slim-bindings-react-native/web`. That entry point and the `index_bg.wasm` binary are **generated locally** — they are not shipped in the current npm release.

From the bindings package:

```bash
cd ~/slim-workspace/slim-bindings/react-native

# Install JS tooling (uniffi-bindgen-react-native, TypeScript, etc.)
npm install

# Generate browser TypeScript + WebAssembly (one-time, or after bindings changes)
npm run build:web
```

Under the hood, `npm run build:web` runs `task generate:web`, which:

1. Installs `wasm-bindgen-cli` 0.2.106 if missing
2. Runs `ubrn build web` to compile the Rust WASM crate and emit TypeScript
3. Writes output to `generated/web/` (including `generated/web/wasm-bindgen/index_bg.wasm`)

**Verify the build succeeded:**

```bash
test -f generated/web/wasm-bindgen/index_bg.wasm && echo "WASM OK"
test -f web.ts && echo "web entry OK"
```

If either check fails, see [Troubleshooting](#troubleshooting) before continuing.

> **iOS / Android only:** Native React Native bindings use `task generate` (not needed for this browser demo). This demo only requires the **web** build above.

---

## Step 3 — Install the demo app

With the bindings built, install the demo's npm dependencies (this creates the symlink into `slim-bindings/react-native`):

```bash
cd ~/slim-workspace/agentic-apps/slim-cross-transport

npm install
```

**Optional — confirm the link:**

```bash
ls node_modules/@agntcy/slim-bindings-react-native/generated/web/wasm-bindgen/index_bg.wasm
```

You should see the WASM file from your Step 2 build.

---

## Step 4 — Run the demo

Each long-running process needs its **own terminal**. All commands below assume you are in `agentic-apps/slim-cross-transport` unless noted.

### Terminal 1 — SLIM node (dual transport)

```bash
cd ~/slim-workspace/agentic-apps/slim-cross-transport
task node
```

Starts the SLIM data-plane node with:

- WebSocket on `ws://0.0.0.0:46357` (browser + native WebSocket clients)
- gRPC on `0.0.0.0:46358` (native gRPC clients)

Leave this running.

### Terminals 2–5 — Native participants

Start all four native clients. Each waits for a browser invite:

```bash
cd ~/slim-workspace/agentic-apps/slim-cross-transport

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
cd ~/slim-workspace/agentic-apps/slim-cross-transport
task ui
```

Serves the Vite dev server at **http://127.0.0.1:5173**.

---

## Step 5 — Use the browser UI

Open **three tabs** at http://127.0.0.1:5173.

In every tab:

| Field | Value |
| --- | --- |
| **WebSocket endpoint** | `ws://127.0.0.1:46357` (prefilled — do not change unless you changed the node port) |
| **Shared secret** | `test-shared-secret-value-0123456789abcdef` (prefilled — all participants must match) |

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

Run from `agentic-apps/slim-cross-transport`:

| Task | Purpose |
| --- | --- |
| `task wasm` | Rebuild browser WASM bindings (runs `npm run build:web` in `slim-bindings/react-native`) |
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
| `Taskfile.yaml` | Orchestration tasks for node, clients, wasm, UI |
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

### Bindings build

- **`task wasm` / `npm run build:web` fails compiling `mio` for `wasm32`**
  Your `slim` / `slim-bindings` checkout may not be wasm-clean. Use `main` (or another branch known to build for `wasm32`) and rebuild.
- **`wasm-bindgen` version mismatch**
  Install exactly 0.2.106: `cargo install wasm-bindgen-cli --version 0.2.106`
- **`ubrn: command not found`**
  Run `npm install` inside `slim-bindings/react-native` first; the build uses `npx ubrn`.

### Demo runtime

- **`403 Forbidden` for `index_bg.wasm`**
  Run the UI via `task ui` (not by opening `index.html` directly). Vite must serve the WASM from the linked bindings package. Re-run Step 2 if the file is missing.
- **`Cannot find module '@agntcy/slim-bindings-react-native/web'`**
  Complete Step 2 (`npm run build:web`) and Step 3 (`npm install` in this folder).
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

Use this if something is not working:

```bash
# 1. Layout
ls ~/slim-workspace/agentic-apps/slim-cross-transport
ls ~/slim-workspace/slim
ls ~/slim-workspace/slim-bindings/react-native

# 2. WASM built
test -f ~/slim-workspace/slim-bindings/react-native/generated/web/wasm-bindgen/index_bg.wasm

# 3. Demo deps linked
cd ~/slim-workspace/agentic-apps/slim-cross-transport && npm install
test -f node_modules/@agntcy/slim-bindings-react-native/generated/web/wasm-bindgen/index_bg.wasm

# 4. Run (separate terminals)
task node
task native:grpc-1 && task native:grpc-2 && task native:ws-1 && task native:ws-2
task ui
```

Then open http://127.0.0.1:5173 and connect three browser tabs as described in Step 5.
