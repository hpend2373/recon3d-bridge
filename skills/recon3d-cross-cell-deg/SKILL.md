---
name: recon3d-cross-cell-deg
description: Audit metabolite-mediated connections between DEG sets from two cell types using Recon3D reaction topology, GPR-aware RNA proxies, paired patient evidence, and explicit evidence limits. Use for cross-cell metabolic route searches; not for claiming flux or causal transfer from transcriptomics alone.
---

# Recon3D cross-cell DEG audit

Find short, model-permitted metabolic routes between treatment-associated transcriptional changes in two cell types. Keep observed RNA, model topology, and unmeasured transfer as separate evidence layers.

## Start by freezing the question

Record before searching:

- source and receiver cell definitions and denominators;
- patient/sample pairing, treatment contrast, and responder labels;
- DEG model and its full multiple-testing family;
- primary expression source and normalization;
- per-timepoint detection gate;
- maximum reaction events, allowed crossing count, and currency-metabolite policy;
- whether the task is discovery, a fixed-candidate audit, or completeness check.

If unspecified, use source-to-receiver paths of 1–5 directed reaction events, exactly one extracellular crossing, full-family FDR 0.05, and the default currency list in the protocol (Protocol §4). State every default. Do not choose thresholds or route length after seeing favorable candidates.

## Check whether patient-level route support is possible

DEG tables plus a model JSON support endpoint mapping and topology only. They do not support intermediate GPR gates or patient-level route tests unless sample-level before/after expression, positive-cell counts, normalization metadata, patient labels, and full-family tests are available.

When those inputs are absent, run the topology audit and grade results only as `observed_endpoint_pair` plus `model_permitted_route`. Never call them `RNA_supported_route` or patient-level supported.

## Reuse before rebuilding

Look for an existing Recon3D reaction registry, canonical GPR classes, sample-level GPR proxies, directed event graph, and full-family gene/GPR tests. Reuse them when their cell definitions and statistical contract match. Never refit only a favorable candidate subset.

For the full data contract, route algorithm, status vocabulary, and reporting template, follow the **Protocol** section below.

## Required workflow

1. Map assay gene symbols to model gene IDs. Report unmapped and assay-absent genes separately.
2. Parse each GPR as a Boolean expression. Evaluate transcript proxies on log2(CPM+1): `AND=min`, `OR=max`. Preserve the determinant gene at every sample.
3. Maintain two coverage modes:
   - `strict`: every native GPR component is assayed and the paired gate passes;
   - `measured_OR`: use only fully measured OR branches as a sensitivity analysis.
4. Expand each native reaction only in directions permitted by its bounds. Preserve full stoichiometry even when the path graph uses one handoff metabolite.
5. Duplicate intracellular pools by cell type. Share only explicitly extracellular metabolites. A reversible transporter does not identify the source cell.
6. Enumerate all paths within the frozen ceiling. For cross-cell routes, normally require exactly one extracellular crossing. Reject repeated reaction IDs within one cell and repeated handoff metabolites within one pool.
7. Keep no-GPR reactions in topology and label them RNA-unmeasurable. Do not convert missing coverage into zero or nonsignificance.
8. Fit patient-level paired effects. Separate common treatment effects from response-by-treatment interactions. Correct within the predeclared full gene or canonical-GPR family.
9. For complete-path tests, require every node to be evaluable. Use an intersection-union test such as `max(node P)` only when the scientific claim requires every node to change. Weight multiplicity by the represented topology count when signatures compress many paths.
10. Audit promising routes against all patient before/after values, detection counts, normalization settings, determinant switches, native direction, cosubstrates, and alternative GPR branches.

## Candidate grading

Use these labels:

- `observed_endpoint_pair`: both endpoint changes pass their declared tests; no route inference yet.
- `model_permitted_route`: directed Recon3D topology exists.
- `RNA_supported_route`: every required GPR node passes coverage and the prespecified paired test.
- `partially_measured_route`: topology exists but at least one step is no-GPR, assay-absent, or below gate.
- `unsupported_direction`: a measured required step contradicts the proposed direction or group pattern.
- `not_testable`: data do not measure enough of the route.

