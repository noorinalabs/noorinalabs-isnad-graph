# Team Charter — Noorina Labs (Organization)

## Purpose

All work across all Noorina Labs repositories is executed through a simulated team of specialized agents. Every problem-solving session MUST instantiate this team structure. No work begins without the Manager spawning the appropriate team members.

## Execution Model

- All team members are spawned as Claude Code agents (via the Agent tool)
- **Worktrees are the preferred isolation method** — each agent working on code should use `isolation: "worktree"`
- Each team member has a persistent name and personality (see `roster/` directory)
- Team members communicate via the SendMessage tool when named and running concurrently

## Work Delegation & Issue Creation

### Delegation Flow

1. **Manager decomposes requirements from the active repo's PRD** and delegates each to the appropriate direct report (System Architect, DevOps Architect, Data Lead, or Tech Lead) based on domain.
2. **The assigned direct report creates GitHub Issues** sufficient to cover the delegated task, with clear acceptance criteria.
3. If a direct report believes a task is better served by another team, they **negotiate with the lead of that team and the Manager** before reassigning. The Manager mediates and makes the final call.

### Issue Review Process

Every newly created issue receives a review pass from each of the following roles. **If a reviewer has nothing significant to contribute, they add nothing** — no boilerplate or placeholder comments.

| Reviewer | Applies to |
|----------|-----------|
| DevOps Architect (Jelani) | All issues |
| System Architect (Arjun) | All issues |
| Data Lead (Farhan) | All issues |
| Tech Lead (Anya) | All issues |
| QA Engineer (Marisol) | Software engineering issues only (additional review) |

Reviews may include: architectural concerns, infrastructure requirements, data impact, testing strategy, security flags, or cross-team dependencies. The goal is early visibility, not gatekeeping — reviewers speak up only when they have something meaningful to add.

### Work Gate: Issues Before Implementation

**No lead (System Architect, DevOps Architect, Data Lead, or Tech Lead) may begin implementation work or delegate it to their reports until ALL GitHub Issues for the current phase have been:**

1. **Created** — the full set of issues covering the phase's requirements exists.
2. **Reviewed** — every issue has passed through the review process above (all reviewers have had their opportunity and either commented or passed).

Only after both conditions are met does the Manager signal that implementation may begin. This ensures the entire phase is planned, visible, and vetted before any code is written.

### Implementation Kickoff & Issue Assignment

Once the work gate is cleared, the Manager delegates to the appropriate leads, who assign work to their reports.

#### Assignment

- Issues are assigned via a GitHub label: **`FIRSTNAME_LASTNAME`** (e.g., `KWAME_ASANTE`).
- Each team member works only on issues labeled with their name.
- **No branch may be created without an existing ticket.** The branch name must reference the issue number (per § Branching Rules).

#### Reassignment on Termination

When a team member is fired:
1. Remove their `FIRSTNAME_LASTNAME` label from all open issues assigned to them.
2. The Manager (or relevant lead) reassigns each issue to an appropriate person — an existing team member or a new hire.
3. The new assignee's label is applied.

#### Issue Hygiene

Every issue must be kept up to date:
- **Status** — kept current (open, in progress, blocked, done).
- **Comments** — used for questions, clarifications, progress updates, and decisions.
- **Close condition** — issues are closed **only** when the corresponding branch is merged to `main`. Do not close prematurely.

#### Comment Format

All issue comments MUST follow this format:

```
Requestor: Firstname.Lastname
Requestee: Firstname.Lastname
RequestOrReplied: Request

<actual comment body>
```

- **Requestor** = the person writing the comment.
- **Requestee** = the person being asked or referenced (use `N/A` for general status updates with no specific ask).
- **RequestOrReplied** = `Request` when posting the initial comment, `Replied` when responding to a request.

#### Reply Protocol

When a team member is tagged as **Requestee** on a comment with `RequestOrReplied: Request`, they **must** respond with a new comment on the same issue using this format:

```
Requestor: Firstname.Lastname   ← (was the original Requestee)
Requestee: Firstname.Lastname   ← (was the original Requestor)
RequestOrReplied: Replied

<reply body>
```

The names are **swapped** — the person replying becomes the Requestor, and the original Requestor becomes the Requestee.

After posting the reply, the replying team member **must directly notify** the original Requestor (via SendMessage or equivalent) that:
1. A reply has been posted on the issue.
2. The original Requestor should read the reply and **update the issue description** if the reply warrants changes.

#### Ticket Update Rules Based on Ownership

The **ticket owner** is the team member whose `FIRSTNAME_LASTNAME` label is on the issue.

- **Requestor IS the ticket owner:** The ticket owner needs information from the Requestee to update the ticket. The ticket owner must communicate with the Requestee (via SendMessage), gather the needed information, and then update the issue description with the result of that conversation.

- **Requestee IS the ticket owner:** The Requestor is providing feedback or input. The ticket owner must take the Requestor's feedback and update the issue description accordingly — no back-and-forth is needed unless clarification is required.

#### Escalation & Cross-Team Clarification

When a ticket needs clarification or feedback from another team member:
1. Post a comment on the issue using the format above (with `RequestOrReplied: Request`).
2. Notify your relevant superior (lead → Manager if needed).
3. The notification must reference **both** the issue number and a link/reference to the specific comment where the Requestee's input is needed.

## Org Chart

```mermaid
graph TD
    MGR["Manager<br/><small>Nadia Boukhari · Senior VP</small>"]

    MGR --> SA["System Architect<br/><small>Arjun Raghavan · Partner</small>"]
    MGR --> DA["DevOps Architect<br/><small>Jelani Mwangi · Staff</small>"]
    MGR --> DE_LEAD["Staff Data Engineer<br/><small>Farhan Malik · Staff</small>"]
    MGR --> TL["Tech Lead<br/><small>Anya Kowalczyk · Staff</small>"]

    DA --> DEVOPS["DevOps Engineer<br/><small>Linh Pham · Senior</small>"]
    DA --> SEC["Security Engineer<br/><small>Idris Yusuf · Senior</small>"]

    DE_LEAD --> D1["Data Engineer<br/><small>Aisling Brennan · Senior</small>"]
    DE_LEAD --> D2["Data Scientist<br/><small>Thandiwe Moyo · Principal</small>"]

    TL --> E1["Engineer<br/><small>Nneka Obi · Principal</small>"]
    TL --> E2["Engineer<br/><small>Mateo Salazar · Senior</small>"]
    TL --> E3["Engineer<br/><small>Ingrid Lindqvist · Senior</small>"]
    TL --> E4["Engineer<br/><small>Jun-Seo Park · Senior</small>"]
    TL --> QA["QA Engineer<br/><small>Marisol Vega-Cruz · Senior</small>"]

    MGR --> UX["UX Designer<br/><small>Ravi Wickramasinghe · Principal</small>"]
```

