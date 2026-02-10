<a id="readme-top"></a>

<!-- PROJECT SHIELDS -->
[![Stars][stars-shield]][stars-url]
[![Forks][forks-shield]][forks-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]

<!-- PROJECT LOGO -->
<br />

<div align="center">
  <p align="center">
    <picture>
      <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/fleetclaw/fleetclaw/main/docs/assets/fleetclaw-logo-text-dark.png">
      <img src="https://raw.githubusercontent.com/fleetclaw/fleetclaw/main/docs/assets/fleetclaw-logo-text.png" alt="FleetClaw" width="500">
    </picture>
  </p>
  <h3>Digital Operators for Every Machine</h3>


  <p align="center">
    A skill library and architecture reference that gives every piece of mining equipment its own AI agent. Built on <a href="https://github.com/openclaw/openclaw">OpenClaw</a>.
    <br />
    <a href="https://github.com/fleetclaw/fleetclaw/issues/new?labels=bug">Report Bug</a>
    ·
    <a href="https://github.com/fleetclaw/fleetclaw/issues/new?labels=enhancement">Request Feature</a>
  </p>

</div>

---

## About The Project

FleetClaw gives every piece of mining equipment its own AI agent. Operators text their machine to log fuel, record meter readings, complete pre-op inspections, and report issues. The system makes compliance feel like a conversation rather than a form.

FleetClaw is a **platform, not a product**. The core system provides agent identities, communication patterns, and behavior definitions. What agents actually do is defined entirely by **skills** -- swappable markdown instructions that organizations can customize, extend, or replace.

This repository contains no executable code. It is a **skill library and architecture reference** designed to be deployed by a coding agent (Claude Code, Codex, etc.) or a human operator following the documentation.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## How It Works

FleetClaw runs three types of agents:

| Agent | Audience | Role |
|-------|----------|------|
| **Asset Agents** | Operators | One per machine. Accepts casual input, logs data, provides feedback, nudges. |
| **Clawvisor** | Mechanics, foremen, supervisors, safety reps | Fleet oversight. Aggregates data, tracks compliance, detects anomalies, accepts maintenance logs. |
| **Clawordinator** | Managers, safety reps, owners | Command layer. Fleet composition, directives, escalation resolution, service management. |

```
Operator texts EX-001: "400l"
  --> Asset agent logs fuel to outbox/, calculates burn rate, responds: "13.2 L/hr, normal range."

Clawvisor reads asset outbox files on heartbeat
  --> Tracks compliance, detects anomalies, routes alerts

Mechanic texts Clawvisor: "replaced hyd pump on EX-001, 6 hours"
  --> Logs maintenance to outbox/, writes acknowledgment to EX-001's inbox/

Next operator session with EX-001:
  --> "Heads up -- hydraulic pump was replaced yesterday. Monitor temps."
```

Agents communicate through **filesystem inbox/outbox directories** containing timestamped markdown files. Each agent runs as its own system user with POSIX ACL-based permissions. See [`docs/communication.md`](docs/communication.md) for the protocol.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Skills-First Architecture

Agents learn behavior from **skills** -- markdown files containing plain English instructions, not code. Each agent role has its own skill set:

**Asset Agent:** `fuel-logger` `meter-reader` `pre-op` `issue-reporter` `nudger` `memory-curator`

**Clawvisor:** `fleet-status` `compliance-tracker` `maintenance-logger` `anomaly-detector` `shift-summary` `escalation-handler` `asset-query` `memory-curator`

**Clawordinator:** `asset-onboarder` `asset-lifecycle` `fleet-director` `escalation-resolver` `fleet-analytics` `fleet-config` `memory-curator`

Organizations extend the platform by writing new skills. A Tier 2 skill like `tire-pressure-logger` just needs a `SKILL.md` following the template -- deploy it to the agent's skills directory, and the agent picks it up. See [`docs/skill-authoring.md`](docs/skill-authoring.md) for the guide.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Getting Started

Point your coding agent (Claude Code, Codex, etc.) at [`AGENTS.md`](AGENTS.md) and provide your fleet's asset list. The coding agent will:

1. Create system users for each agent
2. Install and configure OpenClaw per agent
3. Inject FleetClaw skills and identity documents
4. Set filesystem permissions
5. Start agent services
6. Initialize `fleet.md` with your fleet composition

For manual setup, see [`docs/implementation.md`](docs/implementation.md) and the platform-specific guide in [`platform/`](platform/).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Repo Structure

```
fleetclaw/
├── AGENTS.md                       # Coding agent entry point
├── CLAUDE.md                       # Claude Code guidance
├── docs/
│   ├── architecture.md             # System design and agent roles
│   ├── communication.md            # Filesystem message protocol
│   ├── permissions.md              # POSIX ACL permission model
│   ├── implementation.md           # Setup and deployment guide
│   ├── skill-authoring.md          # Skill writing guide and philosophy
│   └── customization.md            # Extending FleetClaw for your org
├── skills/
│   ├── SKILL-TEMPLATE.md           # Blank scaffolding for new skills
│   ├── fuel-logger/SKILL.md        # 21 Tier 1 skills, one per directory
│   ├── meter-reader/SKILL.md
│   └── ...
├── templates/                      # SOUL.md templates per agent role
└── platform/                       # OS-specific references (Ubuntu, macOS, Windows)
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Documentation

| Document | Description |
|----------|-------------|
| [`AGENTS.md`](AGENTS.md) | Entry point for coding agents -- setup flow and architecture overview |
| [`docs/architecture.md`](docs/architecture.md) | System design -- agents, data flow, communication, permissions |
| [`docs/communication.md`](docs/communication.md) | Filesystem message protocol -- inbox/outbox format, state.md, fleet.md |
| [`docs/permissions.md`](docs/permissions.md) | POSIX ACL permission model for multi-agent filesystem access |
| [`docs/implementation.md`](docs/implementation.md) | How to set up agents -- OpenClaw install, FleetClaw injection, services |
| [`docs/skill-authoring.md`](docs/skill-authoring.md) | How to write skills -- philosophy, conventions, complete examples |
| [`docs/customization.md`](docs/customization.md) | Extending FleetClaw -- custom skills, messaging channels, multi-site |
| [`platform/ubuntu.md`](platform/ubuntu.md) | Ubuntu 24.04 platform reference |
| [`platform/macos.md`](platform/macos.md) | macOS platform reference |
| [`platform/windows.md`](platform/windows.md) | Windows platform reference |

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Contributing

Contributions make the open source community an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## License

Distributed under the MIT License. See `LICENSE` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Acknowledgments

* [OpenClaw](https://github.com/openclaw/openclaw) by [@steipete](https://github.com/steipete) -- The AI agent framework
* [Best-README-Template](https://github.com/othneildrew/Best-README-Template) -- README inspiration
* [Shields.io](https://shields.io) -- Badges

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->

[stars-shield]: https://img.shields.io/github/stars/fleetclaw/fleetclaw.svg?style=for-the-badge
[stars-url]: https://github.com/fleetclaw/fleetclaw/stargazers
[forks-shield]: https://img.shields.io/github/forks/fleetclaw/fleetclaw.svg?style=for-the-badge
[forks-url]: https://github.com/fleetclaw/fleetclaw/network/members
[issues-shield]: https://img.shields.io/github/issues/fleetclaw/fleetclaw.svg?style=for-the-badge
[issues-url]: https://github.com/fleetclaw/fleetclaw/issues
[license-shield]: https://img.shields.io/github/license/fleetclaw/fleetclaw.svg?style=for-the-badge
[license-url]: https://github.com/fleetclaw/fleetclaw/blob/main/LICENSE
