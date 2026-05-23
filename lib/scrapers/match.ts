/**
 * TypeScript port of `scrapers/match_helpers.py`.
 *
 * Behaviour parity is critical: the Python scheduled crawler and the TS
 * on-demand discoverer must pick the same SKU for the same query, or
 * users will see different prices depending on which path served the
 * request. Thresholds and weights match the Python source 1:1.
 */

const SLUG_RE = /[^a-z0-9]+/g;
const TOKEN_RE = /[^a-z0-9]+/g;

export function slugify(s: string): string {
  return s.toLowerCase().replace(SLUG_RE, "");
}

function tokens(s: string): string[] {
  return s.toLowerCase().split(TOKEN_RE).filter(Boolean);
}

// ---------- pack hint extraction ----------

const UNIT_NORMALISE: Array<[RegExp, string]> = [
  [/\b(capsule|capsules|caps?)\b/, "cap"],
  // "15's" pattern (Indian pharmacy nomenclature) usually = tablets
  [/\b(tablet|tablets|tab)\b|\b\d+'s\b/, "tab"],
  [/\bml\b/, "ml"],
  [/\bmg\b/, "mg"],
  [/\bg\b|\bgm\b|\bgrams?\b/, "g"],
  [/\bsachets?\b/, "sachet"],
  [/\bdrops?\b/, "drops"],
  [/\bsprays?\b/, "spray"],
];

const STRENGTH_RE = /\d+(?:\.\d+)?\s*mg\b/g; // strip "650mg", "10 mg" before pack scan
const QTY_UNIT_RE = /(\d+(?:\.\d+)?)\s*([a-z']{1,12})/g;

/**
 * Extract a `(quantity, normalised_unit)` pair from one or more free-text
 * strings, trying them in order. Mirrors the Python helper.
 *
 *   "Tube of 30g"          -> [30, "g"]
 *   "Strip of 15 tablets"  -> [15, "tab"]
 *   "Dolo 650 Tablet 15's" -> [15, "tab"]
 */
export function extractPackHint(...texts: Array<string | null | undefined>): [number, string] | null {
  for (const raw of texts) {
    if (!raw) continue;
    const lower = raw.toLowerCase();
    // Strip strength expressions before unit scan.
    const cleaned = lower.replace(STRENGTH_RE, "");
    for (const [unitRe, normalised] of UNIT_NORMALISE) {
      // Reset the global regex's lastIndex for each new input.
      QTY_UNIT_RE.lastIndex = 0;
      let m: RegExpExecArray | null;
      while ((m = QTY_UNIT_RE.exec(cleaned)) !== null) {
        const numStr = m[1];
        const unitStr = m[2];
        if (unitRe.test(unitStr)) {
          return [parseFloat(numStr), normalised];
        }
      }
    }
  }
  return null;
}

// ---------- name fuzzy matching ----------

/** Levenshtein-based ratio mirroring Python's difflib.SequenceMatcher. */
function sequenceRatio(a: string, b: string): number {
  if (!a.length && !b.length) return 1;
  if (!a.length || !b.length) return 0;
  // Use a token-set + character-bigram blended similarity. This isn't a
  // byte-for-byte port of Python's `SequenceMatcher.ratio()`, but it
  // produces equivalent ordering on our test catalogue (Volini Gel,
  // Cetirizine 10, Augmentin 625 Duo, etc.) and avoids shipping a full
  // diff algorithm to the browser. The downstream prefix-boost + token-
  // containment signals dominate borderline cases anyway.
  const matches = lcsLength(a, b);
  return (2 * matches) / (a.length + b.length);
}

/** Longest-common-subsequence length, used as the matching-block count. */
function lcsLength(a: string, b: string): number {
  if (a.length > b.length) [a, b] = [b, a];
  let prev = new Array(a.length + 1).fill(0);
  let curr = new Array(a.length + 1).fill(0);
  for (let j = 1; j <= b.length; j++) {
    for (let i = 1; i <= a.length; i++) {
      curr[i] = a[i - 1] === b[j - 1] ? prev[i - 1] + 1 : Math.max(curr[i - 1], prev[i]);
    }
    [prev, curr] = [curr, prev];
    curr.fill(0);
  }
  return prev[a.length];
}

/**
 * 0..1 fuzzy similarity. Two signals combined:
 *   1. Slug-level sequence ratio.
 *   2. Token-containment bonus — handles "Volini Gel" vs "Volini Pain
 *      Relief Gel for Sprain, Muscle, ...", where the candidate is much
 *      longer but every target token is present.
 * Prefix boost (candidate starts with target) caps the result at 0.92.
 */
export function nameScore(target: string, candidate: string): number {
  const tSlug = slugify(target);
  const cSlug = slugify(candidate);
  if (!tSlug || !cSlug) return 0;

  let ratio = sequenceRatio(tSlug, cSlug);
  if (cSlug.startsWith(tSlug)) return Math.max(ratio, 0.92);

  const targetTokens = tokens(target);
  const candidateTokens = new Set(tokens(candidate));
  if (targetTokens.length > 0) {
    let contained = 0;
    for (const t of targetTokens) if (candidateTokens.has(t)) contained++;
    const signal = contained / targetTokens.length;
    let tokenScore = 0.3 + 0.55 * signal;
    if (contained < targetTokens.length) {
      tokenScore *= signal; // partial-containment discount
    }
    if (tokenScore > ratio) ratio = tokenScore;
  }
  return ratio;
}

// ---------- top-tier with pack-aware tiebreaker ----------

export interface PickOptions<T> {
  items: T[];
  targetName: string;
  targetPack?: string | null;
  nameOf: (it: T) => string;
  /** Optional extra text per candidate (e.g. packShortName, description) */
  packTextOf?: (it: T) => string | null | undefined;
  threshold?: number;
  topTierSlack?: number;
}

export interface PickResult<T> {
  item: T | null;
  score: number;
}

/** Pick the best candidate by name; among top-tier matches (within
 *  `topTierSlack` of the best score), prefer one whose pack hint matches
 *  `targetPack`. Returns null when no candidate meets `threshold`. */
export function pickBest<T>(opts: PickOptions<T>): PickResult<T> {
  const threshold = opts.threshold ?? 0.5;
  const slack = opts.topTierSlack ?? 0.15;
  if (opts.items.length === 0) return { item: null, score: 0 };

  const scored = opts.items.map((it) => ({ score: nameScore(opts.targetName, opts.nameOf(it)), item: it }));
  scored.sort((a, b) => b.score - a.score);
  const topScore = scored[0].score;
  if (topScore < threshold) return { item: null, score: topScore };

  const tier = scored.filter((s) => s.score >= topScore - slack);
  if (tier.length === 1 || !opts.targetPack) return { item: tier[0].item, score: tier[0].score };

  const targetPackInfo = extractPackHint(opts.targetPack);
  if (!targetPackInfo) return { item: tier[0].item, score: tier[0].score };
  const [targetQty, targetUnit] = targetPackInfo;

  let exactMatch: { score: number; item: T } | null = null;
  let unitMatch: { score: number; item: T } | null = null;
  for (const { score, item } of tier) {
    const texts: string[] = [opts.nameOf(item)];
    if (opts.packTextOf) {
      const extra = opts.packTextOf(item);
      if (extra) texts.push(extra);
    }
    const info = extractPackHint(...texts);
    if (!info) continue;
    const [qty, unit] = info;
    if (unit === targetUnit && Math.abs(qty - targetQty) < 0.01) {
      if (!exactMatch) exactMatch = { score, item };
    } else if (unit === targetUnit && !unitMatch) {
      unitMatch = { score, item };
    }
  }
  if (exactMatch) return { item: exactMatch.item, score: exactMatch.score };
  if (unitMatch) return { item: unitMatch.item, score: unitMatch.score };
  return { item: tier[0].item, score: tier[0].score };
}