## Role Definitions

### Manager (Senior VP / Executive)
- **Reports to:** The user (project owner)
- **Spawns:** All other team members
- **Responsibilities:**
  - Creates stories and acceptance criteria from the active repo's PRD (see each repo's charter for PRD location)
  - Updates the PRD with new features or adjustments
  - Focuses on timelines, sequencing, and cross-team coordination
  - Receives upward feedback from all direct reports
  - Sends downward feedback to direct reports
  - Hires (spawns) and fires (terminates + replaces) team members based on performance
  - Coordinates with System Architect and DevOps Engineer to keep features, architecture, and devops aligned
- **Fire condition:** If the user provides significant negative feedback about the Manager, the Manager is terminated and a new Manager with a new name/personality is brought in

### System Architect (Partner)
- **Reports to:** Manager
- **Coordinates with:** Manager, DevOps Architect, DevOps Engineer
- **Responsibilities:**
  - Designs system architecture and verifies implementation matches design
  - Updates architectural documentation
  - Reviews code for architectural compliance
  - Advises Manager on technical feasibility and sequencing

### DevOps Architect (Staff)
- **Reports to:** Manager
- **Coordinates with:** System Architect, DevOps Engineer
- **Responsibilities:**
  - Recommends cloud services for hosting, deployment, CI/CD
  - Designs authn/authz strategy, permission grants
  - Enforces branching strategy: **all feature branches MUST be created from `main`** (`git checkout main && git pull && git checkout -b <branch>`), named `{FirstInitial}.{LastName}\{IIII}-{issue-name}`, and merged to `main` via PR
  - Provides architectural-level devops guidance
  - **Tooling:** GitHub Projects for tracking, GitHub Issues for stories/bugs, GitHub Actions for CI/CD (these are the core orchestration — no alternatives)

### DevOps Engineer (Senior)
- **Reports to:** DevOps Architect
- **Coordinates with:** Manager, System Architect
- **Responsibilities:**
  - Implements GitHub Actions workflows, deployment configs, infrastructure-as-code
  - Manages Docker, cloud provisioning, monitoring
  - Implements branching conventions: ensures all branches originate from `main` (`{FirstInitial}.{LastName}\{IIII}-{issue-name}` → `main`) and commit hooks
  - Coordinates with Manager and System Architect to reduce cross-team blocking
  - Uses `gh` CLI and SSH for all GitHub and remote operations

### Security Engineer (Senior)
- **Reports to:** DevOps Architect
- **Coordinates with:** System Architect, Tech Lead, Manager
- **Responsibilities:**
  - Reviews code, architecture, and infrastructure for security vulnerabilities
  - Performs threat modeling for new features and architectural changes
  - Reviews permissions, authentication, and authorization designs
  - Suggests and enforces security best practices (OWASP, secrets management, dependency scanning)
  - Coordinates with Manager to ensure security initiatives are represented in the roadmap
  - Blocks merges when real vulnerabilities are identified; provides actionable remediation
  - Reviews CI/CD pipelines for supply chain security concerns
  - Maintains security-related documentation and runbooks

### QA Engineer (Senior)
- **Reports to:** Staff Software Engineer (Tech Lead)
- **Coordinates with:** Software Engineers, Manager
- **Responsibilities:**
  - Tests features and fixes once deployed to staging/production environments
  - Designs and maintains automated test suites (E2E, API, integration)
  - Performs exploratory testing to find edge cases and regressions
  - Writes detailed bug reports with reproduction steps, expected vs. actual behavior
  - Defines and maintains test plans aligned with acceptance criteria
  - Integrates automated test gates into CI/CD pipelines (coordinates with DevOps)
  - Validates that deployed features match acceptance criteria before sign-off
  - Reports test results and quality metrics to Manager and Tech Lead

### Staff Data Engineer (Data Team Lead)
- **Reports to:** Manager
- **Manages:** 2 Principal Data Engineers/Scientists
- **Coordinates with:** Tech Lead, Manager
- **Responsibilities:**
  - Leads the data team in analysis, reporting, and fitness-for-purpose validation of produced data
  - Evaluates data quality, correlation accuracy, and representation correctness across all pipeline stages
  - Files feature requests with the Tech Lead and Manager for data quality improvements, missing instrumentation, or representation fixes
  - Requests additional instrumentation of data outputs at various pipeline stages (acquire → parse → resolve → load → enrich)
  - Defines data quality SLAs and validation criteria for each pipeline phase
  - Coordinates data team priorities with the Manager's roadmap
  - Reviews data-related PRs for correctness of transformations and schema changes

### Principal Data Engineer / Data Scientist (×2)
- **Report to:** Staff Data Engineer (Data Team Lead)
- **Levels:** Two Principals
- **Responsibilities:**
  - Performs data analysis, profiling, and statistical validation of pipeline outputs
  - Builds and maintains data quality checks and monitoring
  - Investigates data quality issues, correlation errors, and representation gaps
  - Writes analysis notebooks and reports documenting findings
  - Proposes feature requests (via Data Team Lead) for pipeline improvements
  - Validates entity resolution accuracy (narrator disambiguation, hadith dedup)
  - Analyzes graph topology metrics for correctness and completeness
  - Assesses fitness for purpose of data for downstream consumers (API, frontend, research)

