"""Standalone verification scenarios for the benchmark's silent failure risks."""

import copy
from mapping import build_index, indexed_map, oracle_map, require_equal, scan_map, validate_inputs


def reject(function):
    try:
        function()
    except ValueError:
        return
    raise AssertionError("Expected a failed gate")


def main():
    model = {
        "genes": [{"id": "1", "name": "GENE_A"}, {"id": "11", "name": "GENE_B"},
                  {"id": "2_AT1", "name": "GENE_A"}],
        "reactions": [
            {"id": "nested", "gene_reaction_rule": "(1 and (11 or 2_AT1))"},
            {"id": "prefix_only", "gene_reaction_rule": "11"},
            {"id": "isoform", "gene_reaction_rule": "2_AT1"},
            {"id": "unmeasured", "gene_reaction_rule": ""},
        ],
    }
    rows = [{"analysis_id": "a", "gene": "GENE_A"}, {"analysis_id": "b", "gene": "GENE_B"},
            {"analysis_id": "b", "gene": "MISSING"}]
    validate_inputs(rows, model)
    baseline = scan_map(rows, model)
    require_equal(baseline, indexed_map(rows, build_index(model)))
    require_equal(baseline, oracle_map(rows, model))
    assert baseline[0][2] == ("isoform", "nested")  # exact IDs, multiple model IDs per symbol
    assert baseline[2][2] == ()                  # unmatched row retained
    reject(lambda: require_equal(baseline, baseline[:-1]))
    altered = copy.deepcopy(baseline)
    altered[0] = ("a", "GENE_A", ("isoform", "prefix_only"))  # same count, different identities
    reject(lambda: require_equal(baseline, altered))
    reject(lambda: validate_inputs([], model))
    reject(lambda: validate_inputs(rows + rows[:1], model))
    invalid = copy.deepcopy(model)
    invalid["reactions"][0]["gene_reaction_rule"] = "UNKNOWN"
    reject(lambda: validate_inputs(rows, invalid))
    invalid = copy.deepcopy(model)
    invalid["reactions"].append(invalid["reactions"][0])
    reject(lambda: validate_inputs(rows, invalid))
    print("SCENARIOS_RUN=8")


if __name__ == "__main__":
    main()
