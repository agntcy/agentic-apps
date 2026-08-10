// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

import { SessionType } from "@agntcy/slim-bindings-react-native/web";
import type {
  AppLike,
  NameLike,
  ServiceLike,
  SessionLike,
} from "@agntcy/slim-bindings-react-native/web";

import {
  createAndConnectApp,
  describeError,
  initializeWasm,
  parseInviteNames,
  sleep,
  splitId,
} from "./common";
import { logSessionSecurity } from "./session-common";
import { SessionCard } from "./session-card";
import "./style.css";

function el<T extends HTMLElement>(id: string): T {
  const node = document.getElementById(id);
  if (!node) throw new Error(`missing #${id}`);
  return node as T;
}

// --- DOM ---------------------------------------------------------------------
const wasmStatus = el<HTMLSpanElement>("wasm-status");
const connStatus = el<HTMLSpanElement>("conn-status");
const modeSelect = el<HTMLSelectElement>("mode");
const modeHint = el<HTMLParagraphElement>("mode-hint");
const endpointInput = el<HTMLInputElement>("endpoint");
const localNameInput = el<HTMLInputElement>("local-name");
const secretInput = el<HTMLInputElement>("secret");
const tokenInput = el<HTMLInputElement>("token");
const connectBtn = el<HTMLButtonElement>("connect");
const disconnectBtn = el<HTMLButtonElement>("disconnect");
const autoAcceptInput = el<HTMLInputElement>("auto-accept");

const sessionTypeInput = el<HTMLSelectElement>("session-type");
const mlsInput = el<HTMLInputElement>("mls-enabled");
const channelField = el<HTMLDivElement>("channel-field");
const channelInput = el<HTMLInputElement>("channel");
const inviteesField = el<HTMLDivElement>("invitees-field");
const inviteesInput = el<HTMLTextAreaElement>("invitees");
const destinationField = el<HTMLDivElement>("destination-field");
const destinationInput = el<HTMLInputElement>("destination");
const createBtn = el<HTMLButtonElement>("create-session");

const sessionsEl = el<HTMLDivElement>("sessions");
const sessionsEmpty = el<HTMLDivElement>("sessions-empty");
const sessionCount = el<HTMLSpanElement>("session-count");
const logEl = el<HTMLPreElement>("log");
const clearLogBtn = el<HTMLButtonElement>("clear-log");

// --- state -------------------------------------------------------------------
let wasmReady = false;
let app: AppLike | undefined;
let service: ServiceLike | undefined;
let connId: bigint | undefined;
let localName = "";
let listenAbort: AbortController | undefined;
const cards = new Map<number, SessionCard>();
let nextCardId = 1;

const modeHints: Record<string, string> = {
  moderator:
    "Create sessions and invite participants by name. Enable auto-accept below if you also want to receive invitations.",
  participant:
    "Auto-accepts incoming sessions on connect. You can still create your own session to be in two at once.",
};

// --- helpers -----------------------------------------------------------------
function log(message: string): void {
  logEl.textContent += `[${new Date().toLocaleTimeString()}] ${message}\n`;
  logEl.scrollTop = logEl.scrollHeight;
}

function logError(message: string, error: unknown): void {
  log(`ERROR: ${message}: ${describeError(error)}`);
  console.error(message, error);
}

function setConnectedUi(connected: boolean): void {
  connectBtn.disabled = connected || !wasmReady;
  disconnectBtn.disabled = !connected;
  createBtn.disabled = !connected;
  autoAcceptInput.disabled = !connected;
  modeSelect.disabled = connected;
  for (const input of [endpointInput, localNameInput, secretInput, tokenInput]) {
    input.disabled = connected;
  }
}

function updateComposerMode(): void {
  const group = sessionTypeInput.value === "group";
  channelField.hidden = !group;
  inviteesField.hidden = !group;
  destinationField.hidden = group;
}

function updateModeHint(): void {
  modeHint.textContent = modeHints[modeSelect.value] ?? "";
}

function syncSessionsUi(): void {
  sessionsEmpty.hidden = cards.size > 0;
  sessionCount.textContent = String(cards.size);
}

function addCard(session: SessionLike, origin: "created" | "incoming"): SessionCard {
  logSessionSecurity(session, log);
  const card = new SessionCard({
    id: nextCardId++,
    session,
    origin,
    localName,
    log,
    logError,
    onClose: (id) => void closeSession(id),
    onInvite: (id, participant) => inviteToSession(id, participant),
  });
  cards.set(card.id, card);
  sessionsEl.appendChild(card.element);
  syncSessionsUi();
  return card;
}

// --- core flow (mirrors examples/browser) ------------------------------------
async function connect(): Promise<void> {
  if (!wasmReady || app) return;
  connectBtn.disabled = true;
  connectBtn.textContent = "Connecting...";
  try {
    localName = localNameInput.value.trim();
    const connected = await createAndConnectApp({
      endpoint: endpointInput.value,
      localId: localName,
      sharedSecret: secretInput.value,
      token: tokenInput.value.trim() || undefined,
    });
    app = connected.app;
    service = connected.service;
    connId = connected.connId;

    const detail = ` (conn ${connId})`;
    log(`Connected as ${app.name().toString()}${detail}`);
    connStatus.textContent = `Connected${detail}`;
    connStatus.className = "badge badge-ready";
    setConnectedUi(true);

    if (modeSelect.value === "participant") {
      autoAcceptInput.checked = true;
      startListening();
    }
  } catch (error) {
    logError("Connection failed", error);
    app = undefined;
    service = undefined;
    connId = undefined;
    setConnectedUi(false);
  } finally {
    connectBtn.textContent = "Connect";
  }
}

