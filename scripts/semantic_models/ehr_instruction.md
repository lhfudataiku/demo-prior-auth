# Semantic Model Archetype Instructions

## ARC_observation_threshold_numeric

**semantic_question_template**

For patient {subject_id}, find observation {category_or_synonym | observation_display} where numeric value {value_numeric} within {lookback_clause}.

**sql_template**

```sql
SELECT DISTINCT
  o."subject_id",
  o."observation_id",
  o."category_code",
  o."observation_code",
  o."observation_display",
  o."value_numeric",
  o."value_text",
  o."value_unit",
  o."effective_datetime",
  o."encounter_id"
FROM "DKU_SOLUTION_DESIGN"."SOL_DESIGN"."PREAUTHPOC_OBSERVATION" AS o
WHERE 
  o."subject_id" = '{subject_id}'
  {optional_category_filter}
  {optional_observation_filter}
  {optional_numeric_filter}
  {optional_time_filter}
```

**returns**

`observation_id, encounter_id, category_code, observation_code, observation_display, value_numeric, value_unit, value_text, effective_datetime`

**status_hint**

Found if threshold condition met. When category is expressed in natural language, map it to the canonical category_code or a small OR-list of equivalent category_code values. Use parentheses around OR conditions. Prefer canonical category codes over literal user phrasing. Ambiguous if non-numeric values or mixed units are present.

## ARC_qualitative_observation_result

**semantic_question_template**

For patient {subject_id}, find qualitative observation {category_or_synonym | observation_display} within {lookback_clause}.

**sql_template**

```sql
SELECT DISTINCT
  o."subject_id",
  o."observation_id",
  o."category_code",
  o."observation_code",
  o."observation_display",
  o."value_numeric",
  o."value_text",
  o."value_unit",
  o."effective_datetime",
  o."encounter_id"
FROM "DKU_SOLUTION_DESIGN"."SOL_DESIGN"."PREAUTHPOC_OBSERVATION" AS o
WHERE
  o."subject_id" = '{subject_id}'
  {optional_category_filter}
  {optional_observation_filter}
  {optional_time_filter}
```

**returns**

`observation_id, encounter_id, category_code, observation_code, observation_display, value_numeric, value_unit, value_text, effective_datetime`

**status_hint**

Found if a matching qualitative observation exists. Prefer observation_display or canonical category filters first. Do not filter directly on value_text in SQL because it is free text and not normalized. Downstream reasoning should inspect returned value_text values to determine whether they satisfy the qualitative criterion.

## ARC_dx_code_range_with_lookback

**semantic_question_template**

For patient {subject_id}, find diagnosis codes {ranges} within {lookback_clause}.

**sql_template**

```sql
SELECT
  c."condition_name",
  c."condition_code",
  c."condition_id",
  c."encounter_id",
  e."encounter_start_datetime"
FROM "DKU_SOLUTION_DESIGN"."SOL_DESIGN"."PREAUTHPOC_CONDITION" AS c
INNER JOIN "DKU_SOLUTION_DESIGN"."SOL_DESIGN"."PREAUTHPOC_ENCOUNTER" AS e
  ON c."encounter_id" = e."encounter_id"
  AND c."subject_id" = e."subject_id"
WHERE
  c."subject_id" = '{subject_id}'
  {optional_range_filter}
  {optional_time_filter}
```

**returns**

`condition_id, encounter_id, condition_code, condition_name, encounter_start_datetime`

**status_hint**

Found if diagnosis in requested code range exists during lookback. Expand one or more requested ranges into explicit SQL range predicates. Ambiguous if range semantics differ from lexical BETWEEN behavior or if multiple coding systems are mixed.

## ARC_demographic_age_or_gender

**semantic_question_template**

For patient {subject_id}, return age and gender.

**sql_template**

```sql
SELECT
  p."subject_id",
  p."birth_date",
  p."gender",
  DATEDIFF('year', p."birth_date", CURRENT_DATE())
    - IFF(
        DATEADD('year', DATEDIFF('year', p."birth_date", CURRENT_DATE()), p."birth_date") > CURRENT_DATE(),
        1,
        0
      ) AS "age"
FROM "DKU_SOLUTION_DESIGN"."SOL_DESIGN"."PREAUTHPOC_PATIENT" AS p
WHERE
  p."subject_id" = '{subject_id}'
```

**returns**

`subject_id, birth_date, gender, age`

**status_hint**

Found if patient exists. Compute integer age from birth_date as of CURRENT_DATE(). Ambiguous if birth_date is missing or incomplete.

## ARC_medication_exposure_presence

**semantic_question_template**

For patient {subject_id}, find medication requests matching {medication_terms_or_ndc} within {lookback_clause}.

**sql_template**

```sql
SELECT
  mr."medication_id",
  m."medication_name",
  mr."dosage_text",
  mr."med_request_id",
  mr."dose_unit",
  mr."encounter_id",
  mr."frequency_code",
  mr."order_datetime",
  mr."route_code",
  mr."dispense_start_datetime",
  mr."dispense_end_datetime",
  mr."dose_value",
  mr."subject_id"
FROM "DKU_SOLUTION_DESIGN"."SOL_DESIGN"."PREAUTHPOC_MEDICATIONREQUEST" AS mr
INNER JOIN "DKU_SOLUTION_DESIGN"."SOL_DESIGN"."PREAUTHPOC_MEDICATION" AS m
  ON mr."medication_id" = m."medication_id"
WHERE
  mr."subject_id" = '{subject_id}'
  {optional_medication_filter}
  {optional_time_filter}
```

**returns**

