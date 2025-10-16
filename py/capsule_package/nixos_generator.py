#!/usr/bin/env python3
"""NixOS Configuration Generator for Capsule

This module generates comprehensive NixOS configurations including:
- configuration.nix (system-wide configuration)
- home-manager (user environment)
- flake.nix (modern Nix flakes)
- hardware-configuration.nix (hardware detection)
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime
import yaml

class NixOSConfigGenerator:
    """Generate comprehensive NixOS configurations from Capsule profiles"""

    def __init__(self, capsule_dir: Path = None):
        """Initialize the generator

        Args:
            capsule_dir: Base directory for Capsule config (default: ~/.capsule)
        """
        self.capsule_dir = capsule_dir or Path.home() / ".capsule"
        self.presets_dir = Path(__file__).parent / "presets"

    def _load_preset(self, name: str) -> Optional[Dict]:
        """Load a preset configuration file"""
        preset_file = self.presets_dir / f"{name}.yml"
        if not preset_file.exists():
            return None
        with open(preset_file) as f:
            return yaml.safe_load(f)

    def _resolve_dependencies(self, preset_name: str, resolved: List[str] = None,
                             visiting: Set[str] = None) -> List[str]:
        """Recursively resolve preset dependencies"""
        if resolved is None:
            resolved = []
        if visiting is None:
            visiting = set()

        if preset_name in visiting or preset_name in resolved:
            return resolved

        visiting.add(preset_name)

        preset = self._load_preset(preset_name)
        if not preset:
            visiting.remove(preset_name)
            return resolved

        # Resolve dependencies first
        for dep in preset.get("dependencies", []):
            self._resolve_dependencies(dep, resolved, visiting)

        if preset_name not in resolved:
            resolved.append(preset_name)

        visiting.remove(preset_name)
        return resolved

    def _collect_packages(self, config: Dict) -> Tuple[List[str], Dict[str, List[str]]]:
        """Collect all packages from presets and custom packages

        Returns:
            Tuple of (all_packages, packages_by_preset)
        """
        all_packages = []
        packages_by_preset = {}

        # Add base packages
        base_packages = ["git", "curl", "wget", "vim", "htop", "unzip"]
        packages_by_preset["base"] = base_packages
        all_packages.extend(base_packages)

        # Resolve and collect preset packages
        for preset_name in config.get("presets", []):
            if preset_name == "base":
                continue
            resolved = self._resolve_dependencies(preset_name)

            for stack in resolved:
                if stack in packages_by_preset:
                    continue
                preset = self._load_preset(stack)
                if preset and "packages" in preset:
                    packages_by_preset[stack] = preset["packages"]
                    all_packages.extend(preset["packages"])

        # Add custom packages
        custom_packages = config.get("custom_packages", [])
        if custom_packages:
            packages_by_preset["custom"] = custom_packages
            all_packages.extend(custom_packages)

        # Remove duplicates while preserving order
        seen = set()
        unique_packages = []
        for pkg in all_packages:
            if pkg not in seen:
                seen.add(pkg)
                unique_packages.append(pkg)

        return unique_packages, packages_by_preset

    def _detect_services(self, config: Dict) -> Dict[str, Dict]:
        """Detect and map services from presets

        Returns:
            Dict mapping service names to their configuration
        """
        services = {}
        presets = config.get("presets", [])

        # Service mapping
        service_map = {
            "docker": {
                "virtualisation.docker.enable": True,
                "virtualisation.docker.enableOnBoot": True,
            },
            "webserver": {
                "services.nginx.enable": True,
                "networking.firewall.allowedTCPPorts": [80, 443],
            },
            "database": {
                "services.postgresql.enable": True,
                "services.postgresql.enableTCPIP": True,
            },
            "monitoring": {
                "services.prometheus.enable": True,
                "services.grafana.enable": True,
            },
            "ollama": {
                "# Ollama service (manual setup required)": True,
            },
        }

        for preset_name in presets:
            if preset_name in service_map:
                services.update(service_map[preset_name])

        return services

    def generate_configuration_nix(self, profile: Dict, hostname: str = "nixos",
                                   username: str = "user") -> str:
        """Generate a comprehensive configuration.nix file

        Args:
            profile: Capsule profile configuration
            hostname: System hostname
            username: Primary user account name

        Returns:
            Complete NixOS configuration.nix content
        """
        packages, packages_by_preset = self._collect_packages(profile)
        services = self._detect_services(profile)

        # Header
        config_lines = [
            "# NixOS Configuration",
            f"# Generated by Capsule on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"# Profile: {profile.get('description', 'Custom configuration')}",
            "",
            "{ config, pkgs, ... }:",
            "",
            "{",
            "  imports = [",
            "    ./hardware-configuration.nix",
            "  ];",
            "",
        ]

        # Boot loader
        config_lines.extend([
            "  # Boot loader",
            "  boot.loader.systemd-boot.enable = true;",
            "  boot.loader.efi.canTouchEfiVariables = true;",
            "",
        ])

        # Network configuration
        config_lines.extend([
            "  # Network configuration",
            f"  networking.hostName = \"{hostname}\";",
            "  networking.networkmanager.enable = true;",
            "",
        ])

        # Time zone and locale
        config_lines.extend([
            "  # Localization",
            "  time.timeZone = \"America/New_York\";",
            "  i18n.defaultLocale = \"en_US.UTF-8\";",
            "",
        ])

        # User accounts
        config_lines.extend([
            "  # User accounts",
            "  users.users." + username + " = {",
            "    isNormalUser = true;",
            "    description = \"Primary User\";",
            "    extraGroups = [ \"wheel\" \"networkmanager\" \"docker\" ];",
            "    openssh.authorizedKeys.keys = [",
            "      # Add your SSH public keys here",
            "    ];",
            "  };",
            "",
        ])

        # Services configuration
        if services:
            config_lines.extend([
                "  # Services",
            ])
            for service_key, service_value in services.items():
                if service_key.startswith("#"):
                    config_lines.append(f"  {service_key}")
                elif isinstance(service_value, bool):
                    config_lines.append(f"  {service_key} = {str(service_value).lower()};")
                elif isinstance(service_value, list):
                    config_lines.append(f"  {service_key} = [ {' '.join(str(v) for v in service_value)} ];")
            config_lines.append("")

        # SSH configuration
        config_lines.extend([
            "  # SSH",
            "  services.openssh = {",
            "    enable = true;",
            "    settings = {",
            "      PermitRootLogin = \"no\";",
            "      PasswordAuthentication = false;",
            "    };",
            "  };",
            "",
        ])

        # Firewall
        config_lines.extend([
            "  # Firewall",
            "  networking.firewall = {",
            "    enable = true;",
            "    allowedTCPPorts = [ 22 ];",
            "    # allowedUDPPorts = [ ... ];",
            "  };",
            "",
        ])

        # System packages
        config_lines.extend([
            "  # System packages",
            "  environment.systemPackages = with pkgs; [",
        ])

        # Add packages grouped by preset
        for preset_name, preset_packages in packages_by_preset.items():
            if preset_packages:
                preset_obj = self._load_preset(preset_name)
                description = preset_obj.get("description", preset_name) if preset_obj else preset_name
                config_lines.append(f"    # {description}")
                for pkg in preset_packages:
                    config_lines.append(f"    {pkg}")
                config_lines.append("")

        config_lines.extend([
            "  ];",
            "",
        ])

        # Nix settings
        config_lines.extend([
            "  # Nix settings",
            "  nix.settings = {",
            "    experimental-features = [ \"nix-command\" \"flakes\" ];",
            "    auto-optimise-store = true;",
            "  };",
            "",
            "  # Automatic garbage collection",
            "  nix.gc = {",
            "    automatic = true;",
            "    dates = \"weekly\";",
            "    options = \"--delete-older-than 30d\";",
            "  };",
            "",
        ])

        # System version
        config_lines.extend([
            "  # System version",
            "  system.stateVersion = \"24.05\"; # Don't change this!",
            "}",
        ])

        return "\n".join(config_lines)

    def generate_home_manager(self, profile: Dict, username: str = "user") -> str:
        """Generate home-manager configuration

        Args:
            profile: Capsule profile configuration
            username: User account name

        Returns:
            Complete home-manager home.nix content
        """
        packages, packages_by_preset = self._collect_packages(profile)

        config_lines = [
            "# Home Manager Configuration",
            f"# Generated by Capsule on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"# Profile: {profile.get('description', 'Custom configuration')}",
            "",
            "{ config, pkgs, ... }:",
            "",
            "{",
            f"  home.username = \"{username}\";",
            "  home.homeDirectory = \"/home/" + username + "\";",
            "",
            "  # Home Manager version (match your NixOS version)",
            "  home.stateVersion = \"24.05\";",
            "",
            "  # Let Home Manager install and manage itself",
            "  programs.home-manager.enable = true;",
            "",
        ]

        # User packages
        config_lines.extend([
            "  # User packages",
            "  home.packages = with pkgs; [",
        ])

        for preset_name, preset_packages in packages_by_preset.items():
            if preset_packages:
                preset_obj = self._load_preset(preset_name)
                description = preset_obj.get("description", preset_name) if preset_obj else preset_name
                config_lines.append(f"    # {description}")
                for pkg in preset_packages:
                    config_lines.append(f"    {pkg}")
                config_lines.append("")

        config_lines.extend([
            "  ];",
            "",
        ])

        # Shell configuration
        editor = profile.get("editor", "vim")
        config_lines.extend([
            "  # Shell configuration",
            "  programs.bash = {",
            "    enable = true;",
            "    shellAliases = {",
            "      ll = \"ls -la\";",
            "      gs = \"git status\";",
            "      gd = \"git diff\";",
            "    };",
            "  };",
            "",
            "  # Editor",
            f"  home.sessionVariables = {{",
            f"    EDITOR = \"{editor}\";",
            "  };",
            "",
        ])

        # Git configuration
        if "github" in profile.get("presets", []):
            config_lines.extend([
                "  # Git configuration",
                "  programs.git = {",
                "    enable = true;",
                "    userName = \"Your Name\";",
                "    userEmail = \"your.email@example.com\";",
                "    extraConfig = {",
                "      init.defaultBranch = \"main\";",
                "      pull.rebase = false;",
                "    };",
                "  };",
                "",
            ])

        # Direnv for development environments
        if "devtools" in profile.get("presets", []) or "python" in profile.get("presets", []):
            config_lines.extend([
                "  # Development tools",
                "  programs.direnv = {",
                "    enable = true;",
                "    nix-direnv.enable = true;",
                "  };",
                "",
            ])

        config_lines.append("}")

        return "\n".join(config_lines)

    def generate_flake_nix(self, profile: Dict, hostname: str = "nixos",
                          username: str = "user") -> str:
        """Generate a flake.nix for modern NixOS configuration

        Args:
            profile: Capsule profile configuration
            hostname: System hostname
            username: User account name

        Returns:
            Complete flake.nix content
        """
        config_lines = [
            "{",
            "  description = \"NixOS configuration with Capsule-generated setup\";",
            "",
            "  inputs = {",
            "    nixpkgs.url = \"github:NixOS/nixpkgs/nixos-24.05\";",
            "    home-manager = {",
            "      url = \"github:nix-community/home-manager/release-24.05\";",
            "      inputs.nixpkgs.follows = \"nixpkgs\";",
            "    };",
            "  };",
            "",
            "  outputs = { self, nixpkgs, home-manager, ... }@inputs: {",
            f"    nixosConfigurations.{hostname} = nixpkgs.lib.nixosSystem {{",
            "      system = \"x86_64-linux\";",
            "      modules = [",
            "        ./configuration.nix",
            "        home-manager.nixosModules.home-manager",
            "        {",
            "          home-manager.useGlobalPkgs = true;",
            "          home-manager.useUserPackages = true;",
            f"          home-manager.users.{username} = import ./home.nix;",
            "        }",
            "      ];",
            "    };",
            "  };",
            "}",
        ]

        return "\n".join(config_lines)

    def generate_hardware_config(self) -> str:
        """Generate hardware-configuration.nix by scanning the system

        Returns:
            Hardware configuration content (or template if scan fails)
        """
        try:
            # Try to run nixos-generate-config to detect hardware
            result = subprocess.run(
                ["nixos-generate-config", "--show-hardware-config"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0 and result.stdout:
                return result.stdout
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Return template if hardware detection fails
        return """# Hardware Configuration