async function createSession(): Promise<void> {
  const currentApp = app;
  const currentConnId = connId;
  if (!currentApp || currentConnId === undefined) return;

  const group = sessionTypeInput.value === "group";
  const mls = mlsInput.checked;
  createBtn.disabled = true;
  createBtn.textContent = "Creating...";
  try {
    const destination = splitId(
      (group ? channelInput.value : destinationInput.value).trim(),
    );
    const invitees: NameLike[] = group
      ? parseInviteNames(inviteesInput.value, localName)
      : [destination];

    for (const participant of invitees) {
      await currentApp.setRouteAsync(participant, currentConnId);
      log(`Route to ${participant.toString()} installed`);
    }

    const created = await currentApp.createSessionAndWaitAsync(
      {
        sessionType: group ? SessionType.Group : SessionType.PointToPoint,
        maxRetries: 10,
        interval: 1_000,
        metadata: new Map([
          ["demo", "slim-cross-transport"],
          ["delivery", group ? "multicast" : "unicast"],
          ["security", mls ? "mls" : "plaintext"],
        ]),
        mlsSettings: mls ? { headerIntegrityValidationPercent: 100 } : undefined,
      },
      destination,
    );

    await sleep(100);

    const pendingId = nextCardId;
    log(
      `Session #${pendingId} created (${group ? "multicast" : "unicast"}, ${mls ? "MLS" : "no MLS"})`,
    );

    if (group) {
      for (const participant of invitees) {
        const label = participant.toString();
        log(`Session #${pendingId}: inviting ${label}...`);
        try {
          await created.inviteAndWaitAsync(participant);
          log(`Session #${pendingId}: ${label} joined`);
        } catch (error) {
          logError(
            `Session #${pendingId}: ${label} did not join — check it is connected with this exact name and the same shared secret`,
            error,
          );
        }
      }
    }

    addCard(created, "created");
  } catch (error) {
    logError("Unable to create the session", error);
    log("Check the endpoint, channel/remote name, and shared secret.");
  } finally {
    createBtn.textContent = "Create session";
    createBtn.disabled = !app;
  }
}

async function inviteToSession(id: number, participant: string): Promise<void> {
  const currentApp = app;
  const currentConnId = connId;
  const card = cards.get(id);
  if (!currentApp || currentConnId === undefined || !card) return;
  const name = splitId(participant.trim());
  await currentApp.setRouteAsync(name, currentConnId);
  log(`Route to ${name.toString()} installed`);
  await card.session.inviteAndWaitAsync(name);
  log(`Session #${id}: ${name.toString()} joined`);
}

function startListening(): void {
  const currentApp = app;
  if (!currentApp || listenAbort) return;
  const controller = new AbortController();
  listenAbort = controller;
  autoAcceptInput.checked = true;
  log("Accepting incoming sessions...");

  void (async () => {
    const { signal } = controller;
    while (app === currentApp && !signal.aborted) {
      try {
        const incoming = await currentApp.listenForSessionAsync(undefined, {
          signal,
        });
        if (signal.aborted) break;
        const card = addCard(incoming, "incoming");
        log(`Session #${card.id} accepted from a moderator`);
      } catch (error) {
        if (!signal.aborted) logError("Incoming session listener stopped", error);
        break;
      }
    }
    if (listenAbort === controller) {
      listenAbort = undefined;
      autoAcceptInput.checked = false;
    }
  })();
}

function stopListening(): void {
  listenAbort?.abort();
  listenAbort = undefined;
  autoAcceptInput.checked = false;
}

async function closeSession(id: number): Promise<void> {
  const card = cards.get(id);
  if (!card) return;
  card.stop();
  try {
    await app?.deleteSessionAndWaitAsync(card.session);
    log(`Session #${id} closed`);
  } catch (error) {
    logError(`Unable to close session #${id}`, error);
  }
  card.element.remove();
  cards.delete(id);
  syncSessionsUi();
}

async function disconnect(): Promise<void> {
  stopListening();
  const current = app;
  const currentService = service;
  const currentConnId = connId;
  for (const card of [...cards.values()]) {
    card.stop();
    try {
      await current?.deleteSessionAndWaitAsync(card.session);
    } catch {
      // best-effort cleanup
    }
    card.element.remove();
  }
  cards.clear();
  syncSessionsUi();

  if (currentService && currentConnId !== undefined) {
    try {
      currentService.disconnect(currentConnId);
    } catch (error) {
      logError("Disconnect failed", error);
    }
  }
  app = undefined;
  service = undefined;
  connId = undefined;
  log("Disconnected");
  connStatus.textContent = "Disconnected";
  connStatus.className = "badge badge-idle";
  setConnectedUi(false);
}

// --- wiring ------------------------------------------------------------------
modeSelect.addEventListener("change", updateModeHint);
sessionTypeInput.addEventListener("change", updateComposerMode);
connectBtn.addEventListener("click", () => void connect());
disconnectBtn.addEventListener("click", () => void disconnect());
createBtn.addEventListener("click", () => void createSession());
autoAcceptInput.addEventListener("change", () => {
  if (autoAcceptInput.checked) startListening();
  else stopListening();
});
clearLogBtn.addEventListener("click", () => {
  logEl.textContent = "";
});
window.addEventListener("pagehide", () => void disconnect());

updateModeHint();
updateComposerMode();
setConnectedUi(false);

void (async () => {
  try {
    await initializeWasm();
    wasmReady = true;
    wasmStatus.textContent = "WASM ready";
    wasmStatus.className = "badge badge-ready";
    connectBtn.disabled = false;
    log("WASM bindings initialized");
  } catch (error) {
    wasmStatus.textContent = "WASM failed";
    wasmStatus.className = "badge badge-error";
    logError("Unable to initialize WASM bindings", error);
  }
})();
