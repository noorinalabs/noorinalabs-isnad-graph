# Backup & Restore

Automated backup system for isnad-graph production databases (PostgreSQL + Neo4j) to Backblaze B2.

## Overview

| Component | Method | Format | Compression |
|-----------|--------|--------|-------------|
| PostgreSQL | `pg_dump -Fc` (via Docker exec) | Custom format (built-in compression) | N/A (already compressed) |
| Neo4j | `neo4j-admin database dump` (offline) | Binary dump | zstd (`-3`) |
| Redis | Skipped | — | — |

Backups are uploaded to Backblaze B2 via rclone with SHA256 checksum sidecar files.

## Prerequisites

- `rclone` installed on the VPS (`/usr/local/bin/rclone`)
- `zstd` installed (`apt install zstd`)
- Docker and Docker Compose available
- Backblaze B2 account with bucket created (see issue #305)

## Environment Variables

Add these to `/opt/isnad-graph/.env`:

```bash
# Backblaze B2 credentials
B2_KEY_ID=your-key-id
B2_APP_KEY=your-application-key
B2_BUCKET=isnad-graph-backups
```

Optional overrides:

```bash
BACKUP_DIR=/tmp/isnad-backups     # Local staging directory
DAILY_RETAIN=7                     # Days to keep daily backups
WEEKLY_RETAIN=4                    # Weeks to keep weekly backups
```

Credentials are passed to rclone via native environment variables (`RCLONE_CONFIG_ISNAD_*`), never via CLI flags.

## Backup Schedule

Backups run daily at 03:00 UTC via systemd timer:

- **Daily backups** (Mon-Sat): stored in `daily/YYYY-MM-DD/`
- **Weekly backups** (Sunday): stored in `weekly/YYYY-MM-DD/`

### Retention Policy

| Category | Retention |
|----------|-----------|
| Daily | 7 days |
| Weekly | 4 weeks (28 days) |

Pruning uses date-stamped directory names (not remote file mtime) for deterministic behavior.

## B2 Bucket Structure

```
isnad-graph-backups/
├── daily/
│   ├── 2026-03-24/
│   │   ├── isnad-pg-20260324-030012.dump
│   │   ├── isnad-pg-20260324-030012.dump.sha256
│   │   ├── isnad-neo4j-20260324-030012.dump.zst
│   │   └── isnad-neo4j-20260324-030012.dump.zst.sha256
│   └── 2026-03-25/
│       └── ...
└── weekly/
    └── 2026-03-23/
        └── ...
```

## Running Backups

### Manual backup

```bash
cd /opt/isnad-graph
./scripts/backup.sh
```

### Dry run (shows retention pruning without deleting)

```bash
DRY_RUN=true ./scripts/backup.sh
```

### View logs

```bash
# systemd journal
journalctl -u isnad-backup.service --since today

# Backup log files
ls /tmp/isnad-backups/backup-*.log
```

## Restoring

### List available backups

```bash
./scripts/restore.sh --list
```

### Restore most recent backup

```bash
./scripts/restore.sh latest
```

### Restore specific date

```bash
./scripts/restore.sh daily/2026-03-25
```

### Force restore (skip confirmation prompt)

```bash
./scripts/restore.sh --force daily/2026-03-25
```

### Restore process

1. Downloads backup files from B2
2. Verifies SHA256 checksums
3. Prompts for confirmation (unless `--force`)
4. Restores PostgreSQL: terminates active connections, runs `pg_restore --clean --if-exists`
5. Restores Neo4j: stops Neo4j, loads dump with `neo4j-admin database load --overwrite-destination`, restarts

## Neo4j Downtime

Neo4j must be stopped for both backup and restore (community edition limitation). Expected downtime:

- **Backup:** 10-30 seconds (dump only, restart immediate)
- **Restore:** 30-120 seconds (depends on data size)

The backup script automatically restarts Neo4j and waits for it to become healthy.

## systemd Installation

```bash
# Copy unit files
sudo cp systemd/isnad-backup.service /etc/systemd/system/
sudo cp systemd/isnad-backup.timer /etc/systemd/system/

# Enable and start the timer
sudo systemctl daemon-reload
sudo systemctl enable --now isnad-backup.timer

# Verify timer is active
systemctl list-timers isnad-backup.timer
```

## Troubleshooting

### Backup fails with "Cannot find Neo4j data volume"

The script looks for a Docker volume ending in `neo4j_data` or `neo4j-data`. Check your volume names:

```bash
docker volume ls | grep neo4j
```

### pg_restore warnings

`pg_restore` with `--clean --if-exists` commonly emits warnings like "role already exists" -- these are harmless.

### Checksum mismatch on restore

The restore script aborts if any checksum fails. Re-download the backup or try an older backup:

```bash
./scripts/restore.sh --list
./scripts/restore.sh daily/2026-03-24  # try previous day
```
