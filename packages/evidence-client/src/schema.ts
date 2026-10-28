/** Fixed evidence/report profile shapes. Domain relationships stay in application code. */
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
  return typeof value === "string" && value.length > 0 && [...value].length <= 256 &&
    !/[\uD800-\uDFFF]/u.test(value);
}

function fact(value: unknown): Fact | null {
  if (!record(value) || !exactKeys(value, ["id", "value"]) ||
      !boundedText(value.id) || value.id.length === 0 || !boundedText(value.value)) {
    return null;
  }
  return Object.freeze({id: value.id, value: value.value});
}

export function decodeIds(value: unknown): readonly string[] | null {
  if (!Array.isArray(value) || value.length === 0 || value.length > 32 ||
      !value.every((id: unknown) => boundedText(id) && id.length > 0)) return null;
  const ids: string[] = value;
  if (new Set(ids).size !== ids.length) return null;
  return Object.freeze([...ids]);
}

export function decodeEvidence(value: unknown, documentId: string): Evidence | null {
  if (!record(value) || !exactKeys(value, ["documentId", "revision", "facts"]) ||
      value.documentId !== documentId || !boundedText(value.documentId) ||
      value.revision !== 1 || !Array.isArray(value.facts) || value.facts.length === 0 || value.facts.length > 32) {
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

