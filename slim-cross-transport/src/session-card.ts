// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

import { SessionType } from "@agntcy/slim-bindings-react-native/web";
import type {
  ReceivedMessage,
  SessionLike,
} from "@agntcy/slim-bindings-react-native/web";

import { describeError, toArrayBuffer } from "./common";
import {
  isReceiveTimeout,
  refreshSessionRoster,
  startSessionParticipantPolling,
} from "./session-common";

const encoder = new TextEncoder();
const decoder = new TextDecoder();

export type SessionOrigin = "created" | "incoming";

export interface SessionCardDeps {
  id: number;
  session: SessionLike;
  origin: SessionOrigin;
  localName: string;
  log: (message: string) => void;
  logError: (message: string, error: unknown) => void;
  onClose: (id: number) => void | Promise<void>;
  /** Invite a new participant into this session (route + invite). */
  onInvite?: (id: number, participant: string) => void | Promise<void>;
}

/**
 * A single active session rendered as a card: its own receive loop, send box,
 * participant roster, and transport/type/MLS badges. Several cards can be live
 * at once for the same connected participant.
 */
export class SessionCard {
  readonly id: number;
  readonly element: HTMLElement;
  readonly session: SessionLike;

  private readonly deps: SessionCardDeps;
  private readonly receiveAbort = new AbortController();
  private readonly messagesEl: HTMLDivElement;
  private readonly rosterEl: HTMLDivElement;
  private stopParticipantPolling: (() => void) | undefined;
  private stopped = false;

  constructor(deps: SessionCardDeps) {
    this.deps = deps;
    this.id = deps.id;
    this.session = deps.session;

    const { element, messagesEl, rosterEl } = this.render();
    this.element = element;
    this.messagesEl = messagesEl;
    this.rosterEl = rosterEl;

    this.startReceiveLoop();
    void this.refreshRoster();
    this.stopParticipantPolling = startSessionParticipantPolling(
      () => (this.stopped ? undefined : this.session),
      this.rosterEl,
      () => this.stopped,
      this.deps.logError,
    );
  }

