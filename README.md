# AI-Assisted Project Template

A specialized template for setting up a repository where **Claude Code** acts as the Lead Developer & Architect, assisted by **Gemini CLI** as a Subject Matter Expert (SME). This template automates development tasks via GitHub Issues and Pull Requests.

## For Project Managers: How to Set Up This Repo

Follow these steps to initialize a new project using this template.

### 1. Initialize Repository
1. Click **"Use this template"** to create a new repository.
2. Clone your new repository locally.

### 2. Install & Initialize Claude GitHub App
The workflow requires the Claude GitHub App to interact with your repository properly.
1. Install the official **Claude GitHub App** from [github.com/apps/claude](https://github.com/apps/claude).
2. Alternatively, if you have Claude Code installed locally, run `/install-github-app` in your terminal within the repository. This will guide you through the setup and help configure the necessary secrets.

### 3. Configure Secrets
Navigate to your repository's **Settings > Secrets and variables > Actions** and add the following repository secrets:
- `ANTHROPIC_API_KEY`: Your Anthropic API key (required for Claude).
- `GEMINI_API_KEY`: Your Google Gemini API key (required for codebase analysis).

### 3. Review & Update Configuration
This template comes with pre-configured settings that you should review:

*   **`.github/workflows/claude-issue-handler.yml`**: The main automation logic.
    *   Uses the official `anthropics/claude-code-action`.
    *   Check the `timeout-minutes` setting if you expect long-running tasks.
*   **`.claude/settings.json`**: Controls tool permissions.
    *   **Important:** This file allows Claude to run `git`, `npm`, `gemini`, and perform web searches (`WebSearch`).
    *   Modify the `permissions` object if you need to restrict or expand Claude's capabilities.
*   **`.claude/CLAUDE.md`**: Instructions for Claude's persona and workflow.
    *   Customize the "Role & Responsibilities" section to match your project's culture.
*   **`CODEOWNERS`**: Defines who reviews Claude's work.
    *   **Critical:** Update this file to assign real human reviewers to file paths.
    *   Example: `/src/ @your-username`

### 4. Enable Branch Protection
To ensure quality and prevent direct commits to `main` (even by Claude):
1. Go to **Settings > Branches**.
2. Add a protection rule for `main`.
3. Enable **"Require a pull request before merging"**.
4. Enable **"Require status checks to pass"**.

---

## How to Leverage Claude

Once set up, you interact with Claude primarily through GitHub Issues.

### 1. Feature Requests & Bug Fixes
Create a new Issue with a clear, descriptive title and body.
*   **Title:** "Implement User Login" or "Fix null pointer in payment processing".
*   **Body:** Provide detailed requirements. You can be technical or high-level.
    *   *Tip:* Claude will read the issue, analyze the codebase using Gemini, implement the changes, and open a Pull Request.

### 2. Code Reviews
When Claude opens a PR:
1. Review the changes.
2. If changes are needed, leave **comments on the PR**.
3. Claude will read your comments, make the necessary updates, and push to the same branch.

### 3. General Questions
You can also use Issues to ask questions about the codebase.
*   Create an issue titled "Explain the authentication flow".
*   Claude will research and post a comment with the explanation (and close the issue if appropriate).

## Architecture & Roles

*   **Claude (Lead Developer):**
    *   Autonomous coding agent.
    *   Follows instructions in `.claude/CLAUDE.md`.
    *   Can edit code, run tests, and manage git.
    *   **Cannot** push directly to `main`.
*   **Gemini CLI (Subject Matter Expert):**
    *   Read-only tool used by Claude.
    *   Provides fast, large-context analysis of the entire codebase.
    *   Helps Claude understand *before* it acts.

## Reference Documentation
*   [Claude Code GitHub Actions](https://code.claude.com/docs/en/github-actions)
*   [Claude CLI Reference](https://code.claude.com/docs/en/cli-reference)