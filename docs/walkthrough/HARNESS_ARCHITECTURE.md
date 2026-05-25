# Agentic Harness Architecture

This document provides a visual representation of the Agentic Harness architecture, illustrating how the build-time engine (`src/harness`) mints a project and deploys an isolated runtime payload to the target workspace (e.g., `.gemini/`).

## Architectural Flow

Below is the Graphviz (DOT) representation of the system. You can render this using any standard Graphviz viewer (like [WebGraphviz](http://www.webgraphviz.com/) or Edotor).

```dot
digraph HarnessArchitecture {
    fontname="Helvetica,Arial,sans-serif"
    node [fontname="Helvetica,Arial,sans-serif", shape=box, style="rounded,filled", fillcolor="#f8f9fa", color="#dee2e6"]
    edge [fontname="Helvetica,Arial,sans-serif", color="#6c757d", fontsize=10]
    rankdir=LR;
    compound=true;

    // External Inputs
    node [fillcolor="#e9ecef", shape=cylinder]
    UserCommand [label="User / CLI Args\n(gemini harness init)", shape=ellipse, fillcolor="#d4edda"]
    DomainDoc [label="ONBOARDING_DOMAIN.md\n(Context & Invariants)"]
    Boilerplate [label="Bundled Boilerplate\n(Templates, Skills, Hooks)"]

    subgraph cluster_harness_src {
        label = "src/harness (Build-Time Engine)";
        style = "dashed";
        color = "#0056b3";
        bgcolor = "#f8f9fa";

        CLI [label="cli.py\n(Entrypoint & Config Parsing)", fillcolor="#cce5ff"]
        
        subgraph cluster_discovery {
            label = "Discovery & Telemetry";
            style = "dotted";
            DiscoveryEngine [label="discovery_engine.py\n(Tech Stack & Agent Recs)"]
            LLMClient [label="llm_client.py\n(Langfuse + Retry Wrapper)", fillcolor="#fff3cd"]
        }

        MintingEngine [label="minting_engine.py\n(Docs-as-Code Compiler)", fillcolor="#cce5ff"]
        PluginGenerator [label="plugin_generator.py\n(Payload Assembly)"]
        
        subgraph cluster_adapters {
            label = "adapters/";
            style = "dotted";
            AdapterBase [label="base.py"]
            AdapterGemini [label="gemini.py"]
            AdapterClaude [label="claude.py"]
        }
        
        DispatcherSource [label="dispatcher.py\n(Runtime Intent Router)", fillcolor="#fff3cd"]
    }

    subgraph cluster_target_workspace {
        label = "Target Workspace (e.g., .gemini/)";
        style = "solid";
        color = "#28a745";
        bgcolor = "#e8f5e9";
        
        TargetHooks [label="hooks/\n(prompt_classifier.py)"]
        TargetSkills [label="skills/\n(DDD, TDD, etc.)"]
        TargetAgents [label="agents/\n(SME, Orchestrator)"]
        
        subgraph cluster_runtime_payload {
            label = "Isolated Runtime Payload";
            style = "dashed";
            color = "#ffc107";
            TargetDispatcher [label="src/dispatcher.py\n(Matrix Routing)"]
            TargetLLMClient [label="src/llm_client.py\n(API Calls)"]
        }
    }

    // Flow Relationships
    UserCommand -> CLI [label=" triggers"]
    
    // CLI Orchestration
    CLI -> DiscoveryEngine [label=" 1. detect stack"]
    CLI -> MintingEngine [label=" 2. mint workspace"]
    
    // Dependencies
    DiscoveryEngine -> LLMClient [label=" uses"]
    MintingEngine -> PluginGenerator [label=" invokes"]
    MintingEngine -> DomainDoc [label=" parses"]
    
    // Adapter Resolution
    CLI -> AdapterBase [label=" selects"]
    AdapterBase -> AdapterGemini [style="dashed", dir="back"]
    AdapterBase -> AdapterClaude [style="dashed", dir="back"]
    MintingEngine -> AdapterBase [label=" requests tool syntax"]

    // Generation & Injection
    PluginGenerator -> Boilerplate [label=" reads"]
    PluginGenerator -> TargetHooks [label=" templates & copies"]
    PluginGenerator -> TargetSkills [label=" copies"]
    PluginGenerator -> TargetAgents [label=" synthesizes & copies"]
    
    // The Runtime Payload Extraction
    PluginGenerator -> TargetDispatcher [label=" copies"]
    PluginGenerator -> TargetLLMClient [label=" copies"]
    DispatcherSource -> TargetDispatcher [style="dotted", label=" source"]
    LLMClient -> TargetLLMClient [style="dotted", label=" source"]
    
    // Runtime Execution (Conceptual)
    TargetHooks -> TargetDispatcher [label=" calls on user prompt", color="#dc3545", fontcolor="#dc3545"]
    TargetDispatcher -> TargetLLMClient [label=" classifies intent", color="#dc3545", fontcolor="#dc3545"]
}
```

## Component Breakdown

### 1. Build-Time Engine (`src/harness`)
This is the compiler phase. It is responsible for reading the user's codebase, analyzing constraints, and minting the target environment.
- **`cli.py`**: The main entrypoint that orchestrates the setup phases.
- **`discovery_engine.py`**: Analyzes the tech stack and proposes specialized agents.
- **`minting_engine.py`**: Converts human-readable `ONBOARDING_DOMAIN.md` files into strict machine configurations.
- **`plugin_generator.py`**: Assembles the files, resolves templates, and writes the output.
- **`adapters/`**: Abstracts platform-specific syntax (e.g., Gemini vs. Claude subagent invocation).

### 2. Isolated Runtime Payload (Target Workspace)
During generation, the harness explicitly copies a subset of itself into the target workspace (e.g., `.gemini/src/`).
- **`dispatcher.py`**: Intercepts user prompts and performs Matrix Routing (classifying intents into Bug Fix, Feature Request, etc.).
- **`llm_client.py`**: Handles resilient API calls and telemetry (Langfuse) for the dispatcher.

This isolation ensures that the active AI environment remains lightweight and strictly decoupled from the heavy build-time parsing logic.