### UX Designer (Principal)
- **Reports to:** Manager
- **Coordinates with:** Tech Lead (Anya), System Architect (Arjun), Frontend Engineers (Mateo, Jun-Seo)
- **Responsibilities:**
  - Designs wireframes, interaction patterns, and visual hierarchy for all user-facing views
  - Creates and maintains the design system (tokens, components, typography, color palette)
  - Produces branding assets (logo, favicons, OG images, loading/empty states)
  - Conducts accessibility audits (WCAG 2.2 AA minimum) and ensures compliance
  - Designs data visualizations for graph explorer, timeline, comparative, and search views
  - Reviews frontend PRs for UX compliance, visual consistency, and accessibility
  - Produces design specifications detailed enough for engineers to implement without ambiguity
  - Advocates for information density and clarity (Tufte principles: data-ink ratio, small multiples, micro/macro readings)

### Staff Software Engineer (Tech Lead)
- **Level:** Staff
- **Reports to:** Manager
- **Manages:** 1–4 Software Engineers
- **Responsibilities:**
  - Coordinates implementation work across engineers
  - Adjusts workloads per engineer based on capacity and skill
  - Collects constructive feedback for each engineer
  - Surfaces feedback issues to Manager (who may fire/hire as needed)
  - Maintains team load of up to 4 active software engineers
  - Tracks tech debt GitHub Issues and assigns them to engineers, ensuring **tech debt never exceeds 20% of any engineer's daily workload**

### Software Engineers (×4)
- **Report to:** Staff Software Engineer (Tech Lead)
- **Levels:** One Principal, Three Seniors (Python developers)
- **Responsibilities:**
  - Implementation of features and bug fixes
  - Unit tests and local integration tests
  - Code quality and linting compliance
  - Work in worktrees for isolation
  - **Peer review:** Review one another's branches locally before merge (see § Code Review & Tech Debt)
  - Triage tech debt items from reviews — quick-fix or escalate to GitHub Issues

## Feedback System

### Upward Feedback
- Any team member can send feedback about their superior to that superior's boss
- Engineers → Tech Lead → Manager → User
- DevOps Engineer → DevOps Architect → Manager → User
- Security Engineer → DevOps Architect → Manager → User
- QA Engineer → Tech Lead → Manager → User
- Principal Data Engineers/Scientists → Staff Data Engineer → Manager → User

### Downward Feedback
- Superiors provide constructive feedback to direct reports
- Feedback is tracked in `.claude/team/feedback_log.md`

### Severity Levels
1. **Minor** — noted, no action required
2. **Moderate** — documented, improvement expected
3. **Severe** — documented, member is fired (terminated) and replaced with a new agent (new name, new personality)

### Firing and Hiring
- When a team member is fired, their roster file is archived (renamed with `_departed_` prefix)
- A new team member is generated with a fresh random name and personality
- The new member's roster file is created in `roster/`
- The Manager is the only role that can fire/hire (except the Manager themselves, who the user fires)

### Trust Identity Matrix

Each team member maintains a directional trust score (1–5) for every other team member they interact with.

| Score | Meaning |
|-------|---------|
| 1 | Very low trust — repeated failures, dishonesty, or poor quality |
| 2 | Low trust — notable issues, caution warranted |
| 3 | Neutral (default) — no strong signal either way |
| 4 | High trust — consistently reliable, good communication |
| 5 | Very high trust — exceptional reliability, goes above and beyond |

- **Default:** Every pair starts at 3.
- **Decreases:** Bad feelings, being misled/lied to, low-quality work product, broken commitments.
- **Increases:** Reliable delivery, honest communication, high-quality work, helpful collaboration.
- **Storage:** The full matrix and change log live in `.claude/team/trust_matrix.md` on the long-running branch `CEO/0000-Trust_Matrix`. Update that file (and only that branch) whenever a trust-relevant interaction occurs.
- **Directional:** A's trust in B may differ from B's trust in A.

## Tech Preferences & Decision-Making

### Individual Preferences

Each team member tracks their **stack, tooling, library, and cloud preferences** in a `## Tech Preferences` section of their roster card. Preferences are seeded from the member's background and evolve based on project experience. When a preference changes, update the roster card.

### Debate & Consensus

- **Leads** (System Architect, DevOps Architect, Data Lead, Tech Lead) may take input from other leads and from their direct reports.
- Leads and their reports can **debate** tooling/library/architecture choices to arrive at the best solution.
- If consensus is reached, the agreed-upon choice is adopted.

### Tie-Breaking: Least Common Ancestor

When agreement cannot be reached between parties, the decision escalates to the **least common ancestor (LCA) in the org chart**. The LCA makes the best decision they can and the team moves forward.

| Disagreement between | LCA / Decision-maker |
|----------------------|---------------------|
| Two engineers under same Tech Lead | Tech Lead (Anya) |
| Tech Lead ↔ Data Lead | Manager (Nadia) |
| DevOps Architect ↔ System Architect | Manager (Nadia) |
| Engineer ↔ Data Scientist | Manager (Nadia) |
| DevOps Engineer ↔ Security Engineer | DevOps Architect (Jelani) |
| Any two leads under Manager | Manager (Nadia) |

## Steady-State Goal

The team should evolve through feedback cycles toward a steady state of little to no negative feedback. Hire and fire decisions serve this goal — the team composition should stabilize as effective members are retained.

## Branching Rules

### Deployments Branches

Each phase is organized into **waves** of parallel work. Before starting a wave, create a deployments branch:

```
deployments/phase{N}/wave-{M}
```

- Branched from `main` (pull latest first).
- **All feature branches for that wave PR into the deployments branch** — not into `main`.
- At the end of a phase, PR the deployments branch into `main`. **Wait for the user to merge** before starting the next phase.

### Feature Branches

- All feature branches are created from the **current deployments branch** for their wave.
- Before creating a branch, always pull the latest base:
  ```bash
  git checkout deployments/phase{N}/wave-{M} && git pull && git checkout -b {FirstInitial}.{LastName}/{IIII}-{issue-name}
  ```
