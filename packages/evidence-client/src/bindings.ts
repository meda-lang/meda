import {decodeEvidence, record, type Evidence} from "./schema";

declare const taskRefBrand: unique symbol;
/** No constructor or token observer is exported. The runtime membership check is
 * essential: TypeScript casts alone cannot mint authority. */
export interface TaskRef { readonly [taskRefBrand]: true }

export type RemoteOutcome = "NotStarted" | "Completed" | "Unknown";
export type ErrorCode = "AuthorityDenied" | "BindingChanged" | "BudgetDenied" |
  "Timeout" | "ProtocolRejected" | "ResponseLimit" | "UnsupportedRemoteState" |
  "TransportFailure" | "RootTerminated" | "InvalidReference" | "CleanupFailure" |
  "TaskNotCancelable";
export interface HostError {
  readonly kind: "Error";
  readonly code: ErrorCode;
  readonly remoteOutcome: RemoteOutcome;
  readonly fatal: boolean;
}
export type TaskState = "Submitted" | "Working" | "InputRequired" | "AuthRequired" |
  "Completed" | "Failed" | "Canceled" | "Rejected";
export interface Task {
  readonly kind: "Task";
  readonly ref: TaskRef;
  readonly state: TaskState;
  readonly artifact?: unknown;
}
export interface DirectReply { readonly kind: "DirectReply" }
export type TaskResult = Task | DirectReply | HostError;
export type EvidenceResult = {readonly kind: "Evidence"; readonly value: Evidence} | HostError;
export type Operation = "readEvidence" | "submit" | "observe" | "provideInput" | "cancel";
export type Exchange = (operation: Operation, args: Readonly<Record<string, unknown>>) => Promise<unknown>;

export interface HostApi {
  readEvidence(documentId: string): Promise<EvidenceResult>;
  submit(evidence: Evidence, includeIds?: readonly string[]): Promise<TaskResult>;
  observe(ref: TaskRef): Promise<TaskResult>;
  provideInput(ref: TaskRef, includeIds: readonly string[]): Promise<TaskResult>;
  cancel(ref: TaskRef): Promise<TaskResult>;
}

const codes: readonly ErrorCode[] = ["AuthorityDenied", "BindingChanged", "BudgetDenied",
  "Timeout", "ProtocolRejected", "ResponseLimit", "UnsupportedRemoteState",
  "TransportFailure", "RootTerminated", "InvalidReference", "CleanupFailure", "TaskNotCancelable"];
const states: readonly TaskState[] = ["Submitted", "Working", "InputRequired", "AuthRequired",
  "Completed", "Failed", "Canceled", "Rejected"];

function oneOf<T extends string>(value: unknown, options: readonly T[]): value is T {
  return typeof value === "string" && options.some((option) => option === value);
}

export function bindingError(code: ErrorCode, remoteOutcome: RemoteOutcome = "NotStarted",
  fatal = false): HostError {
  return Object.freeze({kind: "Error", code, remoteOutcome, fatal});
}

function decodeError(value: unknown): HostError | null {
  if (!record(value) || value.kind !== "Error" || !oneOf(value.code, codes) ||
      !oneOf(value.remoteOutcome, ["NotStarted", "Completed", "Unknown"] as const) ||
      (value.fatal !== undefined && typeof value.fatal !== "boolean")) return null;
  return bindingError(value.code, value.remoteOutcome, value.fatal === true);
}

export function createBindings(exchange: Exchange): {readonly host: HostApi; close(): void} {
  let active = true;
  let tokens = new WeakMap<object, string>();
  const issued = new Map<string, TaskRef>();

  function taskResult(value: unknown): TaskResult {
    const error = decodeError(value);
    if (error !== null) return error;
    if (!record(value)) return bindingError("ProtocolRejected", "Unknown");
    if (value.kind === "DirectReply") return Object.freeze({kind: "DirectReply"});
    if (value.kind !== "Task" || typeof value.ref !== "string" ||
        value.ref.length === 0 || value.ref.length > 1024 || !oneOf(value.state, states)) {
      return bindingError("ProtocolRejected", "Unknown");
    }
    let ref = issued.get(value.ref);
    if (ref === undefined) {
      ref = Object.freeze({}) as TaskRef;
      tokens.set(ref, value.ref);
      issued.set(value.ref, ref);
    }
    const base = {kind: "Task" as const, ref, state: value.state};
    return Object.freeze(Object.hasOwn(value, "artifact") ? {...base, artifact: value.artifact} : base);
  }

  async function invoke(operation: Operation, args: Readonly<Record<string, unknown>>): Promise<unknown> {
    if (!active) return bindingError("RootTerminated", "NotStarted", true);
    const response = await exchange(operation, args);
    return active ? response : bindingError("RootTerminated", "Unknown", true);
  }

  async function withRef(operation: "observe" | "provideInput" | "cancel", ref: TaskRef,
    extra: Readonly<Record<string, unknown>> = {}): Promise<TaskResult> {
    if (!active) return bindingError("InvalidReference");
    const token = typeof ref === "object" && ref !== null ? tokens.get(ref) : undefined;
    if (token === undefined) return bindingError("InvalidReference");
    return taskResult(await invoke(operation, {...extra, ref: token}));
  }

  const host: HostApi = Object.freeze({
    async readEvidence(documentId: string): Promise<EvidenceResult> {
      const raw = await invoke("readEvidence", {documentId});
      const error = decodeError(raw);
      if (error !== null) return error;
      const value = record(raw) && raw.kind === "Evidence" ? decodeEvidence(raw.value, documentId) : null;
      return value === null ? bindingError("ProtocolRejected", "Unknown") : Object.freeze({kind: "Evidence", value});
    },
    async submit(evidence: Evidence, includeIds?: readonly string[]): Promise<TaskResult> {
      return taskResult(await invoke("submit", includeIds === undefined ? {evidence} : {evidence, includeIds}));
    },
    observe: (ref: TaskRef) => withRef("observe", ref),
    provideInput: (ref: TaskRef, includeIds: readonly string[]) => withRef("provideInput", ref, {includeIds}),
    cancel: (ref: TaskRef) => withRef("cancel", ref),
  });

  return {host, close(): void { active = false; tokens = new WeakMap(); issued.clear(); }};
}
