export type Snapshot = Readonly<{
  stage: string;
  observation: string;
  taskId: string;
  remaining: number;
  evidence: string;
  input: string;
}>;

export type Action = "read" | "submit" | "poll" | "continue" | "cancel" | "stop";

export type Decision = Readonly<{
  action: Action;
  taskId: string;
  payload: string;
}>;

export function next(snapshot: Snapshot): Decision {
  if (snapshot.observation === "completed") {
    return { action: "stop", taskId: snapshot.taskId, payload: snapshot.evidence };
  }
  if (snapshot.observation === "cancelled" || snapshot.observation === "denied" || snapshot.observation === "invalid" || snapshot.observation === "unknown" || snapshot.observation === "budget") {
    return { action: "stop", taskId: snapshot.taskId, payload: snapshot.observation };
  }
  if (snapshot.remaining <= 0) {
    return { action: "stop", taskId: snapshot.taskId, payload: "budget" };
  }
  if (snapshot.stage === "start") {
    return { action: "read", taskId: "", payload: "" };
  }
  if (snapshot.observation === "evidence") {
    return { action: "submit", taskId: "", payload: snapshot.evidence };
  }
  if (snapshot.observation === "pending") {
    return { action: "poll", taskId: snapshot.taskId, payload: "" };
  }
  if (snapshot.observation === "input_required") {
    if (snapshot.input === "") {
      return { action: "stop", taskId: snapshot.taskId, payload: "input_required" };
    }
    return { action: "continue", taskId: snapshot.taskId, payload: snapshot.input };
  }
  return { action: "stop", taskId: snapshot.taskId, payload: "unsupported" };
}
