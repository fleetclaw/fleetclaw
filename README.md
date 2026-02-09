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
    AI-powered fleet management that gives every piece of equipment its own dedicated digital assistant.
    <br />
    <a href="https://github.com/fleetclaw/fleetclaw/issues/new?labels=bug">Report Bug</a>
    ·
    <a href="https://github.com/fleetclaw/fleetclaw/issues/new?labels=enhancement">Request Feature</a>
  </p>

</div>

<!-- TABLE OF CONTENTS -->

---

## About The Project

FleetClaw is a platform that gives every piece of mining equipment its own AI agent. Operators text their machine via Telegram to log fuel, record meter readings, complete pre-op inspections, and report issues. The system makes compliance feel like a conversation rather than a form.

Built on [OpenClaw](https://github.com/openclaw/openclaw), each agent runs in its own Docker container with its own identity, memory, and skills. Agents communicate through Redis and persist context through curated markdown files.

FleetClaw is a **platform, not a product**. The core system provides agents, communication, and infrastructure. What those agents actually do is defined by **skills** -- swappable markdown instructions that organizations can customize, extend, or replace.

### Built With

* ![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
* ![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)
* ![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat&logo=redis&logoColor=white)
* ![Telegram](https://img.shields.io/badge/Telegram-26A5E4?style=flat&logo=telegram&logoColor=white)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## How It Works

FleetClaw runs three types of agents:

| Agent | Audience | Role |
|-------|----------|------|
| **Asset Agents** | Operators | One per machine. Accepts casual input, logs data, provides feedback, nudges. |
| **Clawvisor** | Mechanics, foremen, supervisors, safety reps | Fleet oversight. Aggregates data, tracks compliance, detects anomalies, accepts maintenance logs. |
| **Clawordinator** | Managers, safety reps, owners | Command layer. Fleet composition, directives, escalation resolution, infrastructure control. |

```
Operator texts EX-001: "400l"
  --> Asset agent logs fuel, calculates burn rate, responds: "13.2 L/hr, normal range."
  --> Redis stream event

Clawvisor reads Redis on heartbeat
  --> Tracks compliance, detects anomalies, routes alerts

Mechanic texts Clawvisor: "replaced hyd pump on EX-001, 6 hours"
  --> Logs maintenance, sends acknowledgment to EX-001's inbox

Next operator session with EX-001:
  --> "Heads up -- hydraulic pump was replaced yesterday. Monitor temps."
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Skills-First Architecture

Agents learn behavior from **skills** -- markdown files containing plain English instructions, not code. Each agent role (asset, clawvisor, clawordinator) has its own skill set:

**Asset Agent:** `fuel-logger` `meter-reader` `pre-op` `issue-reporter` `nudger` `memory-curator`

**Clawvisor:** `fleet-status` `compliance-tracker` `maintenance-logger` `anomaly-detector` `shift-summary` `escalation-handler` `asset-query` `memory-curator`

**Clawordinator:** `asset-onboarder` `asset-lifecycle` `fleet-director` `escalation-resolver` `fleet-analytics` `fleet-config` `memory-curator`

Organizations extend the platform by writing new skills. A Tier 2 skill like `tire-pressure-logger` just needs a `SKILL.md` following the template -- mount it, and the agent picks it up. See [`docs/skill-authoring.md`](docs/skill-authoring.md) for the guide.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Quick Start

### Prerequisites

- Linux server with Docker and Docker Compose
- One Telegram bot token per agent (create via [@BotFather](https://t.me/botfather))
- [Fireworks](https://fireworks.ai) API key (or other LLM provider)

### Setup

```bash
# 1. Configure your fleet
cp fleet.yaml.example fleet.yaml
# Edit fleet.yaml -- add your assets, contacts, timezone

# 2. Generate configs
python generate-configs.py
# Creates output/ with workspaces, configs, compose, env template, redis setup

# 3. Fill in credentials
cp output/.env.template .env
# Edit .env -- add Telegram bot tokens, API keys

# 4. Initialize Redis
bash output/setup-redis.sh

# 5. Launch
docker compose -f output/docker-compose.yml --project-directory . up -d
```

Each agent creates its own `MEMORY.md` on the first operator interaction. No manual initialization needed.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Repo Structure

```
fleetclaw/
├── generate-configs.py          # Reads fleet.yaml, produces all output
├── fleet.yaml.example           # Example fleet configuration
├── docs/
│   ├── architecture.md          # System design and agent roles
│   ├── redis-schema.md          # Authoritative Redis key reference
│   ├── skill-authoring.md       # Skill writing guide and philosophy
│   └── implementation.md        # How design maps to OpenClaw/Docker/Redis
├── skills/
│   ├── SKILL-TEMPLATE.md        # Blank scaffolding for new skills
│   ├── fuel-logger/SKILL.md     # 21 Tier 1 skills, one per directory
│   ├── meter-reader/SKILL.md
│   └── ...
├── templates/                   # SOUL.md and openclaw.json templates
└── docker/                      # Dockerfiles (standard + clawordinator)
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Documentation

| Document | Description |
|----------|-------------|
| [`docs/architecture.md`](docs/architecture.md) | System design -- agents, data flow, Redis schema, deployment model |
| [`docs/redis-schema.md`](docs/redis-schema.md) | Every Redis key pattern with field definitions and retention rules |
| [`docs/skill-authoring.md`](docs/skill-authoring.md) | How to write skills -- philosophy, conventions, complete examples |
| [`docs/implementation.md`](docs/implementation.md) | How the design maps to OpenClaw config, Docker volumes, Redis commands |

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
