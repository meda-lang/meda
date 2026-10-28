import {createBindings, type HostApi, type Operation} from "./bindings";
import {record} from "./schema";

const MAX_FRAME = 65_536;

/** One expected frame at a time. Retained input is bounded before parsing. */
class Inbox {
  private chunks: Buffer[] = [];
  private bytes = 0;
  private pending: {resolve(value: unknown): void; reject(reason: Error): void} | undefined;
  private failure: Error | undefined;
  private ended = false;
  readonly failed: Promise<never>;
  private rejectFailure!: (reason: Error) => void;

  constructor() {
    this.failed = new Promise<never>((_, reject) => { this.rejectFailure = reject; });
    // The caller races this promise once application execution starts. Avoid an
    // unhandled rejection if malformed input arrives before that point.
    void this.failed.catch(() => {});
    process.stdin.on("data", this.onData);
    process.stdin.on("end", this.onEnd);
    process.stdin.on("error", this.onError);
  }

  private fail(): void {
    if (this.failure !== undefined) return;
    this.failure = new Error("Invalid controller frame");
    const pending = this.pending;
    this.pending = undefined;
    this.chunks = [];
    this.bytes = 0;
    pending?.reject(this.failure);
    this.rejectFailure(this.failure);
    process.stdin.pause();
  }

  private onData = (chunk: Buffer | string): void => {
    if (this.failure !== undefined) return;
    const data = typeof chunk === "string" ? Buffer.from(chunk) : chunk;
    let offset = 0;
    while (offset < data.length) {
      const newline = data.indexOf(10, offset);
      const end = newline < 0 ? data.length : newline + 1;
      const length = end - offset;
      if (this.pending === undefined || this.bytes + length > MAX_FRAME) {
        this.fail();
        return;
      }
      // Copy the slice so a short retained fragment cannot retain an arbitrarily
      // large input chunk's backing allocation.
      this.chunks.push(Buffer.from(data.subarray(offset, end)));
      this.bytes += length;
      offset = end;
      if (newline >= 0) {
        const raw = Buffer.concat(this.chunks, this.bytes);
        this.chunks = [];
        this.bytes = 0;
        let value: unknown;
        try {
          value = JSON.parse(new TextDecoder("utf-8", {fatal: true}).decode(raw));
        } catch {
          this.fail();
          return;
        }
        const pending = this.pending;
        this.pending = undefined;
        pending.resolve(value);
      }
    }
  };

  private onEnd = (): void => {
    this.ended = true;
    if (this.pending !== undefined || this.bytes > 0) this.fail();
  };
  private onError = (): void => { this.fail(); };

  read(): Promise<unknown> {
    if (this.failure !== undefined) return Promise.reject(this.failure);
    if (this.pending !== undefined || this.ended) {
      this.fail();
      return Promise.reject(this.failure);
    }
    const promise = new Promise<unknown>((resolve, reject) => { this.pending = {resolve, reject}; });
    process.stdin.resume();
    return promise;
  }

  assertHealthy(): void {
    if (this.failure !== undefined) throw this.failure;
  }

  close(): void {
    process.stdin.pause();
    process.stdin.off("data", this.onData);
    process.stdin.off("end", this.onEnd);
    process.stdin.off("error", this.onError);
    this.chunks = [];
    this.bytes = 0;
    if (this.pending !== undefined) {
      const pending = this.pending;
      this.pending = undefined;
      pending.reject(new Error("Worker closed"));
    }
  }
}

function emit(value: unknown): void {
  const serialized = JSON.stringify(value);
  if (serialized === undefined || Buffer.byteLength(serialized, "utf8") + 1 > MAX_FRAME) {
    throw new Error("Invalid worker frame");
  }
  process.stdout.write(serialized + "\n");
}

/** Run one application in the stdio worker protocol owned by meda-runtime.
 * stdout is reserved for protocol frames. Credentials stay in the Python host.
 * Application code must await each host call; this profile is sequential.
 * Errors are normalized without exposing exception strings or wire references.
 */
export async function runWorker<Input, Output>(
  decodeInput: (value: unknown) => Input | null,
  application: (host: HostApi, input: Input) => Promise<Output>,
): Promise<void> {
  const inbox = new Inbox();
  let requestId = 0;
  let inFlight = false;
  let closed = false;
  let finished = false;

  const bindings = createBindings(async (operation: Operation, args) => {
    if (closed || inFlight) throw new Error("Concurrent or retired host call");
    inFlight = true;
    const id = ++requestId;
    const pending = inbox.read();
    void pending.catch(() => {});
    try {
      emit({kind: "call", id, operation, arguments: args});
      const reply = await pending;
      inbox.assertHealthy();
      if (!record(reply) || reply.kind !== "response" || reply.id !== id || !Object.hasOwn(reply, "value")) {
        throw new Error("Invalid controller response");
      }
      return reply.value;
    } finally {
      inFlight = false;
    }
  });

  try {
    const start = await inbox.read();
    inbox.assertHealthy();
    const input = record(start) && start.kind === "start" ? decodeInput(start.input) : null;
    if (input === null) throw new Error("Invalid workflow input");
    const result = await Promise.race([application(bindings.host, input), inbox.failed]);
    inbox.assertHealthy();
    if (inFlight || !record(result)) throw new Error("Invalid application completion");
    closed = true;
    bindings.close();
    emit({kind: "finish", result});
    finished = true;
  } catch {
    closed = true;
    bindings.close();
    if (!finished) {
      emit({kind: "finish", result: {outcome: "ProtocolRejected",
        remoteOutcome: requestId > 0 ? "Unknown" : "NotStarted", fatal: true}});
      finished = true;
    }
    process.exitCode = 1;
  } finally {
    closed = true;
    bindings.close();
    inbox.close();
  }
}