  private render(): {
    element: HTMLElement;
    messagesEl: HTMLDivElement;
    rosterEl: HTMLDivElement;
  } {
    const config = this.session.config();
    const isGroup = config.sessionType === SessionType.Group;
    const mls = Boolean(config.mlsSettings);

    let title = "session";
    try {
      title = `${this.session.source().toString()} -> ${this.session
        .destination()
        .toString()}`;
    } catch {
      // Session accessors can throw if the session was already dropped.
    }

    const card = document.createElement("article");
    card.className = "card";

    const header = document.createElement("div");
    header.className = "card-head";
    header.innerHTML = `
      <div class="card-title" title="${title}">${title}</div>
      <div class="card-badges">
        <span class="badge badge-ws">WebSocket</span>
        <span class="badge ${isGroup ? "badge-group" : "badge-p2p"}">${isGroup ? "Multicast" : "Unicast"}</span>
        <span class="badge ${mls ? "badge-mls" : "badge-plain"}">${mls ? "MLS" : "No MLS"}</span>
        <span class="badge badge-origin">${this.deps.origin === "created" ? "moderator" : "invited"}</span>
      </div>`;

    const rosterEl = document.createElement("div");
    rosterEl.className = "roster";
    rosterEl.textContent = "participants: ...";

    const canInvite =
      this.deps.origin === "created" && isGroup && Boolean(this.deps.onInvite);
    let inviteRow: HTMLFormElement | undefined;
    if (canInvite) {
      inviteRow = document.createElement("form");
      inviteRow.className = "invite-row";
      inviteRow.innerHTML = `
        <input type="text" placeholder="Invite org/namespace/name" autocomplete="off" />
        <button type="submit">Invite</button>`;
      const inviteInput = inviteRow.querySelector("input") as HTMLInputElement;
      const inviteButton = inviteRow.querySelector(
        "button",
      ) as HTMLButtonElement;
      inviteRow.addEventListener("submit", (event) => {
        event.preventDefault();
        const name = inviteInput.value.trim();
        if (!name) return;
        void this.invite(name, inviteInput, inviteButton);
      });
    }

    const messagesEl = document.createElement("div");
    messagesEl.className = "messages";

    const form = document.createElement("form");
    form.className = "send-row";
    form.innerHTML = `
      <input type="text" placeholder="Message for this session" autocomplete="off" />
      <button type="submit">Send</button>`;
    const input = form.querySelector("input") as HTMLInputElement;
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      input.value = "";
      void this.send(text);
    });

    const footer = document.createElement("div");
    footer.className = "card-foot";
    const closeButton = document.createElement("button");
    closeButton.type = "button";
    closeButton.className = "ghost small";
    closeButton.textContent = "Close session";
    closeButton.addEventListener("click", () => {
      closeButton.disabled = true;
      void this.deps.onClose(this.id);
    });
    footer.appendChild(closeButton);

    if (inviteRow) {
      card.append(header, rosterEl, inviteRow, messagesEl, form, footer);
    } else {
      card.append(header, rosterEl, messagesEl, form, footer);
    }
    return { element: card, messagesEl, rosterEl };
  }

  private async invite(
    name: string,
    input: HTMLInputElement,
    button: HTMLButtonElement,
  ): Promise<void> {
    if (!this.deps.onInvite) return;
    button.disabled = true;
    try {
      await this.deps.onInvite(this.id, name);
      input.value = "";
      await this.refreshRoster();
    } catch (error) {
      this.deps.logError(`Session #${this.id} invite failed`, error);
    } finally {
      button.disabled = false;
    }
  }

  private startReceiveLoop(): void {
    const { signal } = this.receiveAbort;
    const currentSession = this.session;

    void (async () => {
      while (!this.stopped && !signal.aborted) {
        try {
          const received = await currentSession.getMessageAsync(1_000, {
            signal,
          });
          if (!signal.aborted && !this.stopped) {
            this.renderReceived(received);
            void this.refreshRoster();
          }
        } catch (error) {
          if (signal.aborted || this.stopped) return;
          if (isReceiveTimeout(error)) continue;
          this.deps.logError(
            `Session #${this.id} receive loop stopped`,
            error,
          );
          this.deps.log(`Session #${this.id} ended: ${describeError(error)}`);
          return;
        }
      }
    })();
  }

  private renderReceived(received: ReceivedMessage): void {
    const source = received.context.sourceName.toString();
    const text = decoder.decode(received.payload);
    this.appendMessage(source, text, false);
    this.deps.log(
      `Session #${this.id}: received ${received.payload.byteLength} bytes from ${source}`,
    );
  }

  private async send(text: string): Promise<void> {
    try {
      await this.session.publishAndWaitAsync(
        toArrayBuffer(encoder.encode(text)),
        "text/plain",
        undefined,
      );
      this.appendMessage("you", text, true);
    } catch (error) {
      this.deps.logError(`Session #${this.id} publish failed`, error);
    }
  }

  private appendMessage(source: string, text: string, mine: boolean): void {
    const row = document.createElement("div");
    row.className = `message ${mine ? "mine" : "theirs"}`;
    const who = document.createElement("span");
    who.className = "message-who";
    who.textContent = source;
    const body = document.createElement("span");
    body.className = "message-body";
    body.textContent = text;
    row.append(who, body);
    this.messagesEl.appendChild(row);
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
  }

  private async refreshRoster(): Promise<void> {
    if (this.stopped) return;
    await refreshSessionRoster(this.session, this.rosterEl);
  }

  /** Stop the receive loop without touching the underlying session. */
  stop(): void {
    this.stopped = true;
    this.stopParticipantPolling?.();
    this.stopParticipantPolling = undefined;
    this.receiveAbort.abort();
  }
}
