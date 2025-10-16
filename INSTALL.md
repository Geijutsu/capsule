# 🔮 Capsule Installation Guide

## Quick Install (Recommended)

```bash
cd /Users/joshkornreich/Documents/Projects/CLIs/capsule
./install.sh
```

This installs capsule globally in development mode, so any changes to the code are immediately available.

## Manual Installation

### Method 1: pip install (Development Mode)
```bash
cd /Users/joshkornreich/Documents/Projects/CLIs/capsule
pip3 install --user -e .
```

### Method 2: setup.py develop
```bash
cd /Users/joshkornreich/Documents/Projects/CLIs/capsule
python3 setup.py develop --user
```

### Method 3: Direct binary
```bash
cd /Users/joshkornreich/Documents/Projects/CLIs/capsule
ln -sf $(pwd)/capsule ~/.local/bin/capsule
```

## Verify Installation

```bash
which capsule
capsule --version
capsule --help
```

## Add to PATH (if needed)

If `capsule` command is not found, add to your shell config:

**For zsh (~/.zshrc):**
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

**For bash (~/.bashrc):**
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

## Update Installation

Since it's installed in development mode (`-e`), changes to the code are automatically available:

```bash
cd /Users/joshkornreich/Documents/Projects/CLIs/capsule
git pull  # if using git
# Changes are immediately available
capsule --version
```

## Uninstall

```bash
pip3 uninstall capsule
```

## Persistent Installation

The installation is persistent across terminal sessions. Once installed, you can run `capsule` from anywhere.

## Global Binary Pattern

Following the pattern from ~/.claude/CLAUDE.md, after building CLI tools:

```bash
cd /Users/joshkornreich/Documents/Projects/CLIs/capsule
./install.sh  # Automatically installs to ~/.local/bin
```

This ensures capsule is always available as a global command.
