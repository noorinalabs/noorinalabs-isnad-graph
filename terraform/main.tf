provider "hcloud" {
  token = var.hcloud_token
}

resource "hcloud_ssh_key" "deploy" {
  name       = "${var.server_name}-deploy"
  public_key = file(var.ssh_public_key_path)
}

resource "hcloud_firewall" "web" {
  name = "${var.server_name}-firewall"

  # PRODUCTION: restrict ssh_source_ips to your operator IPs or VPN CIDR.
  # The default (0.0.0.0/0) is intentionally open for initial setup only.
  rule {
    description = "Allow SSH"
    direction   = "in"
    protocol    = "tcp"
    port        = "22"
    source_ips  = var.ssh_source_ips
  }

  rule {
    description = "Allow HTTP"
    direction   = "in"
    protocol    = "tcp"
    port        = "80"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }

  rule {
    description = "Allow HTTPS"
    direction   = "in"
    protocol    = "tcp"
    port        = "443"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }
}

resource "hcloud_server" "app" {
  name        = var.server_name
  server_type = var.server_type
  datacenter  = var.datacenter
  image       = "ubuntu-24.04"

  ssh_keys = [hcloud_ssh_key.deploy.id]

  firewall_ids = [hcloud_firewall.web.id]

  labels = {
    project     = "isnad-graph"
    environment = "production"
  }
}
