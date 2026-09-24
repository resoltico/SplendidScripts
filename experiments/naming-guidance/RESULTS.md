# Naming instruction comparison — audited results

24 September 2026. All experiment work is on `experiment/naming-guidance-evaluation`; no change was made to `main`.

## Selected instruction

This is the unchanged R9 candidate. Its scope includes names inside code, not just paths.

```markdown
## Purpose-based naming

Name files, directories and everything defined within them by purpose or behavior—not development status, plan steps or change history. Use precise, consistent, idiomatic names; distinguish variants by meaningful differences, not vague or promotional labels.

Retain states, stages, versions and ordering when intrinsic to the subject or required by a contract or tool. Keep implementation history in planning/history records.

Review changed names, update references when renaming, avoid unrelated churn and preserve compatibility.
```

## Audited comparison

| Condition | Core cases | Validation cases | Naming decisions | Direct-source naming |
|---|---:|---:|---:|---:|
| K7: Previous longer wording | 100/112 | 62/80 | 136/160 | 26/32 |
| M2: Medium wording | 100/112 | 60/80 | 134/160 | 26/32 |
| R9: Selected concise wording | 104/112 | 63/80 | 141/160 | 26/32 |
| T4: No-rule control | 103/112 | 54/80 | 133/160 | 24/32 |

Final comparison: 768 recorded fresh-context completions, comprising 640 single-item decisions and 128 direct Python-source outputs. Three instructions and a no-rule control were tested with Qwen2.5-1.5B-Instruct and Qwen3-4B-Instruct-2507 (Q4_K_M), using two seeds. All 640 decision responses were validly scored; all 128 direct-source outputs parsed. Generated code was not executed. A naming pass is not full functional verification.

Candidates, cases and scoring were committed before their respective inference runs. Decision order and answer positions were shuffled and paired. Models saw only one instruction and task per request. Automated scoring did not receive candidate identity. Selection used fewest core failures, then shorter wording on exact ties; validation did not select or revise the instruction. Candidate wording never changed after inference began.

## Method corrections and audit

The batched pilot had format failures and was not used to claim naming effectiveness. The atomic run fixed choice formatting but some JSON-code outputs remained serialization-confounded. A committed amendment requested source directly, retaining the same semantic tasks and replacing those JSON-code observations in final selection. This amendment followed inspection of earlier outputs: it was exploratory, not a wholly independent confirmation.

Manual audit then found a grading defect: `ProductionSoftwareDraftInvoice` was accepted for preserving `Draft` despite also embedding irrelevant product status. A documented, post-hoc correction applied across all conditions changed two R9 successes to failures. R9's source score fell from 28/32 to 26/32 and its core score from 106/112 to 104/112. The selected instruction did not change. This manual audit was unblinded; it must not be called a double-blind study.

Every condition still failed the private-helper rename case, retaining `phase2_total`. No rule eliminated all naming failures. The validation advantage over the closest longer instruction, and the core advantage over the no-rule control, were each only one observation.

All 896 atomic/direct-source responses were checked against saved scores, primary scores were recomputed, and model/runtime/source hashes were verified. Earlier raw outputs and original scores were preserved, not silently replaced.

## Scope of the conclusion

This was real model inference on GitHub Actions, not simulated reviewers or Python fixtures presented as agent trials. It was also a small, author-designed synthetic benchmark using two related compact models, fixed tasks and repeated seeds. It was not a production agent workflow, an independent double-blind experiment, or proof of statistical or universal superiority. The results support a bounded recommendation among these tested wordings. The shortest candidate was selected before and after the audit correction.

## Evidence

- Batched pilot: https://github.com/resoltico/SplendidScripts/actions/runs/35972384050
- Atomic comparison: https://github.com/resoltico/SplendidScripts/actions/runs/35972991366
- Direct-source comparison: https://github.com/resoltico/SplendidScripts/actions/runs/35974387055

The three executions produced 1,040 recorded model completions in total; only the specified 768 contribute to the final comparison. Their artifacts retain protocols, scripts, model revisions, raw requests/responses, per-check results and logs. Artifacts were configured for 14-day retention. A separately supplied evidence package contains the extracted artifacts, complete report and audit scripts.

Original archive SHA-256 values:

```text
pilot: ade98be0c7427d94a8211a0aec851829cb3cb0c8449d5b554dfeac023fe9158e
atomic: b3b190c963af1a7be8b7d5dd8d92afafd23bf737bf8dcc2d65409c96e0e4e382
source: 1a040368ffe322c4c549e64cc8d4b167ac36e387d201af621f6b1b53d0a88077
```
