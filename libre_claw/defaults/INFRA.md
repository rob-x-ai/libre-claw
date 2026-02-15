# INFRA.md - Infrastructure Documentation

Your computers, projects, servers, and infrastructure. Read on-demand, not at startup.

---

## Machines

### Local Workstation

- **Name**: [hostname]
- **OS**: [operating system]
- **CPU**: [processor]
- **RAM**: [amount]
- **GPU**: [if applicable]

### Remote Servers

- **Server 1**: [hostname/IP]
  - Purpose: [what it runs]
  - Access: [SSH user@host]
  - Services: [list of services]

## Services

### Self-Hosted

- [Service 1]: [URL] — [description]
- [Service 2]: [URL] — [description]

### Cloud/SaaS

- [Service]: [purpose]

## Projects

### Active

- **[Project 1]**: [description, repo URL]
- **[Project 2]**: [description, repo URL]

### Archived

- [Old projects for reference]

## Networking

- **Domain**: [your domain]
- **DNS**: [provider]
- **VPN/Tailnet**: [if applicable]

## Credentials

⚠️ **Do NOT store secrets in this file.** Use environment variables, `.env` files, or a secrets manager. Reference where to find credentials, not the credentials themselves.

- SSH keys: `~/.ssh/`
- API keys: `~/.config/libre-claw/.env`
