# NixOS Generator Quick Start Guide

## Overview

Transform your Capsule profiles into production-ready NixOS configurations in seconds.

## Basic Usage

### 1. Generate Configuration

```bash
# Use default settings
capsule nixos generate

# Custom hostname and username
capsule nixos generate --hostname myserver --username admin

# Specify output directory
capsule nixos generate --output /path/to/config
```

**Output**: Complete NixOS configuration in `~/.capsule/nixos/`

### 2. Review Configuration

```bash
cd ~/.capsule/nixos
cat configuration.nix    # System configuration
cat home.nix            # User environment
cat flake.nix           # Flakes configuration
```

### 3. Validate

```bash
capsule nixos validate
```

### 4. Test (Optional but Recommended)

```bash
capsule nixos test
```

This builds a VM. Run it with:
```bash
./result/bin/run-nixos-vm
```

### 5. Deploy

```bash
# Local deployment
capsule nixos apply

# Remote deployment
capsule nixos apply --target user@server.com

# Dry run first
capsule nixos apply --dry-run
```

## Common Workflows

### Development Environment

```bash
capsule profile use dev
capsule nixos generate --hostname devbox
capsule nixos validate
capsule nixos apply
```

**Result**: System with Python, Node.js, Docker, Git, and CLI tools

### Production Web Server

```bash
capsule profile use prod
capsule nixos generate --hostname webserver
capsule nixos validate
capsule nixos test
capsule nixos apply --target root@production.com
```

**Result**: Hardened server with Nginx, security tools, and monitoring

### Machine Learning Workstation

```bash
capsule profile use ml-gpu
capsule nixos generate --hostname mlbox --username researcher
capsule nixos validate
capsule nixos apply
```

**Result**: System with Python, PyTorch, TensorFlow, CUDA, and Ollama

## Profile-Specific Configurations

### Minimal Setup
```bash
capsule profile use minimal
capsule nixos generate
```
Includes: Base tools, tmux, htop

### Web Development
```bash
capsule profile use web
capsule nixos generate
```
Includes: Node.js, Docker, Git, tmux

### Full-Stack Development
```bash
capsule profile use dev
capsule nixos generate
```
Includes: Python, Node.js, Docker, GitHub CLI, modern CLI tools

## Advanced Usage

### Generate Specific Files

```bash
# Home Manager only
capsule nixos generate --home-manager

# Flake only
capsule nixos generate --flake

# Hardware config only
capsule nixos generate --hardware

# Everything (default)
capsule nixos generate --all
```

### Custom Configuration

1. Create custom profile:
```bash
capsule profile create myprofile
capsule add python nodejs docker
capsule add custom packages: neovim ripgrep fd
```

2. Generate configuration:
```bash
capsule nixos generate --hostname custom
```

### Remote Deployment

```bash
# Deploy to remote server
capsule nixos apply --target admin@192.168.1.100

# Custom SSH port
capsule nixos apply --target admin@server --port 2222

# Preview changes
capsule nixos apply --target admin@server --dry-run
```

## Rollback

If something goes wrong:

```bash
# Rollback to previous generation
capsule nixos rollback

# Rollback to specific generation
capsule nixos list-generations
capsule nixos rollback --generation 42
```

## Configuration Files

Generated files in `~/.capsule/nixos/`:

- **configuration.nix** - System-wide configuration (packages, services, users)
- **home.nix** - User environment (shell, editor, development tools)
- **flake.nix** - Modern Nix flakes configuration
- **hardware-configuration.nix** - Hardware-specific settings
- **README.md** - Deployment instructions

## Customization

After generation, you can customize:

### Add SSH Keys
Edit `configuration.nix`:
```nix
users.users.youruser = {
  openssh.authorizedKeys.keys = [
    "ssh-rsa AAAAB3... your-key"
  ];
};
```

### Change Timezone
```nix
time.timeZone = "Europe/London";
```

### Add Firewall Ports
```nix
networking.firewall.allowedTCPPorts = [ 22 80 443 8080 ];
```

### Add More Packages
```nix
environment.systemPackages = with pkgs; [
  # existing packages...
  neovim
  terraform
  kubectl
];
```

## Services

Capsule automatically configures services based on your profile:

| Profile/Preset | Enabled Services |
|----------------|------------------|
| docker | Docker daemon |
| webserver | Nginx, firewall ports 80/443 |
| database | PostgreSQL |
| monitoring | Prometheus, Grafana |

## Troubleshooting

### Validation Fails

```bash
# Check syntax
capsule nixos validate

# Review error messages
cat ~/.capsule/nixos/configuration.nix
```

### VM Build Fails

Ensure you're on NixOS or have Nix installed:
```bash
nix --version
```

### Deployment Fails

Check SSH access:
```bash
ssh user@server
```

### Package Not Found

Check package name in [NixOS packages](https://search.nixos.org/packages)

## Tips

1. **Always test in VM first** for new configurations
2. **Use --dry-run** before remote deployment
3. **Review generated files** before applying
4. **Keep backups** of working configurations
5. **Use flakes** for reproducible builds
6. **Customize hardware-configuration.nix** for specific hardware

## Examples

### Example 1: Quick Dev Environment

```bash
capsule profile use dev
capsule nixos generate
capsule nixos validate
capsule nixos apply
```

Time: < 5 minutes to full development environment

### Example 2: Remote Server Setup

```bash
# Generate configuration locally
capsule profile use prod
capsule nixos generate --hostname production

# Test locally
capsule nixos validate

# Deploy to remote
capsule nixos apply --target root@server.com --dry-run
capsule nixos apply --target root@server.com
```

### Example 3: Multi-User Development Machine

```bash
# Generate with custom settings
capsule profile use dev
capsule nixos generate \
  --hostname devserver \
  --username developer

# Customize user accounts in configuration.nix
# Add more users, SSH keys, etc.

# Apply
capsule nixos apply
```

## Next Steps

1. Explore built-in profiles: `capsule profiles`
2. View available presets: `capsule stacks`
3. Create custom profiles: `capsule profile create`
4. Read generated README: `cat ~/.capsule/nixos/README.md`

## Help

```bash
# Main help
capsule nixos --help

# Command-specific help
capsule nixos generate --help
capsule nixos apply --help
capsule nixos validate --help
capsule nixos test --help
```

## Links

- [NixOS Manual](https://nixos.org/manual/nixos/stable/)
- [Nix Pills](https://nixos.org/guides/nix-pills/)
- [Home Manager Manual](https://nix-community.github.io/home-manager/)
- [NixOS Package Search](https://search.nixos.org/)

---

**Happy NixOS configuration! 🚀**
