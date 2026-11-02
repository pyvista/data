# Running the search as a panel of agents

One record is a solo job. For a batch (a new multi-file contribution, or a
sweep over every `LicenseRef-Unknown` record) the shape that worked is a
two-stage pipeline: researchers in groups of about six records, then one
skeptic per finding whose only job is to refute it. Of 39 findings in the
October 2026 sweep, 3 were refuted and 10 more were corrected by the skeptic
before anything touched the table.

## The brief every agent reads

Write it to a scratch file and point every prompt at it. The one below is
what was used, trimmed to the parts that mattered.

```markdown
# Research brief

You are one researcher in a panel. READ-ONLY: never edit, commit, push or
run `gh` commands that write. `curl`, `gh api -X GET`, WebSearch and
WebFetch are fine.

The table `DATASETS.toml` in <repo path> records every dataset's licence and
origin. Your records are listed in <records.json>; your group is named in
your prompt. Each record's `notes` says what the audit already tried. Do not
repeat it; go past it.

Rules the table follows (do not re-litigate, do check your finding against
them):
- A redistributor's collection licence never covers third-party work it
  merely hosts.
- A source that publishes no terms stays `LicenseRef-Unknown`; a found
  source makes `provenance = "verified"` with the origin link.
- Only terms stated by the rights holder, or a licence published beside the
  file by its author, count. A forum reply saying "sure, use it" is
  permission to include, not a licence.
- Never print patient identifiers from medical files; do not run `strings`
  over `Data/`.

For each record, try to find what was missed:
1. The origin: by filename, by distinctive strings in the notes, by image or
   model names, on GitHub code search, GitLab, Kaggle, Zenodo, figshare,
   university pages, the Wayback Machine CDX.
2. The terms: a licence page, a README beside the file at its origin, a
   dataset landing page, a journal's data-availability statement, a
   repository LICENSE that actually covers the file (its author committed
   it there).
3. Evidence the record is wrong the other way.

Verify before you claim: fetch the page, quote the sentence, give the URL
(and a Wayback capture URL when the live page is gone). Byte identity beats
a name match: `git -C <repo> cat-file blob HEAD:Data/<path> | shasum -a 256`
gives the repository file's hash.

Return one finding per record where you found something: the record name,
kind (`origin`, `terms`, `contradiction` or `nothing`), the proposed change
(field and value) or none, the evidence (URL plus quoted text), and your
confidence. Records with nothing new are `nothing` with one line on what you
tried. Stop early and return what you have if you run low on budget.
```

Budget notes from the agents are worth keeping in the schema: they are
where "GitHub search quota exhausted after six queries" and "Wayback offline
for half the session" surfaced, which told us which records deserved a
second pass.

## The workflow script

```javascript
export const meta = {
  name: 'dataset-provenance-sweep',
  description: 'Research undetermined records for missed origins or terms, then adversarially verify each finding',
  phases: [
    { title: 'Research', detail: 'one agent per group of about six records' },
    { title: 'Verify', detail: 'one skeptic per finding; must reproduce the evidence and check it against the table rules' },
  ],
}
const S = args.scratch            // directory holding BRIEF.md and records.json
const GROUPS = args.groups        // [["name", ...], ...]
const FINDINGS = { type: 'object', properties: {
  findings: { type: 'array', items: { type: 'object', properties: {
    name: { type: 'string' },
    kind: { type: 'string', enum: ['origin', 'terms', 'contradiction', 'nothing'] },
    claim: { type: 'string' }, change: { type: 'string' }, evidence: { type: 'string' },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
  }, required: ['name', 'kind', 'claim', 'change', 'evidence', 'confidence'] } },
  budget_note: { type: 'string' },
}, required: ['findings', 'budget_note'] }
const VERDICT = { type: 'object', properties: {
  refuted: { type: 'boolean' }, reason: { type: 'string' }, corrected_change: { type: 'string' },
}, required: ['refuted', 'reason', 'corrected_change'] }

const results = await pipeline(
  GROUPS,
  (names, _, i) => agent(
    `Read ${S}/BRIEF.md first and follow it exactly. Your group (${i + 1} of ${GROUPS.length}): ${names.join(', ')}. Their records are the matching entries in ${S}/records.json. At least three distinct search angles per record before returning "nothing". Persist notes to ${S}/group-${i + 1}.md as you go.`,
    { label: `research:${i + 1}`, phase: 'Research', schema: FINDINGS, effort: 'high' }),
  (res, names, i) => {
    if (!res) return []
    const real = res.findings.filter(f => f.kind !== 'nothing')
    log(`group ${i + 1}: ${real.length} findings, ${res.findings.length - real.length} nothing`)
    return parallel(real.map(f => () => agent(
      `Read ${S}/BRIEF.md (read-only rules and the table rules). A researcher claims the following about the record "${f.name}" in ${S}/records.json. Try to REFUTE it: fetch the evidence URL yourself and check the quoted text is there and means what is claimed; check the proposed change against the table rules (a redistributor's licence never covers third-party work; a forum "sure" is not a licence; only the rights holder's terms count); check byte identity where the claim rests on a name match; look for an older copy than the candidate. Return refuted=true if the evidence does not reproduce or the change would violate a rule. If it holds but the change is imprecise, return refuted=false with corrected_change.\n\nKind: ${f.kind}\nClaim: ${f.claim}\nProposed change: ${f.change}\nEvidence: ${f.evidence}\nConfidence: ${f.confidence}`,
      { label: `verify:${f.name}`, phase: 'Verify', schema: VERDICT, effort: 'high' })
      .then(v => ({ ...f, group: i + 1, verdict: v })))
    ).then(vs => ({ group: i + 1, nothing: res.findings.filter(f => f.kind === 'nothing'), budget_note: res.budget_note, verified: vs.filter(Boolean) }))
  },
)
const groups = results.filter(Boolean)
const kept = groups.flatMap(g => g.verified.filter(v => v.verdict && !v.verdict.refuted))
const dropped = groups.flatMap(g => g.verified.filter(v => !v.verdict || v.verdict.refuted))
const nothing = groups.flatMap(g => g.nothing)
log(`${kept.length} findings kept, ${dropped.length} refuted, ${nothing.length} records with nothing new`)
return { kept, dropped, nothing, budget_notes: groups.map(g => ({ group: g.group, note: g.budget_note })) }
```

Apply the kept findings by script, one exact-match replacement per edit with
an assertion that it matched exactly once, so a batch that fails partway
leaves nothing half-applied; then run the validator and its tests, and read
the field-level diff before committing. Use the skeptic's `corrected_change`
over the researcher's `change` whenever both exist.

## Things the panel needs from the session

- Read-only `gh` calls must pass whatever gate the session runs: use
  `gh api -X GET` and `-f` only with an explicit GET, so the gate can
  classify them without prompting the user mid-run.
- GitHub code search is 10 queries per minute shared across every agent;
  stagger groups or expect quota notes.
- Give each agent a scratch path to persist notes; a context cutoff then
  loses nothing, and the group files are the raw material for a second pass.