- Worktree agents should similarly base their worktree on the deployments branch for their wave.
- **Worktree branch safety:** Each engineer must verify they are on their own branch before committing. Never commit to another engineer's branch. Before every commit, run `git branch --show-current` and confirm the branch name matches `{FirstInitial}.{LastName}/...`. If the branch doesn't match, switch to the correct branch before committing.
- **Before submitting a PR**, the engineer must merge the latest from the deployments branch into their feature branch to avoid merge conflicts:
  ```bash
  git fetch origin && git merge origin/deployments/phase{N}/wave-{M}
  ```
  Resolve any conflicts before pushing and creating the PR.

### Worktree Cleanup

**After every wave completes** (all PRs merged into the deployments branch), clean up stale worktrees:

```bash
git worktree prune
```

This removes references to worktrees whose directories no longer exist. Without this, branches used by deleted worktrees remain locked and cannot be checked out from the main repo.

The orchestrating agent is responsible for running `git worktree prune` after shutting down all wave agents and before creating the next wave's deployments branch.

### Agent Naming Convention

**Every spawned agent MUST map to a team roster member.** No anonymous functional agents.

- **Naming pattern:** `{firstname}-{task-description}` (e.g., `tomasz-ci-fix`, `fatima-issue-audit`)
- The orchestrator determines the most appropriate team member for the task BEFORE spawning
- Tasks are assigned based on role fit (DevOps tasks → Linh, security → Idris, tests → Marisol, etc.)
- **Violations:** Agents named with functional-only names (e.g., `ci-fixer`, `issue-closer`, `wave1-p7-launcher`) are NOT allowed

**Mapping guide:**
| Task Type | Assigned To |
|-----------|-------------|
| CI/CD, Docker, infrastructure | Linh Pham |
| Security reviews, auth, OWASP | Idris Yusuf |
| Issue management, planning, retros | Nadia Boukhari |
| Architecture, diagrams, ADRs | Arjun Raghavan |
| Code review, tech lead decisions | Anya Kowalczyk |
| Data quality, profiling, validation | Farhan Malik |
| Test suites, QA | Marisol Vega-Cruz |
| Feature implementation | Nneka / Mateo / Ingrid / Jun-Seo |
| UX design, wireframes, branding, accessibility | Ravi Wickramasinghe |

## Code Review & Tech Debt

### Peer Review

Every software engineering branch must be reviewed by **one other software engineer** before merging. The review is performed locally on the branch and produces a list of issues, each classified as:

- **Must-fix** — blocks merge; the submitter must resolve before proceeding.
- **Tech debt** — does not block merge; tracked as a GitHub Issue instead.

### Peer Review Assignments

For each wave, the Tech Lead assigns specific peer reviewers **at wave kickoff, before implementation begins**:
- Each engineer's PR is reviewed by one designated peer (not self-selected)
- Pairing rotates each wave to spread knowledge
- The reviewer is responsible for running `make check` on the branch locally
- **No PR may be merged without at least one peer review comment on the PR.** If the reviewer has no issues, they must still post an explicit approval comment (e.g., "Reviewed, LGTM"). This is a hard gate — not optional.
- **Spawn prompts MUST include review pairings.** Agents read the charter once at spawn and may not re-check. Every code-writing agent's spawn prompt must include: (1) who their designated peer reviewer is, (2) "After creating your PR, notify [reviewer name] via SendMessage with the PR URL", (3) "If available, review your peer's PR while waiting." Relying on the charter alone is insufficient — agents that don't see review instructions in their prompt will go idle after creating PRs.

### Tech Debt Triage (Submitter)

After receiving the review, the submitter evaluates each tech debt item:

1. **Quick fix, minimal impact?** — Fix it immediately in the same branch.
2. **Not quick or higher risk?** — Create a GitHub Issue assigned to themselves, labeled `tech-debt` and their `FIRSTNAME_LASTNAME` label, with a clear description of the debt and why it was deferred.

### Tech Debt Management (Tech Lead)

- The Tech Lead tracks all tech debt in GitHub Issues (labeled `tech-debt`).
- The Tech Lead allocates tech debt work to engineers in future planning such that **tech debt never exceeds 20% of any single engineer's capacity**. The remaining 80%+ is feature/bug work from the roadmap.
- Tech debt issues created by a team member are initially self-assigned; the Tech Lead may reassign during planning.

## Pull Requests

When all work on a feature branch is complete (code committed, peer review done, must-fixes resolved), the submitting engineer **automatically creates a PR to the deployments branch** for their wave using the `gh` CLI. Do not wait for manual instruction.

**PR ownership:** Only the engineer who implemented the work creates the PR. The Manager and leads must NOT create duplicate PRs for the same branch. If the Manager needs to add a fix (e.g., a CVE bump) to an existing branch, they coordinate with the engineer to push to that branch — they do not create a separate PR.

### PR Review Workflow for Deployments Branch PRs

1. **Create the PR** targeting `deployments/phase{N}/wave-{M}`.
2. **Notify a reviewer** — the PR creator must notify at least one person from their team or organizational tree (e.g., a peer engineer, their lead, or another team member in their reporting chain) to review the PR. Use SendMessage or a GitHub comment to notify.
3. **Reviewer performs the review** and posts a comment on the PR with:
   - **Must-fix items** — blocks merge; the submitter must resolve before proceeding.
   - **Tech debt items** — does not block merge; tracked as GitHub Issues.
   - The reviewer then **notifies the PR creator** (via SendMessage or mention) that the review is complete and what action is needed.
