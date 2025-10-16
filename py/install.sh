#!/bin/bash
# Capsule Global Installation Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.local/bin"
PYTHON_BIN="$HOME/Library/Python/3.11/bin"

echo "🔮 Installing Capsule..."

# Install with pip
pip3 install --user -e "$SCRIPT_DIR"

# Ensure .local/bin exists
mkdir -p "$INSTALL_DIR"

# Create symlink if binary is in Python bin directory
if [ -f "$PYTHON_BIN/capsule" ]; then
    ln -sf "$PYTHON_BIN/capsule" "$INSTALL_DIR/capsule"
    echo "✓ Created symlink: $INSTALL_DIR/capsule"
fi

# Check if it's in PATH
if command -v capsule &> /dev/null; then
    echo ""
    echo "✓ Capsule installed successfully!"
    capsule --version
    echo ""
    echo "Try: capsule --help"
else
    echo ""
    echo "⚠ Capsule installed but not in PATH"
    echo ""
    echo "Add this to your ~/.zshrc:"
    echo '  export PATH="$HOME/.local/bin:$PATH"'
    echo ""
    echo "Then run: source ~/.zshrc"
fi