`RNA_supported_route` requires every required GPR node to pass the primary coverage gate and the prespecified complete-path test to pass its full-family FDR threshold. Significant endpoints alone do not satisfy this grade.

Do not promote a route because endpoints are individually significant. Shared patients, shared genes, OR determinants, and many topologically equivalent paths are not independent evidence.

## Completion output

Return:

- frozen analysis contract and denominators;
- model/reaction registry with equations, bounds, GPRs, and gene mapping;
- endpoint DEG table with full-family FDR and patient-level before/after values;
- exhaustive path inventory or an explicit statement that the search was sampled/incomplete;
- per-step coverage, determinant genes, and failure reasons;
- primary and sensitivity results kept separate;
- a verdict for every candidate metabolite or route;
- input hashes and a runnable verification check;
- a short claim ceiling stating what remains unmeasured.

Never describe RNA proxies as enzyme activity, metabolite abundance, transport, flux, mediation, or causality. A zero evaluable-path count means the route was not jointly measurable under the gate, not that biology lacks the route.

---

# Protocol: two-cell DEG to Recon3D route audit

## 1. Analysis contract

Write a machine-readable plan before route search. Minimum fields:

```yaml
source_cell: CD4
receiver_cell: HFSC
paired_unit: patient
timepoints: [before, after]
response_groups: {responders: [P1, P3], nonresponders: [P2, P5]}
primary_counts: DecontX
primary_normalization: TMM
detection_gate: {positive_cells_each_timepoint: 10, total_cells_each_timepoint: 10}
max_reaction_events: 5
extracellular_crossings: 1
coverage: strict
sensitivity: [measured_OR, raw_TMM, DecontX_CPM, raw_CPM]
search_type: discovery
```

Replace values; do not copy the example as a universal default. State whether response labels are confounded with sex, drug, batch, or another patient-level variable.

If fields are omitted and repository conventions do not resolve them, use these topology defaults: source-to-receiver direction; path lengths 1–5 directed reaction events; exactly one extracellular crossing; full-family FDR 0.05; strict coverage as primary. Use the currency list below. These defaults permit topology search, not unsupported statistical claims.

## 2. Input contracts

### Recon3D model

Use an unmodified machine-readable model containing reaction IDs, stoichiometric coefficients, bounds, GPRs, metabolite compartments, and gene-symbol mappings. Record model hash and version. Reaction IDs are not gene symbols. Reject or repair inputs missing those fields before claiming a complete audit.

### Expression table

Preferred long format:

```text
cell_type, sample, patient, status, source, gene,
count, positive_cells, total_cells, effective_library, logCPM
```

Retain raw counts for gene-level count models. GPR proxies are continuous summaries and need their own paired model.

### DEG-only fallback

If only two DEG tables and a model are available:

- map significant endpoint genes to GPR-bearing reactions;
- enumerate topology under the frozen search rules;
- report model direction, metabolites, GPR membership, and missing coverage;
- grade routes at most as `observed_endpoint_pair` and `model_permitted_route`;
- mark intermediate RNA support, determinant switches, paired gates, and complete-path significance `not_testable`.

Do not synthesize sample-level support from DEG summary statistics.

### DEG and GPR tests

At minimum retain:

```text
cell_type, feature, effect, estimate, PValue, FDR, tested_family,
P1_delta, P2_delta, P3_delta, P5_delta
```

`effect` must distinguish common treatment from response-by-treatment interaction.

## 3. Gene and GPR mapping

1. Normalize stable identifiers and symbols without guessing aliases.
2. Tokenize the native Boolean GPR. Map model IDs to symbols.
3. Canonicalize logically identical GPRs and fit each cell-type/GPR class once.
4. Evaluate sample proxies: gene value; `AND=min`; `OR=max`; recurse for nested expressions.
5. Store the determinant gene or complete AND branch for each sample.

These proxies approximate transcriptional capacity. They do not measure enzyme abundance or flux.

