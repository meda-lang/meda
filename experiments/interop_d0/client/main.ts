import {createInterface} from "node:readline";
import {createBindings, type Operation} from "./bindings";
import {record} from "./domain";
import {decodeInput, runWorkflow} from "./workflow";

async function main(): Promise<void> {
  const lines = createInterface({input: process.stdin, crlfDelay: Infinity});
  const iterator = lines[Symbol.asyncIterator]();
  let requestId = 0;
  let inFlight = false;

  async function nextMessage(): Promise<unknown> {
    const next = await iterator.next();
    if (next.done || Buffer.byteLength(next.value, "utf8") > 65_536) {
      throw new Error("Invalid controller frame");
    }
    return JSON.parse(next.value) as unknown;
  }
  function emit(value: unknown): void { process.stdout.write(JSON.stringify(value) + "\n"); }

  const bindings = createBindings(async (operation: Operation, args) => {
    if (inFlight) throw new Error("Concurrent host call");
    inFlight = true;
    const id = ++requestId;
    emit({kind: "call", id, operation, arguments: args});
    const reply = await nextMessage();
    if (!record(reply) || reply.kind !== "response" || reply.id !== id || !Object.hasOwn(reply, "value")) {
      throw new Error("Invalid controller response");
    }
    inFlight = false;
    return reply.value;
  });

  try {
    const start = await nextMessage();
    const input = record(start) && start.kind === "start" ? decodeInput(start.input) : null;
    if (input === null) throw new Error("Invalid workflow input");
    const result = await runWorkflow(bindings.host, input);
    bindings.close();
    emit({kind: "finish", result});
  } catch {
    bindings.close();
    emit({kind: "finish", result: {outcome: "ProtocolRejected", remoteOutcome: requestId > 0 ? "Unknown" : "NotStarted", fatal: true}});
    process.exitCode = 1;
  } finally {
    lines.close();
    process.stdin.pause();
  }
}

void main();
