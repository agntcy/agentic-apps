// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

/**
 * Session roster helpers aligned with
 * slim-bindings/react-native/examples/browser/src/group-common.ts.
 */

import {
  ParticipantStatus,
  type SessionLike,
} from "@agntcy/slim-bindings-react-native/web";

import { describeError } from "./common";

export function formatParticipantNames(
  participants: Awaited<ReturnType<SessionLike["participantsListAsync"]>>,
): string[] {
  return participants.map((participant) => {
    const name = participant.name.toString();
    return participant.status === ParticipantStatus.Offline
      ? `${name} (offline)`
      : name;
  });
}

export async function refreshSessionRoster(
  session: SessionLike,
  rosterEl: HTMLElement,
  logError?: (message: string, error: unknown) => void,
): Promise<void> {
  try {
    const participants = await session.participantsListAsync();
    rosterEl.textContent = participants.length
      ? `participants: ${formatParticipantNames(participants).join(", ")}`
      : "participants: (none yet)";
  } catch (error) {
    rosterEl.textContent = "participants: (unavailable)";
    logError?.("Failed to list participants", error);
  }
}

export function logSessionSecurity(
  session: SessionLike,
  log: (message: string) => void,
): void {
  const security = session.config().mlsSettings ? "MLS" : "No MLS";
  log(`Session security: ${security}`);
}

export function startSessionParticipantPolling(
  getSession: () => SessionLike | undefined,
  rosterEl: HTMLElement,
  stopWhen: () => boolean,
  logError?: (message: string, error: unknown) => void,
): () => void {
  const timer = window.setInterval(() => {
    const session = getSession();
    if (!session || stopWhen()) return;
    void refreshSessionRoster(session, rosterEl, logError);
  }, 3_000);

  return () => window.clearInterval(timer);
}

export function isReceiveTimeout(error: unknown): boolean {
  return describeError(error).toLowerCase().includes("timeout");
}
