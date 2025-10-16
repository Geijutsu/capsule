# Capsule Provider System - Quick Start Guide

## Installation

```bash
cd /Users/joshkornreich/Documents/Projects/CLIs/seed/capsule
cargo install --path .
```

## Basic Commands

### List All Providers

```bash
capsule openmesh providers
```

Shows all 7 providers with template counts, regions, pricing, and GPU availability.

### List Templates

```bash
# All templates
capsule openmesh templates

# GPU templates only
capsule openmesh templates --gpu
```

### Configure Provider

```bash
capsule openmesh provider configure hivelocity --api-key YOUR_API_KEY
capsule openmesh provider configure digitalocean --api-key YOUR_API_KEY
```

Credentials stored in `~/.capsule/providers.yml`

### Smart Deployment

```bash
# Auto-select cheapest option with constraints
capsule openmesh deploy --min-cpu 4 --min-memory 8 --budget 0.10

# Deploy to specific provider
capsule openmesh deploy \
  --provider hivelocity \
  --template hive-large \
  --name my-xnode \
  --region atlanta
```

## Provider Summary

| Provider | Templates | Price Range | GPU | Best For |
|----------|-----------|-------------|-----|----------|
| **Scaleway** | 6 | $0.004-$3.30/hr | ✓ H100 | Budget + GPU options |
| **Vultr** | 4 | $0.004-$0.34/hr | - | Low cost cloud |
| **DigitalOcean** | 4 | $0.007-$0.24/hr | - | Reliable cloud |
| **Linode** | 6 | $0.007-$1.50/hr | ✓ RTX6000 | Cloud + GPU |
| **AWS** | 4 | $0.010-$0.34/hr | - | Enterprise cloud |
| **Hivelocity** | 4 | $0.12-$0.80/hr | ✓ RTX4090 | Bare metal + GPU |
| **Equinix** | 3 | $0.50-$3.00/hr | ✓ V100 | Premium bare metal |

## GPU Templates

| Provider | Template | GPU | Price | Use Case |
|----------|----------|-----|-------|----------|
| Scaleway | RENDER-S | NVIDIA T4 | $0.44/hr | Budget GPU |
| Hivelocity | GPU Bare Metal | RTX 4090 | $0.80/hr | Gaming/ML |
| Linode | GPU RTX6000 | RTX 6000 | $1.50/hr | Professional GPU |
| Equinix | g2.large.x86 | Tesla V100 | $3.00/hr | Enterprise GPU |
| Scaleway | H100-1-80G | H100 80GB | $3.30/hr | LLM Training |

## Example Workflows

### Find Cheapest 4CPU/8GB Option

```bash
capsule openmesh deploy --min-cpu 4 --min-memory 8
```

### Deploy GPU Instance Under $1/hr

```bash
capsule openmesh templates --gpu
capsule openmesh deploy --provider hivelocity --template hive-gpu --name gpu-node
```

### Compare All Cloud Options

```bash
capsule openmesh templates | grep cloud
```

## File Structure

```
src/
├── providers/
│   ├── mod.rs           # Provider trait & manager
│   ├── hivelocity.rs    # Bare metal provider
│   ├── digitalocean.rs  # Cloud provider
│   ├── vultr.rs         # Cloud + bare metal
│   ├── aws.rs           # AWS EC2
│   ├── equinix.rs       # Premium bare metal
│   ├── linode.rs        # Cloud + dedicated
│   └── scaleway.rs      # Cloud + GPU + ARM
├── openmesh.rs          # CLI commands
└── main.rs              # CLI integration
```

## Configuration

Providers configured in `~/.capsule/providers.yml`:

```yaml
hivelocity:
  api_key: your_key_here
digitalocean:
  api_key: your_key_here
vultr:
  api_key: your_key_here
```

## Next Steps

1. Configure your preferred providers
2. Test deployment commands
3. Implement actual API client calls (currently stubbed)
4. Add instance lifecycle management
5. Integrate with xNode deployment scripts

## Help

```bash
capsule openmesh --help
capsule openmesh providers --help
capsule openmesh templates --help
capsule openmesh deploy --help
```