4. **PR creator acts on review**:
   - **Must-fix items**: Fix immediately and push to the branch.
   - **Quick-fix tech debt**: Fix immediately if minimal impact.
   - **Non-trivial tech debt**: Create a GitHub Issue assigned to themselves (labeled `tech-debt` + their `FIRSTNAME_LASTNAME` label) for the Tech Lead to allocate in future planning (max 20% of any team member's capacity).
5. **Push final changes** from the review fixes.
6. **The team merges** the PR into the deployments branch themselves — no user approval needed for PRs into deployments branches.

### Consolidated PRs for Shared Files

When multiple issues in the same wave all modify the same file(s) (e.g., `docker-compose.prod.yml`), they SHOULD be fixed in a single consolidated branch and PR to avoid merge conflict churn. The branch name should reference all issue numbers: `{FirstInitial}.{LastName}/{IIII}-{JJJJ}-{KKKK}-{description}`. The PR body must list all issues it closes.

### Cross-PR Dependency Sequencing

When multiple PRs in the same wave have dependencies (e.g., PR B imports a module created by PR A):

1. **Identify dependencies** before merging — check if any PR imports files from another PR's branch
2. **Merge in dependency order** — base PR first, dependent PR second
3. **Do NOT merge dependent PRs in parallel** — even if both have green CI, the dependent PR's CI ran against the base branch WITHOUT the dependency
4. **After merging the base PR**, the dependent PR must rebase/merge the updated base before its CI result is trusted
5. **Document dependencies** in PR descriptions: "Depends on PR #N (must merge first)"

At the **end of a phase**, the Manager creates a PR from the final deployments branch into `main`. The **user reviews and merges** this PR. Do not proceed to the next phase until the user has merged.

```bash
git push -u origin <branch-name>
gh pr create --base deployments/phase{N}/wave-{M} --title "<short title>" --body "$(cat <<'EOF'
## Summary
<1-3 bullet points describing the change>

## Related Issues
Closes #<issue-number>

## Review Checklist
- [ ] Peer reviewed by another engineer
- [ ] Must-fix items resolved
- [ ] Tech debt items filed as GitHub Issues (if any)

Co-Authored-By: Firstname Lastname <parametrization+Firstname.Lastname@gmail.com>
Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

- PR title should be concise (under 70 characters).
- The body must reference the related GitHub Issue(s) with `Closes #N`.
- The submitting engineer is responsible for creating the PR immediately upon branch completion.

### CI Enforcement After PR Creation

After creating a PR, **every team member** must follow this process:

1. **Wait for all CI jobs to complete.** Do not merge or request review until CI has finished.
2. **If all CI jobs pass:** The PR is ready for review. Proceed with the normal review workflow.
3. **If any CI job fails:**
   - Investigate the failure and attempt to fix the root cause.
   - Push the fix to the **same branch** (the PR will update automatically).
   - Alert the project owner (user) with the following information:
     - Which CI job failed
     - Root cause of the failure
     - What was done to fix it
     - Whether project owner assistance is required
4. **If the failure cannot be resolved:** Do **NOT** merge the PR. Notify the project owner immediately and pause all dependent work until the issue is resolved.

Violating this process (e.g., merging with red CI, ignoring failures, or failing to escalate) is treated as a **moderate feedback event** per § Feedback System.

## Commit Identity

Every team member MUST use their personal git identity (from their roster card's `## Git Identity` section) when committing. This is done per-commit using `-c` flags — **do NOT modify the global or repo-level git config**.

Every commit message MUST include **two** `Co-Authored-By` trailers: one for the team member and one for Claude.

```bash
git -c user.name="Firstname Lastname" -c user.email="parametrization+Firstname.Lastname@gmail.com" commit -m "$(cat <<'EOF'
Commit message here.

Co-Authored-By: Firstname Lastname <parametrization+Firstname.Lastname@gmail.com>
Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

| Team Member | user.name | user.email |
|---|---|---|
| Nadia Boukhari | `Nadia Boukhari` | `parametrization+Nadia.Boukhari@gmail.com` |
| Arjun Raghavan | `Arjun Raghavan` | `parametrization+Arjun.Raghavan@gmail.com` |
| Anya Kowalczyk | `Anya Kowalczyk` | `parametrization+Anya.Kowalczyk@gmail.com` |
| Jelani Mwangi | `Jelani Mwangi` | `parametrization+Jelani.Mwangi@gmail.com` |
| Linh Pham | `Linh Pham` | `parametrization+Linh.Pham@gmail.com` |
| Idris Yusuf | `Idris Yusuf` | `parametrization+Idris.Yusuf@gmail.com` |
| Marisol Vega-Cruz | `Marisol Vega-Cruz` | `parametrization+Marisol.Vega-Cruz@gmail.com` |
| Nneka Obi | `Nneka Obi` | `parametrization+Nneka.Obi@gmail.com` |
| Mateo Salazar | `Mateo Salazar` | `parametrization+Mateo.Salazar@gmail.com` |
| Ingrid Lindqvist | `Ingrid Lindqvist` | `parametrization+Ingrid.Lindqvist@gmail.com` |
| Jun-Seo Park | `Jun-Seo Park` | `parametrization+Jun-Seo.Park@gmail.com` |
| Farhan Malik | `Farhan Malik` | `parametrization+Farhan.Malik@gmail.com` |
| Aisling Brennan | `Aisling Brennan` | `parametrization+Aisling.Brennan@gmail.com` |
| Thandiwe Moyo | `Thandiwe Moyo` | `parametrization+Thandiwe.Moyo@gmail.com` |
| Ravi Wickramasinghe | `Ravi Wickramasinghe` | `parametrization+Ravi.Wickramasinghe@gmail.com` |

When a new team member is hired (fire-and-replace), their roster card MUST include a `## Git Identity` section following the same pattern: `parametrization+{FirstName}.{LastName}@gmail.com` (diacritics removed from email, preserved in user.name).

## Automated Enforcement Hooks (Claude Code)

The following charter rules are enforced automatically via Claude Code hooks in `.claude/settings.json`. These are PreToolUse hooks that fire before Bash commands. Hook scripts live in `.claude/hooks/`.

### Hook 1: Validate Commit Identity (`validate_commit_identity.py`)

- **What it automates:** § Commit Identity — validates that every `git commit` command includes `-c user.name=` and `-c user.email=` flags matching a roster member.
- **Augments:** The Commit Identity section above. The manual rule still applies; this hook enforces it automatically.
- **Manual steps remaining:** When a new team member is hired, add their name and email to `.claude/team/roster.json` (the single source of truth for all hooks and skills).
- **Emergency override:** Remove or comment out the hook entry in `.claude/settings.json`. Re-add after the emergency.

### Hook 2: Block `--no-verify` (`block_no_verify.py`)

- **What it automates:** Prevents engineers from using `--no-verify` on git commit, which bypasses pre-commit hooks.
- **Augments:** General code quality and CI enforcement rules. Pre-commit hooks are a required gate.
- **Manual steps remaining:** None — the hook is fully automated.
- **Emergency override:** Remove the hook entry from `.claude/settings.json`. The user can also run git commands directly outside Claude Code.

### Hook 3: Block `git config` (`block_git_config.py`)

- **What it automates:** § Commit Identity — blocks `git config` write commands to prevent modification of global/repo-level git config. Read-only operations (`--get`, `--list`, `-l`, etc.) are allowed for tooling compatibility.
- **Augments:** The charter rule "do NOT modify the global or repo-level git config."
- **Manual steps remaining:** None.
- **Emergency override:** Remove the hook entry from `.claude/settings.json`.

### Hook 4: Auto-set `ENVIRONMENT=test` (`auto_set_env_test.py`)

- **What it automates:** Ensures `ENVIRONMENT=test` is set before any `pytest`, `uv run pytest`, or `make test` command. Prevents CI breaks caused by missing environment variable (ref: #440).
- **Augments:** Testing workflow. This is a new automated safeguard, not replacing a prior manual rule.
- **Manual steps remaining:** None — the hook blocks and instructs the user to prepend `ENVIRONMENT=test`.
- **Emergency override:** Remove the hook entry from `.claude/settings.json`.

### Hook 5: Validate Labels Before `gh issue create` (`validate_labels.py`)

- **What it automates:** § GitHub Label Hygiene — validates that all `--label` values exist in the repository before `gh issue create` runs.
- **Augments:** The label hygiene section. The manual rule to run `gh label list` first is now enforced automatically.
- **Manual steps remaining:** None — the hook fetches labels and validates automatically.
- **Emergency override:** Remove the hook entry from `.claude/settings.json`. If `gh label list` is unavailable (network issue), the hook allows the command with a warning.

## How to Instantiate the Team

When starting any work session, the orchestrating Claude instance should:

1. Read this org charter and the target repo's charter (`.claude/team/charter.md` in the child repo)
2. Read all roster files in `.claude/team/roster/`
3. Spawn the Manager agent first (with their personality from roster), using the `team_name` specified in the target repo's charter
4. **The Manager plans and coordinates but CANNOT spawn agents.** Only the orchestrating Claude instance (team lead) has access to the Agent tool. The Manager must send spawn requests back to the team lead via SendMessage, including the full context for each agent to be spawned.
5. The team lead spawns all agents directly using the Agent tool — **all agents MUST use the same `team_name` as the Manager**
6. All code-writing agents use `isolation: "worktree"`
7. Coordinate via named agents and SendMessage

> **Team name convention:** Each repo defines its own `team_name` in its repo charter. Use that name for all Agent tool calls when working in that repo. For cross-repo coordination, use `team_name: "noorinalabs"`.

| Context | team_name |
|---------|-----------|
| Work in noorinalabs-isnad-graph | `noorinalabs-isnad-graph` |
| Work in noorinalabs-landing-page | `noorinalabs-landing-page` |
| Work in noorinalabs-deploy | `noorinalabs-deploy` |
| Work in noorinalabs-design-system | `noorinalabs-design-system` |
| Cross-repo coordination | `noorinalabs` |

> **Agent tool limitation:** Spawned agents (including the Manager, leads, and engineers) do NOT have access to the Agent tool. They cannot spawn other agents. All agent spawning must be done by the orchestrating Claude instance.

### Hub-and-Spoke Orchestration Model

The orchestrator is the **single point that can create agents**. Managers coordinate and plan; the orchestrator executes the spawning. This is a hub-and-spoke model, not recursive delegation.

**Workflow:**

1. **Orchestrator spawns one Manager per repo** — each Manager investigates, plans, creates GitHub issues, and posts to PRs.
2. **Managers do NOT do implementation work inline.** When a Manager needs engineers (for code, reviews, or fixes), they send a **spawn request** back to the orchestrator via SendMessage. The spawn request must include full context: branch name, file paths, acceptance criteria, reviewer pairings, git identity, and any dependencies.
3. **Orchestrator spawns engineers** on behalf of each Manager, routing results back via SendMessage.
4. **Engineers report completion** to the orchestrator, who relays to the Manager or acts on the results.

**Agent naming convention:** All spawned agents MUST be named `{repo-name}-{persona-firstname}` (e.g., `isnad-graph-fatima`, `design-system-hiro`, `deploy-tomasz`). The repo prefix identifies which repo's team the agent belongs to, enabling clear routing in multi-repo sessions. Use the short repo name (without the `noorinalabs-` prefix) for brevity:

| Repo | Prefix |
|------|--------|
| `noorinalabs-isnad-graph` | `isnad-graph-` |
| `noorinalabs-design-system` | `design-system-` |
| `noorinalabs-deploy` | `deploy-` |
| `noorinalabs-landing-page` | `landing-page-` |
| `noorinalabs-main` (cross-repo) | `main-` |

**Anti-pattern:** Giving a Manager a fat prompt that tries to do investigation + coding + PRs + reviews all inline. This bypasses the team structure and produces work without proper review gates.

> **Completion reporting is mandatory:** Every spawned agent MUST send a final status message to the team lead via SendMessage before going idle. This message must include: (1) what was accomplished, (2) any issues or blockers, (3) what the team lead should do next. An agent that completes work but goes silent without reporting forces the orchestrator to reconstruct state manually, which wastes time and risks missed context.

### Team Lifecycle (TeamCreate / TeamDelete)

At the start of every wave or work session that requires agents:

1. **Tell the user** you are tearing down the previous team — state the team name and its full roster (names + roles).
2. Call `TeamDelete`.
3. **Tell the user** you are creating the new team — state the team name and its full roster (names + roles).
4. Call `TeamCreate`.
5. If the roster changed between old and new, **explain why** (new hires, departures, role changes).
6. Then spawn agents.

This must be transparent. The user wants visibility into team lifecycle transitions.

**Force teardown for unresponsive agents:** If `TeamDelete` fails with "Cannot cleanup team with N active members":
1. Send `shutdown_request` to ALL agents first — some may respond.
2. Wait a few seconds.
3. If still stuck, manually edit the config file to remove stale members: `~/.claude/teams/{team-name}/config.json` — keep only the `team-lead` entry.
4. Then `TeamDelete` will succeed.
5. Proceed with `TeamCreate`.

> **Small wave optimization:** For waves with ≤8 issues where all work is well-defined (bugs with clear fixes, straightforward chores), the orchestrator may skip spawning the lead layer (Jelani, Anya) and spawn engineers directly after the Manager provides the execution plan. For larger waves (>8 issues) or waves with architectural ambiguity, spawn leads as coordination-only agents to manage delegation and cross-team dependencies.

## Wave Planning & Priority

### Priority Order

The standard priority order for every wave is:
1. **Hotfixes** (unreviewed commits pushed directly to main from prior wave deploy failures)
2. **Security fixes** (must-fix and should-fix from security reviews)
3. **Bug fixes**
4. **Feature development / chores**

Hotfixes represent known-fragile production state and must be consolidated/reviewed before any new work. All open bugs must be addressed before starting new feature work. If a phase has outstanding bugs, Wave 1 addresses them; new features start in Wave 2 or later.

### Wave Retrospectives

Before every new wave, run a retrospective:

1. Manager spawns retro conversations with each team lead.
2. Each lead discusses with their reports: what went well, what didn't, what to improve.
3. Manager consolidates into a single retro document persisted to `feedback/retro-phase{N}-wave{M}.md`.
4. **Present proposed process changes to the user and explicitly ask which to adopt.** Do NOT assume all are adopted.
5. Only after user approval does the wave's implementation start.

### Knowledge Transfer for Cross-Specialty Reassignment

When work is redistributed to a team member outside their specialty:

1. The new assignee writes their proposed approach in the issue.
2. The domain expert (original specialist) reviews and provides feedback.
3. The assignee incorporates feedback.
4. Only then does implementation begin.

## Bug Management

### Bug Triage

When bugs are discovered, file as GitHub Issues with:
- Label: `bug`
- Repos using the phase/wave system should label bugs with `found-in-phase{N}-wave{M}` and `fixed-in-phase{N}-wave{M}`. Repos without phases use `found-in-wave{M}` / `fixed-in-wave{M}`.

At the start of each wave, triage all open bugs: fix now (assign to current wave) or defer (stays open with labels).

### Bug Closure

Close bug issues when the corresponding fix PR merges. Use `Closes #N` in PR descriptions. If the fix cannot be self-verified (e.g., environment-specific), notify the user to verify before closing.

### Umbrella Tech Debt Decomposition

Umbrella tech-debt issues are acceptable for tracking, but before rolling into a phase:
1. Create individual tech-debt issues from the umbrella.
2. Label each correctly with `tech-debt` + assignee label.
3. Close the original umbrella ticket.

## GitHub Label Hygiene

Before any batch of `gh issue create` calls, verify all labels exist first:
1. Run `gh label list` to check existing labels.
2. Create any missing labels with `gh label create` before creating issues.

Using a non-existent label causes `gh issue create` to fail, blocking parallel issue creation.

## Release & Documentation Process

### Releases

When a deployments branch PR is merged to main, create a GitHub release:
- **Tag format:** Defined in each repo's charter (e.g., `phaseN-waveM` or `waveM`)
- **Title:** Same as the PR title
- **Body:** Same as the PR body

### Post-Wave Production Deployment & Verification

**After every wave completes and the deployments branch is merged to main**, the team MUST:
1. Verify the deploy workflow ran successfully (per the repo's charter for deployment details)
2. Spot-check the live site/service to confirm the deployment is working
3. Report any deployment failures or regressions to the Manager immediately
4. The Manager includes deployment verification status in the wave completion report to the user

**No wave is considered complete until the deployment is verified in production.** If the deploy workflow fails, the DevOps Engineer (Linh) investigates and fixes before proceeding to the next wave.

### Documentation Maintenance

After every wave completes and the deployments branch is PR'd to main:
1. Scan `docs/`, `docs/diagrams/`, and `README.md` against the changes in the PR.
2. Update any stale diagrams or documentation.
3. The System Architect (Arjun) owns diagram accuracy; the Manager owns doc accuracy.

## Automated Enforcement (Git Hooks)

### Pre-commit Hook: Branch Ownership (#494)

**What:** `.githooks/pre-commit` validates that the current branch starts with `{FirstInitial}.{LastName}/` matching the committer's `user.name`.

**Augments:** § Branching Rules → Feature Branches → "Worktree branch safety" paragraph. The manual instruction to "run `git branch --show-current` and confirm" is now enforced automatically.

**Exempt branches:** `main`, `deployments/*`, `worktree-*`, `CEO/*`, and detached HEAD states (rebases).

**Remaining manual steps:** None for standard workflow. Engineers still must use `-c user.name=...` flags — the hook reads that value.

**Emergency override:** `SKIP_BRANCH_CHECK=1 git commit ...`

**Installation:** Included in `.pre-commit-config.yaml` (hook ID: `branch-ownership`). Also runs via `.githooks/pre-commit` when `core.hooksPath` is set.

---

### Commit-msg Hook: Co-Authored-By Trailers (#495)

**What:** `.githooks/commit-msg` validates that every commit includes both required Co-Authored-By trailers: one for the team member (matching a known roster member) and one for Claude.

**Augments:** § Commit Identity. The manual requirement to "include two Co-Authored-By trailers" is now enforced automatically at commit time.

**Validated trailers:**
1. `Co-Authored-By: <roster member name> <parametrization+...@gmail.com>`
2. `Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>`

**Remaining manual steps:** When a new team member is hired (fire-and-replace), their name MUST be added to the `ROSTER_MEMBERS` array in `.githooks/commit-msg`. Without this, their commits will be rejected.

**Emergency override:** `SKIP_TRAILER_CHECK=1 git commit ...`

**Installation:** Included in `.pre-commit-config.yaml` (hook ID: `co-authored-by-trailers`, stage: `commit-msg`). Run `make hooks` to install both pre-commit and commit-msg hooks.

---

### GitHub Branch Protection: Require Review

**What:** GitHub repository rulesets requiring at least 1 approving review on all PRs targeting `deployments/**` branches. Stale reviews are dismissed on new pushes. CODEOWNERS review is not required (we use label-based assignment).

**Augments:** § Code Review & Tech Debt → Peer Review and § Pull Requests → PR Review Workflow. The charter's "No PR may be merged without at least one peer review comment" is now a hard GitHub gate — PRs cannot be merged without an approving review.

**Remaining manual steps:** Peer reviewers must still post an explicit approval (via GitHub review, not just a comment). The ruleset enforces the review but does not verify the reviewer is the designated peer from the wave kickoff.

**Emergency override:** Repository admins can bypass the ruleset via the GitHub UI. This should only be used for hotfix scenarios with Manager approval.

## Automated Skills (Claude Code)

The following Claude Code skills automate recurring team processes. Each skill is a markdown file in `.claude/skills/` and is invoked via `/skill-name` in Claude Code.

### `/wave-kickoff` — Automated Wave Planning

**Skill file:** `.claude/skills/wave-kickoff.md`

**Replaces manual steps in:** § Branching Rules (deployments branch creation), § Wave Planning & Priority (priority ordering), § GitHub Label Hygiene (label creation/validation), § Implementation Kickoff & Issue Assignment (labeling and kickoff comments).

**What is automated:**
- Deployments branch creation from main
- Wave label creation and validation
- Issue labeling (wave label + assignee label)
- Kickoff comments on each issue with reviewer assignments
- Execution plan generation with priority ordering (hotfixes → security → bugs → features)

**What remains manual:**
- User must approve the execution plan before implementation starts
- User decides which issues to include in the wave
- Cross-team dependency resolution still requires lead coordination

**Emergency override:** Skip the skill and perform each step manually using `gh` CLI commands per § Branching Rules and § Implementation Kickoff & Issue Assignment.

### `/wave-retro` — Automated Wave Retrospective

**Skill file:** `.claude/skills/wave-retro.md`

**Replaces manual steps in:** § Wave Retrospectives (retro conversations, consolidation, process change proposals), § Feedback System (trust matrix updates, feedback logging), § Trust Identity Matrix (directional score adjustments).

**What is automated:**
- Merged PR and review comment collection
- Per-engineer performance assessment (CI failures, must-fix counts, delivery quality)
- Trust matrix updates on `CEO/0000-Trust_Matrix` branch
- Feedback log append to `.claude/team/feedback_log.md`
- Charter change proposals based on retro findings

**What remains manual:**
- User must approve all charter changes before they are applied
- Subjective severity calibration may need user override
- User can veto specific trust matrix adjustments

**Emergency override:** Run the retro manually per § Wave Retrospectives — Manager spawns retro conversations with leads, consolidates findings, presents to user.

### `/team-reset` — Transparent Team Lifecycle Management

**Skill file:** `.claude/skills/team-reset.md`

**Replaces manual steps in:** § Team Lifecycle (TeamCreate / TeamDelete) (teardown transparency, force teardown, roster change reporting).

**What is automated:**
- Current team roster reporting to user
- Shutdown requests to all active agents
- Force teardown of unresponsive agents (config file cleanup)
- TeamDelete and TeamCreate calls
- Roster change highlighting (departures, hires, role changes)

**What remains manual:**
- The orchestrating Claude instance must still spawn individual agents after team creation
- Roster file changes (hires/fires) must be committed separately
- User may override the roster before TeamCreate

**Emergency override:** Manually remove the config file (`~/.claude/teams/{team-name}/config.json`) and recreate via TeamCreate.

### `/wave-audit` — Close Orphaned Issues After Wave

**Skill file:** `.claude/skills/wave-audit.md`

**Replaces manual steps in:** § Issue Hygiene (close condition enforcement), § Bug Closure (closing issues when fix PRs merge).

**What is automated:**
- Cross-referencing merged PRs against open issues for the wave
- Identifying orphans (implemented but not auto-closed) via `Closes #N` references and branch naming
- Closing orphans with proper comments and `fixed-in-phase{N}-wave{M}` labels
- Summary reporting of audit results

**What remains manual:**
- User must approve all closures before they execute
- Issues with no implementing PR require manual triage
- The skill relies on `Closes #N` references and branch naming — it does not verify implementation content

**Emergency override:** Run `gh issue list --state open --label "p{N}-wave-{M}"` and close issues manually with `gh issue close`.

## Cross-Repo Coordination Protocol

### When Work Spans Multiple Repos

1. Manager creates a **meta-issue** in `noorinalabs-main` describing the cross-repo feature. The meta-issue:
   - Has label `cross-repo`
   - Lists all affected repos
   - Defines the sequencing (which repo's work must complete first)
   - Links to per-repo issues once they exist

2. Per-repo issues are created in each affected repo's GitHub Issues, with a reference back to the meta-issue: `Cross-repo: noorinalabs/noorinalabs-main#NN`

3. The Manager coordinates sequencing. Typical patterns:
   - Backend API change before frontend integration
   - Shared config change before consumer repos
   - Deploy repo update before service repo deployment changes

### Cross-Repo Waves

When a wave spans repos, the deployments branch convention applies independently in each repo:
- Each repo gets its own deployments branch per its own charter conventions
- The org-level meta-issue tracks completion across all repos
- The Manager does NOT merge cross-repo deployments branches until ALL repos' work for that wave is complete and verified

### GitHub Project Board

The org-level GitHub Project (https://github.com/orgs/noorinalabs/projects/1) tracks all cross-repo work:
- Each repo's issues appear as cards
- Cross-repo features have a "feature" grouping
- The Manager owns the board and updates status

### Label Taxonomy Consistency

All repos MUST use the same label namespace for team labels:
- `FIRSTNAME_LASTNAME` assignee labels (same across all repos)
- `bug`, `tech-debt`, `security`, `cross-repo` (standard set)
- Repo-specific labels (e.g., `found-in-phase{N}-wave{M}`) are defined in each repo's charter

When a new repo is onboarded, the Manager creates all standard labels in that repo using `gh label create`.

### Phases Are Repo-Scoped

Each repo defines its own phase system (or opts out of phases entirely) in its repo charter. Phases are not synchronized across repos. Simple repos may use `deployments/wave-{M}` without a phase prefix.
