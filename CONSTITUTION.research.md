# Constitution Research

_Generated: 2026-04-26. Thesis hash: refine-motion is the senior-architect-calling-his-dev-team_

## Design space overview

The autonomous-coding-agent space has split along two axes that matter for refine-motion. On the **planning axis**, products either gate execution behind an editable specification (GitHub Copilot Workspace, Devin 2.0, Sweep) or let an agent jump directly into a codebase and revise as it goes (Claude Code, Cursor's foreground agent, Aider's default chat mode). On the **autonomy axis**, products run as synchronous pair-programmers attached to a human keystroke (Aider, Cursor's foreground), as background workers under an orchestrator (Cursor 3 Agents Window, Anthropic's research orchestrator, Devin), or in flat peer topologies that have largely been abandoned for hierarchical ones (per Cursor's own postmortem).

A second cluster of stances concerns **how the human talks to the agent**. Voice-first products diverge sharply: Wispr Flow chose post-processed monologue over streaming so the LLM can rewrite "what you meant"; OpenAI's Realtime API and the rumored "BiDi" model chose true full-duplex with barge-in; Aider chose explicit push-to-talk turn-taking via `/voice`. And on **codebase grounding**, Aider built a tree-sitter + PageRank repo map upfront, while Anthropic explicitly rejected RAG/indexing for Claude Code in favor of agentic grep-and-read.

## Per-debate entries

---

### Refinement gate — hard spec-before-code vs jump-in-and-iterate (inferred)

**Stance A** (refine-motion's likely side: hard refinement gate produces a contract before implementation):
- Project: GitHub Copilot Workspace — explicitly forces a "proposed specification" stage that articulates current and desired state before any code is generated, and every downstream stage regenerates when the spec is edited. Source: https://githubnext.com/projects/copilot-workspace
- Project: Devin 2.0 — "proactively researches your codebase and develops a detailed plan" and lets the user "modify the plan to ensure that Devin's understanding of the task is aligned with what you have in mind" before autonomous execution. Source: https://cognition.ai/blog/devin-2
- Project: Sweep — posts its plan as a comment on the GitHub issue before writing code, so humans can correct direction before implementation. Source: https://docs.sweep.dev/

**Stance B** (skip the gate; let the agent start coding and refine through the artifact itself):
- Project: Claude Code — Boris Cherny's stated design principle is "do the simple thing first" and "just-in-time retrieval"; the agent decides what to look for, acts, and loops, with no required spec stage. Source: https://vadim.blog/claude-code-no-indexing
- Project: Aider — default chat mode treats a voice or text request as a direct edit instruction; `/voice` transcription is "treated as if typed text" and immediately acted on. Source: https://aider.chat/docs/usage/voice.html

**Is the opposite stance defensible?** Yes — for short, well-scoped edits a spec stage is overhead; Anthropic's argument that "complexity is deferred until it is demonstrated to be necessary" applies.

**Strongest opposite-stance argument found:**
> "Anthropic's principle is 'just in time retrieval of the smallest possible set of high-signal tokens' ... Claude Code decides what to look for, picks the right tool, acts on the result, and loops until it has enough to complete the task." — https://vadim.blog/claude-code-no-indexing

---

### Multi-agent topology — orchestrator+workers vs single agent with sub-tools vs flat peers (inferred)

**Stance A** (refine-motion's likely side: orchestrator + worker agents, hierarchical):
- Project: Anthropic Research — lead agent decomposes the query and spawns parallel subagents; the multi-agent system "outperformed single-agent Claude Opus 4 by 90.2%." Source: https://www.anthropic.com/engineering/multi-agent-research-system
- Project: Cursor 3 — moved from "agents [with] equal status" coordinating via shared files (which deadlocked) to a "planner-worker topology" where "hundreds of workers run concurrently" with "minimal conflicts." Source: https://cursor.com/blog/scaling-agents

**Stance B** (single agent, no orchestration; spawn sub-tools only when needed):
- Project: Claude Code — the main agent is the user's interlocutor; sub-agents (e.g. Explore) are spawned only for context isolation, not as a permanent topology. Source: https://vadim.blog/claude-code-no-indexing
- Project: Aider — single-process pair programmer; no orchestrator, no worker pool. Source: https://aider.chat/docs/

**Is the opposite stance defensible?** Yes — Anthropic itself warns that "some domains that require all agents to share the same context or involve many dependencies between agents are not a good fit for multi-agent systems today" and notes multi-agent costs ~15× more tokens.

**Strongest opposite-stance argument found:**
> "most coding tasks lack sufficient parallelizable components ... LLM agents are not yet great at coordinating and delegating to other agents in real time." — https://www.anthropic.com/engineering/multi-agent-research-system

---

### Voice UX shape — full-duplex barge-in vs post-processed monologue vs push-to-talk (inferred)

**Stance A** (refine-motion's likely side: conversational, low-latency, agent-asks-questions — implies streaming/full-duplex with barge-in):
- Project: OpenAI Realtime API — "live, full-duplex audio so you can interrupt and get quick, conversational turn-taking"; semantic VAD detects user speech and cancels in-flight responses for barge-in. Source: https://platform.openai.com/docs/guides/voice-agents
- Project: Inworld Voice Agents — markets full-duplex, low-latency conversation as the differentiator from turn-based ASR. Source: https://inworld.ai/voice-agents

**Stance B** (post-processed monologue; the user finishes speaking, the LLM rewrites what they meant):
- Project: Wispr Flow — explicitly chose post-processing over streaming so the system can "wait, understand, and then write what you _meant_. Not just what you said." Source: https://wisprflow.ai/post/designing-a-natural-and-useful-voice-interface
- Project: Aider — explicit push-to-talk: type `/voice`, speak, press ENTER; "Recording, press ENTER when done." Source: https://aider.chat/docs/usage/voice.html

**Is the opposite stance defensible?** Yes — Wispr Flow's argument that LLM post-processing produces higher-quality intent capture than streaming ASR is a real tradeoff against latency.

**Strongest opposite-stance argument found:**
> "They use large language models (LLMs) to post-process your speech, which means Flow can wait, understand, and then write what you meant. Not just what you said. ... It allows Flow to be less distracting while you're speaking." — https://wisprflow.ai/post/designing-a-natural-and-useful-voice-interface

---

### Codebase grounding — upfront indexed map vs lazy agentic search (inferred)

**Stance A** (refine-motion's likely side, given Claude Code lineage and "skilled architect" user: lazy agentic search):
- Project: Claude Code — explicitly rejected RAG indexing for four reasons: security (index is an attack target), privacy (embeddings leak proprietary code), staleness (index goes stale during edits), and reliability (more systems = more failure points); plus the precision argument that exact-match grep beats semantic search on symbol names. Source: https://vadim.blog/claude-code-no-indexing

**Stance B** (upfront codebase indexing / repo map):
- Project: Aider — builds a tree-sitter-based repo map ranked by a PageRank-style graph algorithm so "GPT can see classes, methods and function signatures from everywhere in the repo." Source: https://aider.chat/2023/10/22/repomap.html
- Project: Cursor — historically ships codebase embeddings/index for retrieval inside the IDE. Source: https://cursor.com/product

**Is the opposite stance defensible?** Yes — Aider's argument that without a map, GPT cannot reliably locate the right code in large repos is documented and the design predates Claude Code's contrary finding.

**Strongest opposite-stance argument found:**
> "GPT doesn't need to see the entire implementation of BarLog, it just needs to understand it well enough to use it. ... it can figure out by itself which files it needs to look at in more detail." — https://aider.chat/2023/10/22/repomap.html

---

### Blocker handling — agent escalates to architect vs agent pushes through autonomously (inferred)

**Stance A** (refine-motion's likely side: agent escalates new blockers back to the architect; refinement-implementation cycle iterates):
- Project: Devin 2.0 — has three explicit pathways for failures: fix adjacent code, note-and-continue if unrelated, or "escalate if failures genuinely block the task by surfacing this to the user with a clear explanation"; "actively brings you in as needed." Source: https://cognition.ai/blog/devin-2
- Project: GitHub Copilot Workspace — every stage is editable; when downstream fails, the user re-edits the spec or plan rather than the agent silently grinding. Source: https://githubnext.com/projects/copilot-workspace

**Stance B** (agent pushes through; minimize human interruption):
- Project: Cursor 3 long-running agents — designed for "extended autonomous work: following instructions, keeping focus, avoiding drift"; a "judge agent determined whether to continue" rather than escalating to a human at every doubt. Source: https://cursor.com/blog/scaling-agents
- Project: Devin 1.0 (per critics) — earlier versions were criticized for "push[ing] forward with impossible tasks rather than escalating," indicating the inverse stance was a real design point. Source (secondary): https://medium.com/@takafumi.endo/agent-native-development-a-deep-dive-into-devin-2-0s-technical-design-3451587d23c0

**Is the opposite stance defensible?** Yes — Cursor's planner-worker postmortem argues that excess human-in-the-loop creates the same bottlenecks as inter-agent locks; throughput requires the agent to keep moving.

**Strongest opposite-stance argument found:**
> "GPT-5.2 models are much better at extended autonomous work: following instructions, keeping focus, avoiding drift, and implementing things precisely. ... The right amount of structure is somewhere in the middle. Too little structure and agents conflict, duplicate work, and drift. Too much structure creates fragility." — https://cursor.com/blog/scaling-agents

---

## Unsolicited alternatives

- **Spec artifact format**: structured Linear-style ticket with fields vs free-form prose vs an evolving conversation transcript — refine-motion's "contract" needs a canonical form, and Linear's opinionated "one good way" stance vs Copilot Workspace's bulleted spec are real choices.
- **Refinement model vs implementation model split**: use a smaller/faster model for the refinement dialogue and a stronger model for implementation (Anthropic's Opus-leads-Sonnet pattern), or the same model for both.
- **Audio always-on vs explicit wake**: a mobile-in-motion product can either keep the mic hot (drains battery, privacy concerns) or require a wake gesture; neither is implied by the thesis.
- **Where the spec lives**: in-repo file (committed alongside code), external issue tracker (Linear/GitHub), or ephemeral session state — affects whether the contract survives a dropped Tailscale connection.
- **Architect-to-many vs architect-to-one-at-a-time**: the thesis allows multi-agent but is silent on whether the architect ever addresses two agents in one voice turn; Cursor 3's Agents Window vs a single-channel phone-call metaphor are opposite UX defaults.
- **Interruption semantics during implementation**: can the architect barge in mid-implementation to redirect, or only at refinement/blocker checkpoints? Full-duplex voice technically enables the former; product opinion decides.
- **Persistence of the architect persona**: does the agent remember the architect's preferences across sessions (Wispr Flow's "match your personal phrasing style over time") or stay stateless per session?
