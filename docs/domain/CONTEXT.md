# Project Context

## Purpose

This project is a workflow orchestration engine designed for managing distributed tasks. It focuses on providing an execution environment (harness) that allows for the management and tracking of various development and testing phases, as well as the generation of reports and artifacts to monitor progress. A significant aspect is the concept of "design as code" (DAC), integrating code-based design principles into the development lifecycle.

## Ubiquitous Language

*   **Harness:** Refers to the execution environment or framework that manages and runs the distributed tasks.
*   **Workflow (wf):** Indicates the system's core functionality of orchestrating a sequence of tasks.
*   **Phase:** Represents distinct stages or design phases within the project's development lifecycle.
*   **DAC (Design as Code):** A methodology where design aspects are managed and defined using code, likely for versioning, automation, and consistency.
*   **Token Efficiency:** Refers to a metric or aspect of performance related to the efficient use of "tokens" within the system, though its exact technical definition in this context is not fully elaborated.
*   **Artifacts:** Generated outputs from tests, reports, and other processes, used for tracking project progress.

## Strict Invariants

*   **Workflow Orchestration:** The system is fundamentally a workflow orchestration engine.
*   **Execution Environment (Harness):** All tasks are managed and executed within a defined harness.
*   **Design as Code (DAC):** Design principles are intended to be implemented and managed via code.
*   **Phased Development:** The project lifecycle is structured around distinct design phases.