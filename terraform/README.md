# Terraform — Hetzner Cloud Provisioning

Provisions a Hetzner Cloud VPS (CPX41) for the isnad-graph production deployment.

## Resources Created

- **VPS**: CPX41 (8 vCPU, 16 GB RAM) running Ubuntu 24.04 in Ashburn (ash)
- **Firewall**: Allows inbound TCP on ports 22 (SSH), 80 (HTTP), 443 (HTTPS); denies all else
- **SSH Key**: Uploaded from a local public key file

## Prerequisites

- [Terraform >= 1.5](https://developer.hashicorp.com/terraform/install)
- A Hetzner Cloud API token (create one at https://console.hetzner.cloud)
- An SSH key pair

## Usage

```bash
cd terraform/

# Initialize providers
terraform init

# Preview changes
terraform plan -var="hcloud_token=YOUR_TOKEN"

# Apply
terraform apply -var="hcloud_token=YOUR_TOKEN"

# Destroy when no longer needed
terraform destroy -var="hcloud_token=YOUR_TOKEN"
```

To avoid passing the token on every command, create a `terraform.tfvars` file (git-ignored):

```hcl
hcloud_token       = "your-token-here"
ssh_public_key_path = "~/.ssh/id_ed25519.pub"
```

## Variables

| Name | Description | Default |
|------|-------------|---------|
| `hcloud_token` | Hetzner Cloud API token (sensitive) | — |
| `ssh_public_key_path` | Path to SSH public key | `~/.ssh/id_ed25519.pub` |
| `server_type` | Hetzner server type | `cpx41` |
| `server_name` | Instance name | `isnad-graph-prod` |
| `location` | Hetzner location | `ash` |

## Outputs

| Name | Description |
|------|-------------|
| `server_ip` | Public IPv4 address for DNS setup |
| `server_ipv6` | Public IPv6 address |
| `server_status` | Current server status |

## State

State is stored locally in `terraform.tfstate` (git-ignored). Do not commit state files.
