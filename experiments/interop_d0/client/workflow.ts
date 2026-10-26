import {type HostApi, type ErrorCode, type RemoteOutcome, type HostError, type TaskResult} from "./bindings";
import {decodeIds, record, validateReport, type Report} from "./domain";

export interface WorkflowInput {
  readonly documentId: string;
  readonly includeIds: readonly string[];
  readonly requestClarification: boolean;
  readonly suppliedInput?: readonly string[];
  readonly cancelAfterSubmit: boolean;
}
export type ApplicationOutcome = "Success" | "NeedsInput" | "DomainRejected" |
  "AuthorizationRequired" | "RemoteFailed" | "RemoteCanceled" | "RemoteRejected" |
  "UnsupportedReply" | "PollLimit" | ErrorCode;
export interface ApplicationResult {
  readonly outcome: ApplicationOutcome;
  readonly report?: Report;
  readonly remoteOutcome?: RemoteOutcome;
  readonly fatal?: boolean;
}

export function decodeInput(value: unknown): WorkflowInput | null {
  if (!record(value) || Object.keys(value).some((key) => !["documentId", "includeIds",
    "requestClarification", "suppliedInput", "cancelAfterSubmit"].includes(key))) return null;
  const documentId = value.documentId ?? "evidence-42";
  const includeIds = decodeIds(value.includeIds ?? ["f1", "f2"]);
  const suppliedInput = value.suppliedInput === undefined ? undefined : decodeIds(value.suppliedInput);
  if (typeof documentId !== "string" || documentId.length === 0 || [...documentId].length > 256 ||
      includeIds === null || suppliedInput === null ||
      (value.requestClarification !== undefined && typeof value.requestClarification !== "boolean") ||
      (value.cancelAfterSubmit !== undefined && typeof value.cancelAfterSubmit !== "boolean")) return null;
  return Object.freeze({documentId, includeIds, requestClarification: value.requestClarification === true,
    cancelAfterSubmit: value.cancelAfterSubmit === true,
    ...(suppliedInput === undefined ? {} : {suppliedInput})});
}

function errorResult(error: HostError): ApplicationResult {
  return {outcome: error.code, remoteOutcome: error.remoteOutcome, fatal: error.fatal};
}

function unreachable(value: never): never {
  throw new Error("Unreachable task state");
}

export async function runWorkflow(host: HostApi, input: WorkflowInput): Promise<ApplicationResult> {
  const evidence = await host.readEvidence(input.documentId);
  if (evidence.kind === "Error") return errorResult(evidence);
  let selectedIds = input.includeIds;
  let task: TaskResult = await host.submit(evidence.value,
    input.requestClarification ? undefined : selectedIds);
  let polls = 0;
  let continued = false;
  let cancelRequested = false;

  for (;;) {
    if (task.kind === "Error") return errorResult(task);
    if (task.kind === "DirectReply") return {outcome: "UnsupportedReply"};

    if (input.cancelAfterSubmit && !cancelRequested &&
        ["Submitted", "Working", "InputRequired", "AuthRequired"].includes(task.state)) {
      cancelRequested = true;
      task = await host.cancel(task.ref);
      continue;
    }

    switch (task.state) {
      case "Completed": {
        const report = validateReport(task.artifact, evidence.value, selectedIds);
        return report === null ? {outcome: "DomainRejected"} : {outcome: "Success", report};
      }
      case "Failed": return {outcome: "RemoteFailed"};
      case "Canceled": return {outcome: "RemoteCanceled"};
      case "Rejected": return {outcome: "RemoteRejected"};
      case "AuthRequired": return {outcome: "AuthorizationRequired"};
      case "InputRequired":
        if (continued || input.suppliedInput === undefined) return {outcome: "NeedsInput"};
        continued = true;
        selectedIds = input.suppliedInput;
        task = await host.provideInput(task.ref, selectedIds);
        break;
      case "Submitted":
      case "Working":
        if (polls >= 3) return {outcome: "PollLimit"};
        polls += 1;
        task = await host.observe(task.ref);
        break;
      default: return unreachable(task.state);
    }
  }
}