`med_request_id, medication_id, medication_name, dosage_text, dose_value, dose_unit, route_code, frequency_code, order_datetime, dispense_start_datetime, dispense_end_datetime, encounter_id`

**status_hint**

Found if medication request matches the requested medication term or NDC within the lookback window. Prefer canonical medication identifiers when available. Ambiguous if only partial text matching is possible or if medication name variants map to multiple products.

## ARC_medication_trial_duration

**semantic_question_template**

For patient {subject_id}, find continuous/total exposure to {medication_terms} for at least {min_days} days.

**sql_template**

```sql
SELECT
  mr."medication_id",
  m."medication_name",
  mr."dosage_text",
  mr."med_request_id",
  mr."dose_unit",
  mr."encounter_id",
  mr."frequency_code",
  mr."order_datetime",
  mr."route_code",
  mr."dispense_start_datetime",
  mr."dispense_end_datetime",
  mr."dose_value",
  mr."subject_id"
FROM "DKU_SOLUTION_DESIGN"."SOL_DESIGN"."PREAUTHPOC_MEDICATIONREQUEST" AS mr
INNER JOIN "DKU_SOLUTION_DESIGN"."SOL_DESIGN"."PREAUTHPOC_MEDICATION" AS m
  ON mr."medication_id" = m."medication_id"
WHERE
  mr."subject_id" = '{subject_id}'
  {optional_medication_filter}
ORDER BY COALESCE(mr."dispense_start_datetime", mr."order_datetime")
```

**returns**

`med_request_id, medication_id, medication_name, dosage_text, dose_value, dose_unit, route_code, frequency_code, order_datetime, dispense_start_datetime, dispense_end_datetime, encounter_id`

**status_hint**

Returns candidate medication exposure rows for downstream duration calculation. Preserve chronological ordering using dispense_start_datetime or order_datetime. Ambiguous because continuous or total exposure duration usually requires post-SQL interval logic unless explicitly modeled in SQL.

## ARC_latest_observation_snapshot

**semantic_question_template**

Show latest {category_or_synonym | observation_display} observations for patient {subject_id}.

**sql_template**

```sql
SELECT DISTINCT
  o."subject_id",
  o."observation_id",
  o."encounter_id",
  o."category_code",
  o."observation_code",
  o."category_display",
  o."observation_display",
  o."value_numeric",
  o."value_text",
  o."value_unit",
  o."effective_datetime"
FROM "DKU_SOLUTION_DESIGN"."SOL_DESIGN"."PREAUTHPOC_OBSERVATION" AS o
WHERE
  o."subject_id" = '{subject_id}'
  {optional_category_filter}
  {optional_observation_filter}
  AND o."effective_datetime" = (
    SELECT MAX(o2."effective_datetime")
    FROM "DKU_SOLUTION_DESIGN"."SOL_DESIGN"."PREAUTHPOC_OBSERVATION" AS o2
    WHERE
      o2."subject_id" = '{subject_id}'
      {optional_correlated_category_filter}
      {optional_correlated_observation_filter}
  )
```

**returns**

`observation_id, encounter_id, category_code, observation_code, category_display, observation_display, value_numeric, value_text, value_unit, effective_datetime`

**status_hint**

Found if a latest matching observation exists. When category is expressed in natural language, map it to canonical category_code values as needed. Ambiguous if multiple observations share the same latest effective_datetime.

## ARC_procedure_code_presence

**semantic_question_template**

For patient {subject_id}, find procedure codes {procedure_codes_or_ranges} (code class {code_class}) within {lookback_clause}.

**sql_template**

```sql
SELECT
  p."subject_id",
  p."procedure_id",
  p."encounter_id",
  p."code_class",
  p."procedure_code",
  p."procedure_display",
  p."procedure_datestart",
  p."procedure_dateend"
FROM "DKU_SOLUTION_DESIGN"."SOL_DESIGN"."PREAUTHPOC_PROCEDURE" AS p
WHERE
  p."subject_id" = '{subject_id}'
  {optional_code_class_filter}
  {optional_procedure_code_filter}
  {optional_time_filter}
```

**returns**

`procedure_id, encounter_id, code_class, procedure_code, procedure_display, procedure_datestart, procedure_dateend`

**status_hint**

Found if at least one procedure row matches the requested code/class/time constraints. Expand one or more requested ranges into explicit SQL range predicates. Ambiguous if coding class is unspecified, mixed, or if requested ranges cannot be represented safely with lexical BETWEEN semantics.

## ARC_encounter_timing_or_setting

**semantic_question_template**

For patient {subject_id}, return encounters matching {encounter_type | service_type | priority} within {lookback_clause}.

**sql_template**

```sql
SELECT
  e."subject_id",
  e."encounter_id",
  e."encounter_start_datetime",
  e."encounter_end_datetime",
  e."encounter_identifier",
  e."priority_code",
  e."service_type",
  e."discharge_disposition"
FROM "DKU_SOLUTION_DESIGN"."SOL_DESIGN"."PREAUTHPOC_ENCOUNTER" AS e
WHERE
  e."subject_id" = '{subject_id}'
  {optional_encounter_filter}
  {optional_time_filter}
```

**returns**

`encounter_id, encounter_start_datetime, encounter_end_datetime, encounter_identifier, priority_code, service_type, discharge_disposition`

**status_hint**

Found if encounter matches the requested class, type, service, or priority constraint within the lookback window. When type, service, or priority is expressed in natural language, map it to canonical category_code values as needed. Ambiguous if a user-facing encounter concept maps to multiple physical fields or coding systems.
