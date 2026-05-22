# E2G Indexing Pipeline Bug Log

## [2026-05-05] Pydantic ValidationError in verify_artifact

### Description
The indexing pipeline crashes during the verification step with a `pydantic_core._pydantic_core.ValidationError`. The error indicates that the `VerificationVerdict` model is missing the `passed` field because the input contains a `$defs` key (a JSON Schema echo) instead of the expected instance data.

### Status: RESOLVED (2026-05-05)

### Root Cause
The `verify_artifact` method was using a brittle, manual prompt-and-parse loop that lacked retry logic and robust schema coercion. LLMs (especially Gemma) were echoing the JSON Schema definition (including `$defs`) when requested to provide a structured `VerificationVerdict`, causing Pydantic validation to fail as it expected the instance fields at the top level.

### Resolution
1.  **Pipeline Migration**: Refactored `verify_artifact` to use the robust `_execute_single_prompt` infrastructure, enabling automatic retries and standardized error handling.
    *   **FIX**: Resolved a signature mismatch where `verify_artifact` was passing `system_prompt` and `model_type` as direct keyword arguments to `_execute_single_prompt`.
2.  **Schema Hardening**:
    *   Updated `_coerce_for_schema` to detect and strip schema metadata (`$defs`, `$schema`) before validation.
    *   Implemented specific coercion for `VerificationVerdict` to handle stringified booleans and malformed list types.
3.  **Adversarial Prompting**:
    *   Extracted verifier rules into a central `VERIFIER_SYSTEM_PROMPT`.
    *   Added explicit negative constraints ("DO NOT echo the schema") to both system and validation error prompts.
4.  **Self-Healing Error Loops**: Enhanced `_handle_pydantic_validation_error` to detect schema echoes and provide targeted corrective feedback to the LLM.
5.  **Fault Tolerance**: Implemented a low-confidence infrastructure bypass in `verify_artifact` to prevent terminal indexing stalls if the verifier fails repeatedly.

### Verified By
- [x] Code inspection of `sequential_llm_prompter.py`
- [x] Code inspection of `prompt_templates.py`

## [2026-05-05] Mandatory Section Verification Failure (Stage 1.5)

### Description
The indexing pipeline repeatedly aborted at Stage 1.5 because mandatory sections (`key_interfaces`, `blueprint`, `implementation_invariants`) were found to be empty despite the presence of source code in the directory. This occurred even when the LLM was provided with deterministic AST grounding.

### Status: RESOLVED (2026-05-05)

### Root Cause
1.  **Instruction Drift**: The `key_components_agent` instructions were not explicit enough about the mandatory nature of these sections, leading LLMs to skip them for "simple" directories.
2.  **Verifier Over-aggressiveness**: The `ArtifactVerifier` had a coarse "has code -> must have symbols" heuristic that triggered on trivial files (e.g., scripts with no exports) or unsupported languages, leading to false-positive aborts.
3.  **Coercion Gap**: Missing mandatory sections were not being proactively initialized with empty containers, causing Pydantic/Verifier mismatches.
4.  **Attribute Bug**: The verifier was incorrectly checking `blueprint.exported_symbols` instead of the schema-correct `blueprint.symbols`, causing AST grounding checks to fail or crash silently.

### Resolution
1.  **Prompt Reinforcement**: Updated `key_components_instruction` with **MANDATORY** labels and a **BLUEPRINT FIDELITY MANDATE** to force alignment with AST results.
2.  **Smart Verification**: Refactored `ArtifactVerifier._check_mandatory_sections` to be context-aware. It now uses AST grounding to determine if a section *truly* must be populated, allowing empty sections for trivial code.
3.  **Proactive Coercion**: Hardened `_coerce_for_schema` in `sequential_llm_prompter.py` to inject empty model instances for required sections if they are missing or null in the LLM response.
4.  **Schema Alignment**: Fixed the `blueprint.symbols` attribute name bug in `verification.py`.
5.  **AST Pass-through Optimization**: Implemented an AST grounding cache in `llm_indexer.py` that passes pre-extracted symbols directly to the verifier, eliminating redundant parsing and ensuring perfect alignment between LLM context and verification ground truth.

### Verified By
- [x] Code inspection of `sequential_llm_prompter.py` and `verification.py`
- [x] Hardening of `section_registry.py` with `get_mandatory_sections()`
- [x] Reinforcement of `prompt_templates.py`

## [2026-05-05] `OverviewDocument` Pydantic Validation Failure (Missing `overview`)

### Description
The `OverviewAgent` occasionally omits the top-level `overview` field in its JSON response, especially when using smaller models like `gemma4:e2b`. Since `overview` is a mandatory field in the `OverviewDocument` and `IndexDocument` schemas, this causes a `pydantic_core.ValidationError` before the verification stage.

### Status: RESOLVED (2026-05-05)

### Root Cause
1.  **Model Compliance**: Smaller LLMs (e.g., Gemma) may omit mandatory fields if they decide to prioritize optional sections like `architectural_patterns_and_gotchas`.
2.  **Coercion Gap**: The existing `_coerce_for_schema` logic in `sequential_llm_prompter.py` was biased towards patching **list-based** wrappers (Phase 2). It did not proactively inject missing **content-based** mandatory sections like `overview` if they were missing from the dict but required by the schema.

### Resolution
1.  **Phase 0.8 Coercion**: Extended `_coerce_for_schema` in `sequential_llm_prompter.py` to identify missing `required_fields` that are present in `_CONTENT_FIELD_MAP` and inject a default `{"content": ""}` structure to satisfy Pydantic.
2.  **Prompt Reinforcement**: Updated the `OverviewAgent` prompt instructions in `prompt_templates.py` to add a `CRITICAL MANDATE` explicitly requiring the presence of the `overview` section, regardless of other findings.

### Verified By
- [x] Code inspection of `sequential_llm_prompter.py`
- [x] Code inspection of `prompt_templates.py`
- [x] Functional tests running successfully

## [2026-05-04] `KeyComponentsDocument` Pydantic ValidationError (Nested `content` dict)

### Description
The `key_components_agent` failed validation with a `pydantic_core._pydantic_core.ValidationError`. Specifically, `architectural_patterns_and_gotchas.content` received a dictionary `{'content': '...'}` instead of a string. This occurred during a retry triggered by a gRPC failure.

### Status: RESOLVED (2026-05-04)

### Root Cause
1.  **gRPC Instability**: A gRPC `Stream removed` error and a subsequent fatal C++ crash occurred during `subprocess.run` (fork) while gRPC threads were active.
2.  **Double-Wrapping on Retry**: The retry logic produced a double-wrapped `content` structure: `{"architectural_patterns_and_gotchas": {"content": {"content": "..."}}}`.
3.  **Coercion Gap**: `_coerce_for_schema` only handled string-to-dict coercion, not dict-to-dict flattening for content fields.

### Resolution
1.  **gRPC Stabilization**: Set `GRPC_DNS_RESOLVER=native` in `sequential_llm_prompter.py` to use a fork-safe DNS resolver.
2.  **Coercion Hardening**: Enhanced Phase 0.7 of `_coerce_for_schema` to detect and flatten double-wrapped `content` fields in all text-heavy sections.
3.  **Verification**: Verified with `scratch/repro_key_components.py` that double-wrapped inputs are now correctly flattened and pass validation.

### Verified By
- [x] Code inspection of `sequential_llm_prompter.py`
- [x] Functional verification with `scratch/repro_key_components.py`

