# GitHub Secrets

All production credentials and deployment keys are stored as GitHub Actions secrets.
They are injected into CI/CD workflows at runtime and never committed to the repository.

## Required Secrets

| Secret Name | Purpose |
|---|---|
| `DEPLOY_SSH_PRIVATE_KEY` | SSH private key for deploying to Hetzner VPS |
| `HETZNER_API_TOKEN` | Hetzner Cloud API token (Terraform provisioning) |
| `B2_APPLICATION_KEY_ID` | Backblaze B2 application key ID (backups) |
| `B2_APPLICATION_KEY` | Backblaze B2 application key (backups) |
| `NEO4J_USER` | Production Neo4j username |
| `NEO4J_PASSWORD` | Production Neo4j password |
| `POSTGRES_USER` | Production PostgreSQL username |
| `POSTGRES_PASSWORD` | Production PostgreSQL password |
| `POSTGRES_DB` | Production PostgreSQL database name |
| `REDIS_PASSWORD` | Production Redis password |

## Which Workflows / Services Use Each Secret

| Secret | Workflow / Service |
|---|---|
| `DEPLOY_SSH_PRIVATE_KEY` | `deploy.yml` — SSH into VPS to run deployment |
| `HETZNER_API_TOKEN` | Terraform provisioning (manual / future IaC pipeline) |
| `B2_APPLICATION_KEY_ID` | Backup scripts on VPS (`infra/backup/`) |
| `B2_APPLICATION_KEY` | Backup scripts on VPS (`infra/backup/`) |
| `NEO4J_USER` | `deploy.yml` — passed to `docker-compose.prod.yml` |
| `NEO4J_PASSWORD` | `deploy.yml` — passed to `docker-compose.prod.yml` |
| `POSTGRES_USER` | `deploy.yml` — passed to `docker-compose.prod.yml` |
| `POSTGRES_PASSWORD` | `deploy.yml` — passed to `docker-compose.prod.yml` |
| `POSTGRES_DB` | `deploy.yml` — passed to `docker-compose.prod.yml` |
| `REDIS_PASSWORD` | `deploy.yml` — passed to `docker-compose.prod.yml` |

## Adding or Updating Secrets

1. Go to the GitHub repository page.
2. Navigate to **Settings** > **Secrets and variables** > **Actions**.
3. Click **New repository secret** (or **Update** on an existing one).
4. Enter the secret name exactly as shown in the table above.
5. Paste the value and click **Add secret**.

Only repository admins can add or update secrets. Secret values cannot be viewed
after creation — they can only be replaced.

## Security Reminders

- **Never** commit secrets, tokens, or passwords to the repository.
- Rotate all passwords and API tokens periodically (at least every 90 days).
- Use strong, randomly generated passwords (minimum 32 characters for service passwords).
- If a secret is suspected to be compromised, rotate it immediately and redeploy.
- The `DEPLOY_SSH_PRIVATE_KEY` should be an Ed25519 key dedicated to deployment — do not reuse personal SSH keys.
- Backblaze B2 application keys should be scoped to the specific backup bucket only.
