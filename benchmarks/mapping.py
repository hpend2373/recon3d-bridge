"""Exact gene-symbol to reaction membership mapping for a stage benchmark.

This is membership in a GPR expression, not evaluation of Boolean GPR activity.
No reaction direction, route, RNA support, or biological evidence grade is inferred.
"""

from collections import defaultdict
import hashlib
import json
import re


def gene_names(model):
    names = defaultdict(set)
    for gene in model["genes"]:
        if gene.get("name"):
            names[gene["name"]].add(gene["id"])
    return names


def tokens(rule):
    return {value for value in re.findall(r"[^\s()]+", rule) if value not in {"and", "or"}}


def validate_inputs(rows, model):
    if not rows or not model.get("reactions") or not model.get("genes"):
        raise ValueError("Nonempty DEG rows, model reactions, and model genes are required")
    for field in ("genes", "reactions"):
        ids = [item["id"] for item in model[field]]
        if any(not isinstance(value, str) or not value for value in ids) or len(set(ids)) != len(ids):
            raise ValueError(f"Model {field} IDs must be unique nonempty strings")
    gene_ids = {gene["id"] for gene in model["genes"]}
    row_ids = set()
    for row in rows:
        if not row.get("analysis_id") or not row.get("gene"):
            raise ValueError("Every DEG row requires analysis_id and gene")
        key = (row["analysis_id"], row["gene"])
        if key in row_ids:
            raise ValueError("Duplicate analysis_id/gene input rows")
        row_ids.add(key)
    for reaction in model["reactions"]:
        rule = reaction.get("gene_reaction_rule", "")
        if not isinstance(rule, str):
            raise ValueError("GPR rules must be text")
        if tokens(rule) - gene_ids:
            raise ValueError("GPR contains a gene ID not declared in the model")


def scan_map(rows, model):
    """Reference: repeated scans of every reaction for each mapped DEG row.

    This is a newly implemented reference baseline, not an archived prototype.
    Symbol lookup uses exact model gene names; no alias inference is performed.
    """
    names = gene_names(model)
    result = []
    for row in rows:
        ids = names.get(row["gene"], set())
        hits = []
        if ids:
            expression = "|".join(re.escape(value) for value in sorted(ids))
            pattern = re.compile(r"(?<![\w.:-])(?:" + expression + r")(?![\w.:-])")
            for reaction in model["reactions"]:
                if pattern.search(reaction.get("gene_reaction_rule", "")):
                    hits.append(reaction["id"])
        result.append((row["analysis_id"], row["gene"], tuple(sorted(hits))))
    return result


def build_index(model):
    by_gene = defaultdict(set)
    for reaction in model["reactions"]:
        for gene_id in tokens(reaction.get("gene_reaction_rule", "")):
            by_gene[gene_id].add(reaction["id"])
    return gene_names(model), by_gene


def indexed_map(rows, index):
    names, by_gene = index
    result = []
    for row in rows:
        hits = set()
        for gene_id in names.get(row["gene"], set()):
            hits.update(by_gene.get(gene_id, set()))
        result.append((row["analysis_id"], row["gene"], tuple(sorted(hits))))
    return result


def oracle_map(rows, model):
    """Independent literal-token oracle, without regex or an inverted index."""
    result = []
    for row in rows:
        ids = {gene["id"] for gene in model["genes"] if gene.get("name") == row["gene"]}
        hits = []
        for reaction in model["reactions"]:
            literal_tokens = reaction.get("gene_reaction_rule", "").replace("(", " ").replace(")", " ").split()
            if any(token in ids for token in literal_tokens):
                hits.append(reaction["id"])
        result.append((row["analysis_id"], row["gene"], tuple(sorted(hits))))
    return result


def require_equal(reference, candidate):
    if candidate != reference:
        raise ValueError("Mapping mismatch: row identities or exact reaction memberships differ")


def output_digest(result):
    return hashlib.sha256(json.dumps(result, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
