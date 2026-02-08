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

<details>
  <summary>Table of Contents</summary>
  <ol>
    <li><a href="#about-the-project">About The Project</a></li>
    <li><a href="#how-it-works-key-concepts">How It Works: Key Concepts</a></li>
    <li><a href="#openclaw-integration-the-hiring-process">OpenClaw Integration</a></li>
    <li><a href="#why-this-matters">Why This Matters</a></li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#architecture">Architecture</a></li>
    <li><a href="#technical-reference">Technical Reference</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>


---

## About The Project

FleetClaw is a system that creates a **dedicated digital assistant for every single machine in your fleet.**

Instead of one big, messy software program trying to manage 500 trucks, FleetClaw automatically generates 500 small, specialized "agents." Each agent cares only about its specific machine—tracking its fuel, checking its hours, and flagging maintenance—and then reports back to a central coordinator.

Think of **OpenClaw** as a smart, digital worker you can hire. It has a brain (AI), it can read instructions, and it can communicate.

Think of **FleetClaw** as the HR and Onboarding department.

FleetClaw doesn't build the brain from scratch. It automatically hires, trains, and assigns a specific "Digital Operator" to every single piece of equipment in your fleet—whether you have 5 trucks or 500.

**Scope:** FleetClaw targets mobile and semi-mobile equipment (excavators, haul trucks, loaders, dozers, graders, etc.). Fixed plant equipment like crushers, screens, and conveyors are out of scope.

### Built With

* ![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
* ![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)
* ![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat&logo=redis&logoColor=white)
* ![Telegram](https://img.shields.io/badge/Telegram-26A5E4?style=flat&logo=telegram&logoColor=white)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---



<p align="right">(<a href="#readme-top">back to top</a>)</p>

---



<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Getting Started

Follow these steps to get FleetClaw running locally or on your VPS.

### Prerequisites

* **Python 3.10+** with pip
* **Docker** and Docker Compose
* **Telegram Bot Tokens** — One per asset (create via [@BotFather](https://t.me/BotFather))
* **Fireworks AI API Key** — For the AI agents (uses Kimi K2.5 model)

### Installation

1. **Clone the repository**

   ```bash
   
   ```

2. **Copy configuration templates**

   ```bash
   cp config/fleet.yaml.example config/fleet.yaml
   cp config/.env.template config/.env
   ```

3. **Configure your fleet**

   Edit `config/fleet.yaml` to define your assets:

   ```yaml
   assets:
     - asset_id: EX-001
       type: excavator
       make: CAT
       model: 390F
       host: host-01
       specs:
         tank_capacity: 680
         avg_consumption: 28
       telegram_group: "@ex001_ops"
   ```

4. **Set environment variables**

   Edit `config/.env` with your API keys:

   ```bash
   FIREWORKS_API_KEY=...
   TELEGRAM_TOKEN_EX_001=123456:ABC...  # One token per asset
   ```

5. **Generate configurations**

   ```bash
   python scripts/generate-configs.py
   ```

6. **Deploy**

   ```bash
   cd generated/
   docker compose up -d
   ```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Usage

### Chatting with Your Equipment

Open Telegram and message your asset's bot directly:

```
You: Added 400L diesel
EX-001: Logged 400L at 14:32. Tank now at 85%. Hour meter: 8,542h.
```

### Common Operations

```bash
# Preview what would be generated (dry run)
python scripts/generate-configs.py --dry-run

# Regenerate a single asset
python scripts/generate-configs.py --target-asset EX-001

# Check asset status
python scripts/asset_lifecycle.py status

# Wake an idle asset
python scripts/asset_lifecycle.py wake EX-001
```

_For more examples, see the [Technical Reference](#technical-reference) section._

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Architecture

```

```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Technical Reference

### Skills

Each asset workspace includes these skills:

- 

### Escalation Levels

- **Level 1** — Data anomaly (minor) → Flag for operator confirmation
- **Level 2** — Repeated anomaly or ignored flag → Notify supervisor
- **Level 3** — Safety concern or maintenance due → Notify safety officer + supervisor
- **Level 4** — Critical: untracked operation detected → Notify owner, recommend grounding

At Level 4, the asset posts hourly to all channels and recommends grounding itself.

### Directory Structure

```

```

### Adding Assets

**Bulk import from CSV:**

```bash
# Validate CSV before import
python scripts/csv_import.py --csv assets.csv --host my-host --dry-run

# Import and create new host with Redis
python scripts/csv_import.py --csv assets.csv --host new-host --create-host --redis
```

**Interactive script:**

```bash
./scripts/add-asset.sh
```

**Programmatically (used by Fleet Clawordinator):**

```bash
python scripts/auto_onboard.py --json '{"asset_id":"EX-005","type":"excavator","host":"host-01"}'
```

Or manually edit `config/fleet.yaml` and re-run `generate-configs.py`.

### Asset Lifecycle

Assets automatically idle after 7 days of inactivity and wake on operator messages:

```bash
python scripts/asset_lifecycle.py status           # Show all asset states
python scripts/asset_lifecycle.py wake EX-001      # Wake an idle asset
python scripts/asset_lifecycle.py nightly-check    # Run idle check
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Roadmap

- [x] Core config generation from YAML
- [x] Per-asset OpenClaw workspaces
- [x] Telegram bot integration
- [x] Redis `fleet:*` key-based status for inter-asset comms
- [x] Idle management and wake-on-demand
- [x] Bulk CSV import
- [ ] GPS hub or activity tracking API integration
- [ ] Dashboard UI for fleet overview
- [ ] Mobile app for offline fuel logging

See the [open issues](https://github.com/fleetclaw/fleetclaw/issues) for a full list of proposed features and known issues.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Relationship to OpenClaw

FleetClaw generates configs **for** OpenClaw but doesn't include OpenClaw itself. OpenClaw is pulled as a Docker image at deployment time.

**To update OpenClaw:**

```bash
docker pull ghcr.io/openclaw/openclaw:2026.2.6
docker compose up -d
```

**OpenClaw repository:** [github.com/openclaw/openclaw](https://github.com/openclaw/openclaw)

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

### Key Principles

1. **Assets are the authority** — Not databases, not operators
2. **Trust no single source** — Cross-reference everything
3. **Escalate relentlessly** — Until someone acts
4. **Keep it simple** — YAML in, Docker out

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## License

Distributed under the MIT License. See `LICENSE` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Acknowledgments

* [OpenClaw](https://github.com/openclaw/openclaw) by [@steipete](https://github.com/steipete) — The AI agent framework
* [Best-README-Template](https://github.com/othneildrew/Best-README-Template) — README inspiration
* [Shields.io](https://shields.io) — Badges

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
