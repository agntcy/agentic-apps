// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

/**
 * Shared SLIM browser (WASM) helpers aligned with
 * slim-bindings/react-native/examples/browser/src/common.ts.
 */

import {
  Direction,
  Name,
  Service,
  uniffiInitAsync,
  type AppLike,
  type NameLike,
  type ServiceLike,
} from "@agntcy/slim-bindings-react-native/web";

export const DEFAULT_ENDPOINT = "ws://127.0.0.1:46357";
export const DEFAULT_SHARED_SECRET = "test-shared-secret-value-0123456789abcdef";

let wasmReady = false;

export function splitId(id: string): NameLike {
  const parts = id.split("/");
  if (parts.length !== 3) {
    throw new Error(
      `IDs must be in the format organization/namespace/app-or-stream, got: ${id}`,
    );
  }
  return Name.fromString(id);
}

export async function initializeWasm(): Promise<void> {
  if (wasmReady) return;
  await uniffiInitAsync();
  wasmReady = true;
}

export function isWasmReady(): boolean {
  return wasmReady;
}

export type ConnectOptions = {
  endpoint: string;
  localId: string;
  sharedSecret: string;
  token?: string;
};

export type ConnectedApp = {
  app: AppLike;
  service: ServiceLike;
  connId: bigint;
};

export async function createAndConnectApp(
  options: ConnectOptions,
): Promise<ConnectedApp> {
  await initializeWasm();

  const local = splitId(options.localId);
  const serviceId = options.localId.replace(/[^A-Za-z0-9_-]/g, "-");
  const service = new Service(serviceId);
  const connId = await service.connectAsync(
    options.endpoint.trim(),
    options.token?.trim() || undefined,
  );
  const app = await service.createAppWithDirectionAsync(
    local,
    options.sharedSecret,
    Direction.Bidirectional,
  );
  await app.subscribeAsync(local, connId);

  return { app, service, connId };
}

export function describeError(error: unknown): string {
  if (typeof error === "object" && error !== null) {
    const uniffiError = error as {
      tag?: unknown;
      inner?: { message?: unknown };
    };
    if (typeof uniffiError.inner?.message === "string") {
      const tag =
        typeof uniffiError.tag === "string" ? `${uniffiError.tag}: ` : "";
      return `${tag}${uniffiError.inner.message}`;
    }
  }
  if (error instanceof Error) return error.message;
  return String(error);
}

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function toArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  return bytes.slice().buffer as ArrayBuffer;
}

/** Parse comma- or whitespace-separated invitee names. */
export function parseInviteList(raw: string): string[] {
  return raw
    .split(/[\s,]+/)
    .map((value) => value.trim())
    .filter((value) => value.length > 0);
}

export function parseInviteNames(raw: string, exclude?: string): NameLike[] {
  const seen = new Set<string>();
  const names: NameLike[] = [];
  for (const value of parseInviteList(raw)) {
    if (!value || value === exclude || seen.has(value)) continue;
    seen.add(value);
    names.push(splitId(value));
  }
  return names;
}