Use distinct coverage codes: `eligible_strict`, `eligible_measured_OR`, `no_GPR`, `assay_absent`, `incomplete_GPR`, `paired_detection_not_tested`, `tested_not_significant`, and `significant`. Never merge missing coverage into nonsignificance.

## 4. Directed event graph

For each reaction:

- add a forward event when `upper_bound > 0`;
- add a reverse event when `lower_bound < 0`;
- swap reactants and products for a reverse event;
- keep all non-chain substrates and products for later feasibility review.

Represent intracellular metabolites as `(cell_type, metabolite_id)`. Represent extracellular metabolites as one shared pool only when the model marks that compartment extracellular. Do not merge cytosolic or organellar pools across cells.

Connect directed events when the first produces and the second consumes the same compartment-correct metabolite. Use this graph only for reachability. Later inspect full stoichiometry, cosubstrates, charge, direction, and carbon or atom continuity.

### Currency policy

Freeze a list before search. Typical handoff exclusions include water, proton, phosphate, ATP/ADP/AMP, GTP/GDP/GMP, NAD(H), NADP(H), FAD(H2), CoA, oxygen, and carbon dioxide. Keep these compounds in full reaction equations.

Unless the user or project supplies another frozen list, use those compounds as default handoff exclusions. Map names to compartment-specific model IDs, record exact matches, and report unmatched names instead of silently dropping them.

Do not automatically exclude the hypothesized biology. Lactate, pyruvate, PEP, amino acids, GSH/GSSG, steroid sulfates, or nucleobases may be intended handoffs.

## 5. Search modes

### Exhaustive anchor-to-anchor search

Use source reactions whose GPR contains source-cell DEG genes and receiver reactions whose GPR contains receiver-cell DEG genes. Enumerate every path within the frozen ceiling.

By default, a DEG anchor means a gene passing the existing full-family FDR 0.05 for the requested effect. If no full-family FDR exists, label anchor selection exploratory. Five reactions means five directed native reaction events, not five metabolites or compressed graph edges. Search every length from one through the ceiling.

Required guards:

- native direction only;
- no repeated native reaction ID within the same cell;
- no repeated handoff metabolite within one pool;
- fixed extracellular crossing count;
- no phenotype-driven endpoint replacement;
- report the total searched topology count.

### Structured transfer search

Separately identify:

```text
source intracellular production
source export
receiver import
receiver intracellular use
```

Export and import must move the same chemical species through the shared extracellular pool. A no-GPR transport reaction may establish topology but cannot receive RNA support.

### Fixed-candidate audit

When endpoint genes or a metabolite are named, extract every compatible native reaction and GPR branch. Reuse existing full-family FDRs. Label the audit targeted and post hoc.

## 6. Patient-level statistics

Use patients, not cells, as replicates.

Recommended paired models:

- common treatment: patient block plus after;
- response-specific change: patient block plus after plus after-by-responder interaction.

The response main effect is usually collinear with patient blocks. Do not treat raw/corrected counts or multiple normalizations as independent cohorts.

For very small cohorts, also enumerate exact sign or response-label permutations. Report attainable P-value floor. Keep moderated model and exact permutation P values distinct.

Apply BH correction to the predeclared parent family: all tested genes, all tested canonical GPRs per analysis family, or all represented route topologies. Do not correct only shortlisted candidates.

Define patient-level support before reporting:

- with responder labels, use the response-by-treatment interaction family;
- without responder labels, use the paired common-treatment family and do not say responder-specific;
- default threshold is full-family FDR < 0.05;
- require the primary paired detection gate for every claimed endpoint or GPR node;
- show every patient's before/after value and delta;
- report exact-permutation P-value floors separately and do not require an unattainable 0.05 threshold.

If a claim requires every route node to change, use `P_path = max(P_node_1, ..., P_node_k)`. This intersection-union test does not test partial-route mechanisms. Carry topology multiplicity into correction when signatures compress equivalent paths.

## 7. Candidate ranking

Rank only after preserving failure states:

