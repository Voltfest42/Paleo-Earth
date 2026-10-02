# Paleo Earth: Workflow Guidelines

## Version Control and Deployment
- **Git Repository**: The project uses a local Git repository synchronized with a remote GitHub repository.
- **Committing Changes**: All significant code changes should be committed with clear, descriptive commit messages and pushed to the GitHub `main` branch.
- **AWS Deployment**: After code changes are verified, static assets (`index.html`, `js/`, `css/`) must be synced to the AWS S3 bucket. Always create a CloudFront invalidation (`/*`) immediately after syncing to ensure users receive the latest version.

## Task Delegation (Claude CLI)
- For heavy workloads, bulk refactors, or extensive file modifications that risk depleting token quotas in Antigravity, delegate tasks to the **Claude Code CLI** agent.
- Unless explicitly stated otherwise by the user, invoke the Claude agent using the **Claude 3.5 Sonnet** model.
