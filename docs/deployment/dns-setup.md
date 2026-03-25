# DNS Setup Guide

This guide covers configuring DNS for `isnad-graph.how-a-steve-do.com` using Squarespace DNS management.

## Why a Subdomain?

Squarespace locks the root `@` A record when a domain is connected to a Squarespace site. You cannot override it to point at an external server. The solution is to use a **subdomain** (`isnad-graph`) which Squarespace allows you to configure freely via custom DNS records.

## Prerequisites

- Access to the Squarespace account managing `how-a-steve-do.com`
- Terraform provisioned VPS (to get the server IP)

## Step 1: Get the VPS IP Address

From the project root, run:

```bash
cd terraform && terraform output server_ip
```

Note this IP address — you will enter it as the DNS record value.

## Step 2: Add the A Record in Squarespace

1. Log in to [Squarespace](https://www.squarespace.com/)
2. Navigate to **Settings** → **Domains**
3. Click on **how-a-steve-do.com**
4. Click **DNS Settings**
5. Click **Add Custom Record**
6. Fill in the fields:

| Field | Value |
|-------|-------|
| **Host** | `isnad-graph` |
| **Type** | `A` |
| **Data / Value** | `<VPS IP from terraform output>` |
| **TTL** | Lowest available (e.g., 1 hour) while testing |

7. Click **Save**

## Step 3 (Optional): Add an AAAA Record for IPv6

If your VPS has an IPv6 address, you can optionally add an AAAA record:

```bash
cd terraform && terraform output server_ipv6
```

Repeat the same steps above, but select **Type** `AAAA` and use the IPv6 address as the value.

## DNS Propagation

DNS changes typically propagate within **minutes to one hour**, though in rare cases it can take longer. Squarespace DNS updates are generally fast since changes apply directly to their authoritative nameservers.

## TTL Recommendations

- **During initial setup and testing:** Use the lowest TTL available (typically 1 hour on Squarespace). This allows quick corrections if you need to change the IP.
- **After stable operation:** Increase TTL to reduce DNS lookup overhead. A TTL of 1–4 hours is reasonable for a production service.

## Verification

### Check DNS Resolution

```bash
dig isnad-graph.how-a-steve-do.com +short
```

This should return your VPS IP address. If it returns nothing, wait a few minutes for propagation and try again.

### Check HTTPS (After TLS Is Configured)

```bash
curl -I https://isnad-graph.how-a-steve-do.com
```

You should see an HTTP 200 (or redirect) response with valid TLS headers.

### Check SSH Access

```bash
ssh -i ~/.ssh/isnad_deploy root@isnad-graph.how-a-steve-do.com
```

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `dig` returns nothing | DNS not propagated yet, or record not saved | Wait 15–60 minutes; verify the record exists in Squarespace |
| `dig` returns wrong IP | Stale cache or incorrect record value | Verify the A record value matches `terraform output server_ip`; flush local DNS cache |
| SSH times out | Firewall blocking port 22 or DNS not resolving | Confirm `dig` returns the correct IP; check VPS firewall rules |
| `curl` TLS error | TLS not yet configured on the server | Set up the reverse proxy and TLS first (see Caddy/TLS setup docs) |
