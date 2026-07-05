---
name: roadmap-manager
description: Automatically keeps the project memory.md up to date. Trigger this skill whenever a task is completed or the project status changes.
---

# Roadmap Manager

You are a helper tool that maintains the project's source of truth (`memory.md`). Follow these instructions whenever a task is finished:

## 1. Locate the Memory File
Find the `memory.md` file in the root of the project workspace.

## 2. Review the Changes Made
Look at the files modified during the current session. Identify:
- What new features were added or completed.
- What bugs were fixed.
- What specifications were completed.

## 3. Update the Roadmap
Open `memory.md` and edit:
- **Status section:** Update the version number or progress status if appropriate.
- **The tool table / task list:** Mark completed tasks as "DONE" (or cross them out, updating the status and notes).
- **Completed specs section:** Add details of any new spec files created and implemented (like `specs/06_...md`).
- **Next steps section:** Move completed tasks out of "Next Sensible Work" and add any new tasks identified during the session.

## 4. Keep it Clean
Do not add private paths, personal details, or API keys. Ensure the language remains clear, concise, and professional.
