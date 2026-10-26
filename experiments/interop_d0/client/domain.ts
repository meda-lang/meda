/** Pure application validation. This establishes agreement with supplied evidence,
 * not factual truth or remote authority. */
export interface Fact {
  readonly id: string;
  readonly value: string;
}

export interface Evidence {
  readonly documentId: string;
  readonly revision: number;
  readonly facts: readonly Fact[];
}

export interface Report {
  readonly documentId: string;
  readonly revision: number;
  readonly selected: readonly Fact[];
}

export function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
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
      !boundedText(value.id) || value.id.length === 0 || !boundedText(value.value)) {
    return null;
  }
  return Object.freeze({id: value.id, value: value.value});
}

export function decodeIds(value: unknown): readonly string[] | null {
  if (!Array.isArray(value) || value.length > 32 ||
      !value.every((id: unknown) => boundedText(id) && id.length > 0)) return null;
  const ids: string[] = value;
  if (new Set(ids).size !== ids.length) return null;
  return Object.freeze([...ids]);
}

export function decodeEvidence(value: unknown, documentId: string): Evidence | null {
  if (!record(value) || !exactKeys(value, ["documentId", "revision", "facts"]) ||
      value.documentId !== documentId || !boundedText(value.documentId) ||
      value.revision !== 1 || !Array.isArray(value.facts) || value.facts.length > 32) {
    return null;
  }
  const facts: Fact[] = [];
  for (const raw of value.facts) {
    const item = fact(raw);
    if (item === null || facts.some((prior) => prior.id === item.id)) return null;
    facts.push(item);
  }
  return Object.freeze({documentId: value.documentId, revision: value.revision,
    facts: Object.freeze(facts)});
}

export function validateReport(
  value: unknown, evidence: Evidence, includeIds: readonly string[],
): Report | null {
  if (!record(value) || !exactKeys(value, ["documentId", "revision", "selected"]) ||
      value.documentId !== evidence.documentId || value.revision !== evidence.revision ||
      !Array.isArray(value.selected) || value.selected.length !== includeIds.length ||
      decodeIds(includeIds) === null) return null;
  const selected: Fact[] = [];
  for (let i = 0; i < includeIds.length; i += 1) {
    const item = fact(value.selected[i]);
    const expected = evidence.facts.find((candidate) => candidate.id === includeIds[i]);
    if (item === null || expected === undefined || item.id !== expected.id ||
        item.value !== expected.value) return null;
    selected.push(item);
  }
  return Object.freeze({documentId: evidence.documentId, revision: evidence.revision,
    selected: Object.freeze(selected)});
}
