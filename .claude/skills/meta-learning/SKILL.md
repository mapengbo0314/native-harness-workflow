---
name: meta-learning
description: Use when tackling a completely new, complex subject to ensure deep understanding and avoid superficial knowledge or buzzword-heavy explanations.
---

# Meta-Learning Framework

## Overview
A structured, repeatable framework for deconstructing complex subjects into their irreducible units and rebuilding them through first-principles understanding.

## When to Use
Use when:
- You are starting a project with an unfamiliar technology stack.
- You encounter a system that feels "magical" or uses heavy abstractions you don't fully grasp.
- You find yourself using buzzwords (e.g., "orchestrator," "pipeline," "state machine") without being able to explain the underlying mechanism.
- You need to debug a system where standard documentation doesn't provide the answer.

## The Learning Protocol

### Phase 1: Deconstruction (Isolating the Atom)
*Goal: Strip away jargon until you find the smallest irreducible unit.*
1. **Identify the Baseline Unit:** Ask, "What is the absolute smallest thing being moved, changed, or processed here?"
2. **Define the Base State:** What does this unit look like before the system touches it?
3. **Banish the Buzzwords:** Define the concept using only primary vocabulary. If you need a complex word to define a complex word, you haven't hit the atom yet.

### Phase 2: The Single Thread (Tracing the Mechanism)
*Goal: Map the exact chronological journey of a single "atom" through the system.*
1. **The Entry Point:** Where exactly does the atom enter the system?
2. **The Transformation Nodes:** Follow the atom step-by-step. At every point it changes, answer: *What exact mechanism caused this change?* Accept no magic.
3. **The Exit Point:** What is the final state of the atom when the system is done?

### Phase 3: The "No Magic" Build (Removing Abstractions)
*Goal: Prove you understand the underlying physics by removing the tools designed to make it easy.*
1. **Identify the Abstraction Layer:** What software or library is doing the heavy lifting?
2. **The Manual Override:** Conceptually (or in code) build a crude, stripped-down version without that tool.
3. **Compare and Contrast:** Understand *why* the abstraction tool was designed by seeing how hard the manual way is.

### Phase 4: Systems Assembly (Zooming Out)
*Goal: Map how atoms and threads operate at scale.*
1. **Map the Dependencies:** What does this system rely on? What relies on it?
2. **Identify the Bottlenecks:** Where is the constraint at scale (compute, network, latency, rate limits)?
3. **The "Feynman" Check:** Explain the entire architecture end-to-end out loud. If you hesitate or use a vague phrase ("it processes the data"), you've found a blind spot.

### Phase 5: The Stress Test (Breaking It)
*Goal: Understand the boundaries and edge cases.*
1. **The Null Test:** What happens if the input is empty or missing?
2. **The Overload Test:** What happens if you multiply input by 10,000?
3. **The Fault Test:** If a middle component drops offline, how does the system fail?

### Phase 6: Validation (The Grilling)
*Goal: Prove your understanding against relentless, adversarial questioning.*
**REQUIRED SUB-SKILL:** Invoke the `grill-me` skill.
1. Declare your readiness: "I have deconstructed [Topic] using the meta-learning framework. I am ready for the Feynman Check. Please use the `grill-me` skill to question my understanding of the 'atoms', 'threads', and system assembly."
2. The grilling must focus on forcing you to explain the exact mechanisms without relying on buzzwords.
3. If you fail to answer a question clearly or fall back on jargon, the grilling pauses, and you must return to Phase 1 or 2 for that specific component.

## Red Flags - STOP and Re-evaluate
- **Buzzword Reliance:** Using terms like "AI," "Cloud," or "Middleware" to skip explaining a step.
- **"It Just Works":** Accepting a result without knowing the transformation mechanism.
- **Skipping to Scale:** Trying to understand system architecture before understanding the "atom."
- **Hesitation in Explanation:** If you can't explain a step to a child, you don't understand it yet.

## Common Mistakes
- **Mistaking Familiarity for Understanding:** Just because you've used a library doesn't mean you know how it works.
- **Ignoring the Physics:** Focusing on syntax instead of the underlying data movement.
- **Abstraction Worship:** Treating a framework as a black box instead of a convenience layer.

## Rationalization Table
| Excuse | Reality |
|--------|---------|
| "I already know the concept." | Can you explain the 'atom' without jargon? |
| "The docs say it works this way." | Docs often describe *what* it does, not *how* the mechanism transforms the atom. |
| "I don't have time for this." | Superficial learning guarantees high-cost debugging later. |
| "It's just a standard implementation." | Every 'standard' has edge cases you won't see until you stress test it. |
