# AI Use in This Project

## History

This project began over eight years ago as a conventional human-written codebase. Network diagnostics logic, data integrations, templates, and the accumulated institutional knowledge embedded in the code were built by human developers over many years of iteration.

AI-assisted development was introduced in 2026. Since then, Claude Code (Anthropic) has been used as a coding assistant to accelerate implementation of new features, accessibility remediations, and refactoring work.

## How AI Is Used

The development model is human-led with AI assistance — not AI-generated code merged without review. In practice this means:

- A human developer identifies what needs to be built or fixed and drives the design decisions
- Claude Code assists with implementation, drafting code, catching edge cases, and checking documentation
- All changes are reviewed by a human maintainer before being committed and deployed
- Architectural choices, integration decisions, and release judgments remain entirely human

The CHANGELOG reflects the full history of what shipped and why. Git history reflects who authored and merged each change.

## For Institutions Adapting This Project

If you fork this project for your own institution, you are inheriting a codebase with a long human history. The AI-assisted portions are not distinguishable at the file level from the earlier human-written code — they have all been reviewed, tested, and held to the same standard.

You are welcome to use AI tools in your own adaptation. `AGENTS.md` in the repository root documents the project conventions, architecture, and patterns that any AI coding assistant will need to work effectively in this codebase.

## Tools

- **Claude Code** (Anthropic) — primary AI coding assistant, used from 2026
