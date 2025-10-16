# 🔮 Capsule - Beautiful Server Configuration

Dead-simple NixOS/Nix server setup with **named profiles**, modular technology stacks, gorgeous ASCII UI, and declarative Nix configurations.

## Installation

### Quick Install (Recommended)
```bash
# Using Nix flakes
nix profile install .

# Or traditional Nix
nix-env -if .

# Or using Python pip (for development)
pip3 install --user -e .
```

### Alternative: Build with Nix
```bash
nix build
./result/bin/capsule --help
```

## Quick Start

```bash
# See available technology stacks
capsule config stacks

# Add technology stacks you want
capsule config add docker
capsule config add python

# Add custom packages
capsule config pkg add jq tmux htop

# Review your configuration
capsule config show

# Preview generated Nix configuration
capsule preview

# Apply configuration (generates NixOS/home-manager config)
capsule setup

# View interactive documentation
capsule docs
```

## Commands

### Profile Management

```bash
capsule config profiles                      # List all profiles (built-in and user)
capsule config profile use <name>            # Switch to a profile
capsule config profile import <name>         # Import built-in profile to customize
capsule config profile new <name>            # Create new profile
capsule config profile new <name> --copy-from=<source>  # Create from existing
capsule config profile copy <src> <dest>     # Copy a profile
capsule config profile delete <name>         # Delete a profile
```

### Built-in Profiles

Capsule ships with pre-configured profiles:

| Profile | Description | Stacks Included |
|---------|-------------|-----------------|
| `dev` | Full-stack development environment | python, nodejs, docker, github, cli-tools |
| `prod` | Production web server with security | webserver, security, monitoring |
| `ml` | Machine learning workstation | python, machine-learning, ollama |
| `ml-gpu` | ML workstation with GPU support | python, machine-learning, ollama, cuda |
| `web` | Web development environment | nodejs, docker, github |
| `minimal` | Minimal setup with essential tools | base packages only |

## Technology Stack Management

```bash
capsule config stacks              # List available technology stacks
capsule config show                # Show current configuration
capsule config add <stack>         # Add a technology stack to your config
capsule config remove <stack>      # Remove a technology stack
capsule config edit                # Edit config file directly
capsule config reset               # Reset to defaults
```

## Available Technology Stacks

All stacks are defined as Nix expressions:

| Stack | Description | Dependencies |
|--------|-------------|--------------|
| `github` | GitHub CLI (gh) for repo management | - |
| `nodejs` | Node.js LTS and npm | - |
| `devtools` | Essential dev tools (gnumake, cmake, gdb, strace) | - |
| `cli-tools` | Modern CLI utilities (jq, ripgrep, fzf, bat) | - |
| `docker` | Docker and Docker Compose | - |
| `python` | Python 3, pip, venv, and dev tools | - |
| `golang` | Go language and tools | - |
| `rust` | Rust toolchain | - |
| `database` | PostgreSQL and Redis | - |
| `monitoring` | System monitoring tools (htop, iotop) | - |
| `security` | Security tools (ufw, fail2ban) | - |
| `webserver` | Nginx web server | - |
| `machine-learning` | ML tools and libraries | Requires: `python` |
| `ollama` | Local LLM runtime | Optional: `cuda` |
| `cuda` | NVIDIA CUDA for GPU acceleration | - |

## Configuration File

Your configuration is stored at `~/.capsule/configs/<profile-name>.yml`:

```yaml
stacks:
  - base
  - docker
  - python
custom_packages:
  - jq
  - tmux
```

## Remote Deployment

```bash
capsule plant user@hostname      # Deploy Capsule to remote (via Nix)
capsule plant user@host --no-bootstrap  # Skip bootstrap step
capsule plant user@host -p 2222  # Use custom SSH port
capsule plant user@host -i ~/.ssh/key  # Use specific SSH key
```

## Requirements

**Local machine:**
- Nix (with flakes enabled recommended)
- Python 3.7+ (for CLI)

**Remote server (deployment target):**
- NixOS or Nix package manager
- SSH access

## Notes

- Configurations are declarative Nix expressions
- All operations are idempotent (safe to run multiple times)
- Use `capsule preview` to see the generated Nix configuration
- Compatible with NixOS and home-manager

## Global Installation

To install capsule as a global command:

```bash
./install.sh
```

Or manually:
```bash
pip3 install --user -e .
```

Verify:
```bash
capsule --version
capsule openmesh providers
```

See [INSTALL.md](INSTALL.md) for detailed installation instructions.

---

**Installed Location:** `~/.local/bin/capsule`
**Config Directory:** `~/.capsule/`
**Development Mode:** Changes to source code are immediately available
