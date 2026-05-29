# Debugger Agent Design

## Part 1: Problem Understanding
We need to add a new "debugger" subagent to the project's Agentic Harness framework, based on a reference implementation from `https://github.com/VoltAgent/awesome-claude-code-subagents/blob/main/categories/04-quality-security/debugger.md`. To ensure compatibility with the project's architecture, we must adapt this agent to use the graph-first context gathering strategy (using `mcp_codegraph_*` tools) instead of basic file reading and searching tools. Furthermore, we need to implement a structured progress tracking mechanism for the debugger so that it logs its investigations in a dedicated debug directory using a date-based naming convention (`yyyy-mm-dd-{debugger-case}.md`).

## Part 2: Technical Plan
We will create a new template file for the debugger agent in the `src/harness/templates/boilerplate/agents/` directory. This file will define the agent's identity, system instructions, and toolset (omitting the model definition from the reference). To fit into our existing ecosystem, we will adapt the agent's toolset to use our project's specific code graph tools (like `mcp_codegraph_codegraph_search` and `mcp_codegraph_codegraph_context`) instead of standard file reading tools. We will also embed specific instructions in the agent's prompt requiring it to track its debugging progress in a dedicated file. This progress file will be stored in the harness's debug directory (using the platform-agnostic `<!--$HARNESS_DIR$-->/debug/` path) and will follow the `yyyy-mm-dd-{debugger-case}.md` naming convention. The agent will be fully onboarded for both Gemini and Claude environments.

## Part 3: Alternatives
1. **Retaining Standard Tools:** We considered keeping the default file reading and searching tools as defined in the original GitHub template. We ruled this out because it violates the project's Core Mandate for the Agentic Harness, which strictly requires a "Graph-First Strategy" utilizing the `mcp_codegraph_*` tools for better context efficiency.
2. **Hardcoding Paths:** We considered hardcoding the progress tracking directory to `.gemini/debug/`. We ruled this out because it would break compatibility for Claude users. Instead, we will use the dynamic `<!--$HARNESS_DIR$-->/debug/` placeholder, which the harness will correctly resolve to `.gemini/debug/` or `.claude/debug/` as appropriate.

## Part 4: Detailed Implementation Plan
1. **Create: `src/harness/templates/boilerplate/agents/debugger.md`**
   - *Rationale:* This will be the master template for the debugger agent. It will contain the system prompt adapted from the GitHub URL, modified to mandate the `mcp_codegraph_*` toolset for context gathering. It will also include specific instructions for progress tracking, requiring the agent to maintain a document at `<!--$HARNESS_DIR$-->/debug/yyyy-mm-dd-{debugger-case}.md`.
2. **Modify: `.gemini/AGENTS.md`** (and potentially `.claude/AGENTS.md` if it exists)
   - *Rationale:* We must register the new `@debugger` agent in the system's agent roster so the orchestrator and users know it is available and understand its strict mandate.
3. **Create/Generate: `.gemini/agents/debugger.md`**
   - *Rationale:* The active configuration for the Gemini CLI, generated from the boilerplate template to complete onboarding.
4. **Create/Generate: `.claude/plugin-generated/agents/debugger.md`**
   - *Rationale:* The active configuration for Claude Code, ensuring cross-platform compatibility as requested.

## Adversary Review

### 1. Premise Analysis
The design proposes integrating a "debugger" subagent into the Agentic Harness. It dictates replacing standard file read/search tools with a strict "graph-first" strategy utilizing `mcp_codegraph_*` tools. It further requires the agent to log its investigation progress dynamically into a dedicated debug file with a specific date-based naming convention, utilizing a placeholder path (`<!--$HARNESS_DIR$-->/debug/`) for cross-platform compatibility across Gemini and Claude environments.

### 2. Architectural Reality
- **Codegraph vs. Runtime Constraints:** The codegraph operates entirely on static code topology (symbols, references, structure). A debugger intrinsically requires access to dynamic runtime state, unstructured log files, stdout/stderr streams, and environment variables. Restricting a debugger to static graph tools mathematically guarantees it will fail to diagnose any issue lacking a direct, statically analyzable symbol reference.
- **Template Variable Resolution at Runtime:** The design mandates the agent write to `<!--$HARNESS_DIR$-->/debug/`. If the templating engine does not resolve this macro inside the prompt *before* the agent executes tool calls, the agent will literally attempt to create a directory named `<!--$HARNESS_DIR$-->` on the file system, leading to path parsing failures or corrupted directory structures.
- **Agent Registry Mechanisms:** Generating `.claude/plugin-generated/agents/debugger.md` is insufficient. The Claude infrastructure likely requires `.json` registry definitions or specific metadata configurations (as seen in `agent.json` and `skills.json`) to accurately register a subagent. Dropping a markdown file will not magically activate it.

### 3. Variables and Friction
- **Friction 1 (Tool Capability Deficit):** If the agent encounters a stack trace referencing line 42 of a raw JSON configuration file or a dynamically generated script not indexed by the codegraph, it will be physically unable to investigate.
- **Friction 2 (Context Exhaustion):** Logging progress iteratively to a single Markdown file will linearly increase the size of the file. If the agent constantly reads and writes to this file to update its state, it will burn through context windows and incur high token overhead.
- **Friction 3 (Platform Divergence):** The design ignores whether the underlying `mcp_codegraph_*` tools are identically configured and mapped across both Gemini and Claude environments. Any divergence in how the platform passes project context to these tools will cause failures.

### 4. Conclusion
The proposed design is logically unsound and operationally fragile. It fundamentally misunderstands the difference between static code analysis and dynamic debugging. By stripping away basic file operations, it neuters the debugger's primary utility. The reliance on untested template variables for runtime file pathing and the superficial approach to cross-platform agent registration guarantee a high probability of system failure upon deployment.