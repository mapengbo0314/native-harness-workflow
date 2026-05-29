# Project Context (Project-Level Intent)

## Purpose
Creating a harness template system that embeds a harness of tools onto a project. Supporting engineering workflow, velocity, and more.

## Ubiquitous Language
*   **Harness:** The embedded intelligence layer (configuration, agents, hooks) added to a client repository.
*   **Intent:** The guiding values and constraints that dictate how the AI operates at the project, feature, and agent levels.
*   **Velocity:** The primary metric of success. The harness must reduce rework, prevent architectural drift, and provide immediate, accurate code generation for engineers who already know their codebase.

## Strict Invariants
*   **Single Unified Artifact:** Do not generate separate design and implementation documents. Design decisions and execution steps must be consolidated into a single, deterministic artifact.
*   **TDD First:** All feature intent must be testable. An implementation plan is only valid if it includes the criteria for a failing test (Red phase) that proves the issue/feature intent.
*   **Static Subagent Boundaries:** Subagents (like linters or security auditors) must never mutate business logic or architecture outside their strict, predefined roles.
