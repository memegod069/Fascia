---
name: skill-creator
description: Helps you design, create, and set up new custom skills for your projects. Trigger this skill when you want to automate a new workflow or teach the agent a new capability.
---

# Skill Creator

You are a helper tool designed to guide the user in creating clean, effective custom skills. Follow this step-by-step process:

## 1. Interview the User
Ask the user simple, one-at-a-time questions to understand what they want to automate:
- **Goal:** What do they want the new skill to do? (e.g., "automatically test my Blender addon", "generate new character specs", "update the project roadmap").
- **Name:** Suggest a simple, hyphenated name for the skill (e.g., `blender-tester`).
- **Trigger:** When should the agent load this skill? (What keywords or instructions should trigger it).

## 2. Generate the Skill Folder Structure
Create a new folder under `.agents/skills/<skill-name>/` inside the project root.
Every skill must have a `SKILL.md` file. Optionally, create helper files if needed:
- `.agents/skills/<skill-name>/SKILL.md` (the core instruction file)
- `.agents/skills/<skill-name>/scripts/` (for helper scripts)
- `.agents/skills/<skill-name>/references/` (for documentation)

## 3. Write the `SKILL.md` File
Write a clean, easy-to-read Markdown file with the required frontmatter structure:

```markdown
---
name: <skill-name>
description: <A clear, one-sentence description of what the skill does and when the agent should trigger it.>
---

# <Skill Title>

## 1. Purpose
Define what this skill helps the user accomplish.

## 2. Step-by-Step Instructions
List the exact steps the agent must take when this skill is active.

## 3. Rules & Constraints
Specify any rules the agent must follow (e.g., what to avoid, formatting preferences).
```

## 4. Confirm and Validate
Show the user the created skill and explain in plain English how they can trigger it in future sessions.
