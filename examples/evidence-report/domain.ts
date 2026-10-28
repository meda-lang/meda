import {decodeIds, record, type Evidence, type Fact} from "@meda/evidence-client";

export interface Report {
  readonly documentId: string;
  readonly revision: number;
  readonly selected: readonly Fact[];
}

function exactKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
  const actual = Object.keys(value);
  return actual.length === keys.length && keys.every((key) => Object.hasOwn(value, key));
}
function boundedText(value: unknown): value is string {
  return typeof value === "string" && [...value].length <= 256;
}
function fact(value: unknown): Fact | null {
  if (!record(value) || !exactKeys(value, ["id", "value"]) ||
      !boundedText(value.id) || value.id.length === 0 || !boundedText(value.value)) return null;
  return Object.freeze({id: value.id, value: value.value});
}

export function validateReport(
  value: unknown, evidence: Evidence, includeIds: readonly string[],
): Report | null {
  if (!record(value) || !exactKeys(value, ["documentId", "revision", "selected"]) ||
      value.documentId !== evidence.documentId || value.revision !== evidence.revision ||
      !Array.isArray(value.selected) || value.selected.length !== includeIds.length ||
      decodeIds(includeIds) === null) return null;
  const byId = new Map<string, Fact>();
  for (const raw of value.selected) {
    const item = fact(raw);
    if (item === null || !includeIds.includes(item.id) || byId.has(item.id)) return null;
    byId.set(item.id, item);
  }
  const selected: Fact[] = [];
  for (const id of includeIds) {
    const item = byId.get(id);
    const expected = evidence.facts.find((candidate) => candidate.id === id);
    if (item === undefined || expected === undefined ||
        item.value !== expected.value) return null;
    selected.push(item);
  }
  return Object.freeze({documentId: evidence.documentId, revision: evidence.revision,
    selected: Object.freeze(selected)});
}