# This is a template - run 'nixos-generate-config' on the target system

{ config, lib, pkgs, modulesPath, ... }:

{
  imports = [
    (modulesPath + "/profiles/qemu-guest.nix")
  ];

  boot.initrd.availableKernelModules = [ "ata_piix" "uhci_hcd" "virtio_pci" "sd_mod" "sr_mod" ];
  boot.initrd.kernelModules = [ ];
  boot.kernelModules = [ ];
  boot.extraModulePackages = [ ];

  fileSystems."/" = {
    device = "/dev/disk/by-label/nixos";
    fsType = "ext4";
  };

  fileSystems."/boot" = {
    device = "/dev/disk/by-label/boot";
    fsType = "vfat";
  };

  swapDevices = [ ];

  networking.useDHCP = lib.mkDefault true;
  nixpkgs.hostPlatform = lib.mkDefault "x86_64-linux";
}
"""

    def generate_all(self, profile: Dict, output_dir: Path, hostname: str = "nixos",
                     username: str = "user") -> Dict[str, Path]:
        """Generate all NixOS configuration files

        Args:
            profile: Capsule profile configuration
            output_dir: Directory to write configuration files
            hostname: System hostname
            username: User account name

        Returns:
            Dict mapping file types to their paths
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        generated_files = {}

        # Generate configuration.nix
        config_nix = self.generate_configuration_nix(profile, hostname, username)
        config_path = output_dir / "configuration.nix"
        config_path.write_text(config_nix)
        generated_files["configuration.nix"] = config_path

        # Generate home.nix
        home_nix = self.generate_home_manager(profile, username)
        home_path = output_dir / "home.nix"
        home_path.write_text(home_nix)
        generated_files["home.nix"] = home_path

        # Generate flake.nix
        flake_nix = self.generate_flake_nix(profile, hostname, username)
        flake_path = output_dir / "flake.nix"
        flake_path.write_text(flake_nix)
        generated_files["flake.nix"] = flake_path

        # Generate hardware-configuration.nix
        hardware_nix = self.generate_hardware_config()
        hardware_path = output_dir / "hardware-configuration.nix"
        hardware_path.write_text(hardware_nix)
        generated_files["hardware-configuration.nix"] = hardware_path

        # Create a README
        readme_content = f"""# NixOS Configuration

Generated by Capsule on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Files

- **configuration.nix**: System-wide configuration
- **home.nix**: Home Manager user configuration
- **flake.nix**: Nix flakes configuration (modern approach)
- **hardware-configuration.nix**: Hardware-specific configuration

## Usage

### Traditional NixOS (configuration.nix)

1. Copy configuration.nix and hardware-configuration.nix to /etc/nixos/
2. Review and customize the configuration
3. Run: `sudo nixos-rebuild switch`

### With Flakes (recommended)

1. Copy all files to /etc/nixos/
2. Run: `sudo nixos-rebuild switch --flake /etc/nixos#{hostname}`

### With Home Manager

1. Install Home Manager: https://github.com/nix-community/home-manager
2. Copy home.nix to ~/.config/home-manager/
3. Run: `home-manager switch`

## Customization

- Update hostname in configuration.nix
- Add SSH keys in users.users.{username}.openssh.authorizedKeys.keys
- Adjust timezone in time.timeZone
- Modify firewall rules in networking.firewall
- Add additional packages to environment.systemPackages

## Testing

Test in a VM before deploying:
```bash
sudo nixos-rebuild build-vm
./result/bin/run-nixos-vm
```
"""
        readme_path = output_dir / "README.md"
        readme_path.write_text(readme_content)
        generated_files["README.md"] = readme_path

        return generated_files


