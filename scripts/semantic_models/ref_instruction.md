# Reference Semantic Model Archetype Instructions

## ARC_code_reference_expansion

**semantic_question_template**

Expand code type {code_type} range(s) {ranges} to explicit valid individual codes and labels.

**sql_template**

```sql
SELECT DISTINCT
  ref."code",
  ref."code_label",
  ref."code_type"
FROM "DKU_SOLUTION_DESIGN"."SOL_DESIGN"."PREAUTHPOC_REFERENCE_CODES" AS ref
WHERE
  ref."code_type" = '{normalized_code_type}'
  {optional_range_filter}
```

**returns**

`code, code_label, code_type`

**output_contract**

Return row-level query results only (`code`, `code_label`, `code_type`) for all matching codes.
Do not summarize, paraphrase, or collapse the rows into a narrative answer.
If no matches exist, return an empty row set.

**status_hint**

Found if reference codes exist in the requested ranges. Normalize code type to the canonical stored value before filtering. Ambiguous if requested code type naming differs from table conventions or if range endpoints are underspecified.