1. both endpoint interactions pass full-family FDR;
2. route direction and compartment assignment are valid;
3. all required GPR nodes pass primary gate;
4. intermediate changes match the prespecified patient pattern;
5. source/normalization sensitivity holds;
6. no sparse patient, floor value, determinant switch, or incomplete OR branch drives the result;
7. exact/permutation evidence is compatible;
8. literature supports the biochemical step in relevant cells.

Failure at step 3 means `not_testable`, not absent. Failure at steps 4–7 prevents promotion beyond exploratory model hypothesis.

## 8. Required audit outputs

Suggested files:

```text
00_analysis_contract.yaml
01_input_hashes.csv
02_reaction_registry.csv.gz
03_canonical_GPR_classes.csv
04_sample_GPR_proxies.csv.gz
05_gene_tests_full_family.csv.gz
06_GPR_tests_full_family.csv.gz
07_directed_events.json
08_path_inventory.csv.gz
09_path_node_status.csv.gz
10_candidate_verdicts.csv
11_verification.json
README.md
```

The verdict table should contain route, shared metabolite, endpoint evidence, every step's coverage, primary/sensitivity result, determinant switches, failure reason, and final grade.

Verification must independently check input hashes, nested GPR values, native bounds, reverse-event stoichiometry, metabolite production/consumption signs, crossing count, repeated reaction/handoff rules, parent-family FDR, path count, and signature multiplicity.

An exhaustive claim also requires model reaction count, searched event count, path count by length, and confirmation that no top-K, sampling, early result cap, or phenotype-driven pruning was used. Otherwise label the inventory incomplete or sampled.

## 9. Claim template

Present evidence in this order:

1. observed cell-type changes and patient-paired statistics;
2. model-permitted route through named reactions and metabolites;
3. measured and unmeasured steps;
4. claim ceiling for transfer, abundance, flux, mediation, and causality;
5. falsifying metabolite or transport experiment.

Example:

> Paired transcriptional changes were observed at both cellular endpoints. Recon3D permits a short metabolite-mediated route between them, but one transport step lacks a measurable GPR and the analysis does not establish intercellular transfer or flux. The route is therefore a testable hypothesis rather than a demonstrated mechanism.

## 10. Rinvoq repository fast path

When the user's rinvoq repository is reachable (on the user's computer: `/home/minyeop/Desktop/Minyeop/rinvoq`, via the linked-computer tools or an attached copy), inspect and reuse:

- `analysis/output2/106_Recon3D_reaction_and_transfer_census/prepare.py`: GPR parsing, proxies, masks, event graph;
- `analysis/output2/106_Recon3D_reaction_and_transfer_census/test_paths.py`: path testing;
- `analysis/output2/106_Recon3D_reaction_and_transfer_census/transfer_audit.py`: structured transfer routes;
- `analysis/output2/106_Recon3D_reaction_and_transfer_census/verify.py`: independent checks;
- `analysis/output2/110_Recon3D_five_reaction_census/`: five-event enumeration;
- `analysis/output2/114_ENO1_SULT_exhaustive_recheck/audit_all.py`: full-family FDR and dense failure-state audit;
- `analysis/output2/122_ADSK_alternatives_ABCD/audit.py`: compact fixed-candidate audit.

Reuse only when cell definitions, samples, normalization, gates, and statistical families match. If the repository is not reachable, say so and build from the model and expression inputs provided instead.

## 11. Optional Jev / Laya integration

For optional typed decision guidance, read [the integration reference](references/decision-api.md) and use the bundled `scripts/recon3d.py` CLI or `scripts/recon3d_bridge` Python library. The same HTTP client supports TypeSafe Jev and compatible Laya servers; credentials and model identifiers are provider-specific.

Use compact candidate summaries for review ordering. Keep all enumerated candidates, failed or unscored entries, resolved model IDs, probabilities, and usage. A model score does not set a route evidence grade or replace code-level topology, GPR, statistical, or exhaustive-review checks. The supplied integration code exports instructions and calls the decision API; it does not implement the scientific analysis pipeline above.