def validate_config(config_path: Path) -> Tuple[bool, List[str]]:
    """Validate a NixOS configuration file

    Args:
        config_path: Path to configuration.nix

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    if not config_path.exists():
        return False, [f"Configuration file not found: {config_path}"]

    try:
        # Check syntax with nix-instantiate
        result = subprocess.run(
            ["nix-instantiate", "--parse", str(config_path)],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            errors.append(f"Syntax error: {result.stderr}")
            return False, errors

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        errors.append(f"Validation failed: {str(e)}")
        return False, errors
    except subprocess.TimeoutExpired:
        errors.append("Validation timed out")
        return False, errors

    return True, []


def test_in_vm(config_dir: Path) -> bool:
    """Test NixOS configuration in a VM

    Args:
        config_dir: Directory containing configuration.nix

    Returns:
        True if VM build succeeded
    """
    config_path = config_dir / "configuration.nix"

    if not config_path.exists():
        return False

    try:
        # Build VM configuration
        result = subprocess.run(
            ["nixos-rebuild", "build-vm", "-I", f"nixos-config={config_path}"],
            capture_output=True,
            text=True,
            cwd=config_dir
        )

        return result.returncode == 0

    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


if __name__ == "__main__":
    # Demo usage
    generator = NixOSConfigGenerator()

    # Example profile
    demo_profile = {
        "description": "Full-stack development environment",
        "presets": ["base", "python", "nodejs", "docker", "github"],
        "custom_packages": ["tmux", "htop", "jq"],
        "editor": "vim"
    }

    print("Generating NixOS configuration...")
    output_dir = Path("/tmp/capsule-nixos-demo")
    files = generator.generate_all(demo_profile, output_dir, hostname="devbox", username="developer")

    print(f"\nGenerated files in {output_dir}:")
    for file_type, file_path in files.items():
        print(f"  - {file_type}: {file_path}")

    print("\nConfiguration preview (configuration.nix):")
    print("-" * 60)
    config_content = files["configuration.nix"].read_text()
    print(config_content[:1000] + "...\n")
