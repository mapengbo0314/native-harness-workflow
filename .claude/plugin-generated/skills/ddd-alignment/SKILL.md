---
name: ddd-alignment
description: Align implementation with the core domain, ubiquitous language, and architectural goals using the Deterministic DDD Framework. Use when resolving domain conflicts or refining the ubiquitous language.
---

# Deterministic DDD Framework

When grilling for domain alignment, focus on these 5 core areas to avoid technical pedantry and capture high-signal logic:

1.  **Vocabulary/Ubiquitous Language**: What is the exact vocabulary the business experts use to describe this process, and are there terms that mean different things depending on who you ask?
2.  **Core Domain**: If we strip away all the supporting features, what is the single core capability that gives this project its competitive advantage or primary value?
3.  **Aggregates and Invariants**: What pieces of data must absolutely always be updated together in a single transaction to prevent the business from breaking its own rules?
4.  **Domain Events and Eventual Consistency**: When a significant action is completed in this domain, who or what else in the broader system needs to know about it, and what happens if they are unreachable?
5.  **Context Mapping**: When this system interacts with external systems or other internal teams, who dictates the shape of the data contract? (Anti-Corruption Layers, Conformist, Open Host Service).

## Usage

Invoke this skill specifically when:
- Resolving domain conflicts.
- Refining the ubiquitous language in `CONTEXT.md`.
- Aligning implementation with architectural goals.
- Performing a deep dive into domain logic.
