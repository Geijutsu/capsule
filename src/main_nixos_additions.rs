// This file contains the additions needed for main.rs for Nix/NixOS support

use capsule::nix::*;
use capsule::nixos::*;
use std::path::PathBuf;

// Add these variants to Commands enum:
/*
    /// Install packages using Nix
    Setup {
        /// Dry run mode (check what would be installed)
        #[arg(long)]
        check: bool,
        /// Verbose output level
        #[arg(short, long, action = clap::ArgAction::Count)]
        verbose: u8,
    },

    /// Dry run - check what would be changed
    Check {
        /// Verbose output level
        #[arg(short, long, action = clap::ArgAction::Count)]
        verbose: u8,
    },

    /// Preview generated Nix configuration
    Preview,

    /// NixOS configuration generation and management
    Nixos {
        #[command(subcommand)]
        command: NixOSCommands,
    },
*/

// Add this new enum:
#[derive(Subcommand)]
enum NixOSCommands {
    /// Generate NixOS configuration files from profile
    Generate {
        /// Output directory (default: ~/.capsule/nixos)
        #[arg(short, long)]
        output: Option<PathBuf>,
        /// System hostname
        #[arg(long, default_value = "nixos")]
        hostname: String,
        /// Primary user account name
        #[arg(long)]
        username: Option<String>,
        /// Generate home-manager configuration only
        #[arg(long)]
        home_manager: bool,
        /// Generate flake.nix only
        #[arg(long)]
        flake: bool,
        /// Generate hardware-configuration.nix only
        #[arg(long)]
        hardware: bool,
        /// Generate all configuration files
        #[arg(long)]
        all: bool,
    },

    /// Validate NixOS configuration syntax
    Validate {
        /// Path to configuration.nix
        #[arg(short, long)]
        config: Option<PathBuf>,
    },

    /// Test NixOS configuration in a VM
    Test {
        /// Configuration directory
        #[arg(short, long)]
        config_dir: Option<PathBuf>,
    },

    /// Apply NixOS configuration to system
    Apply {
        /// Configuration directory
        #[arg(short, long)]
        config_dir: Option<PathBuf>,
        /// Use flake configuration
        #[arg(long)]
        flake: bool,
    },

    /// Rollback to previous NixOS generation
    Rollback,

    /// List NixOS generations
    ListGenerations,
}

// Add these match arms to the main match statement:
/*
        Some(Commands::Setup { check, verbose }) => cmd_setup(check, verbose)?,
        Some(Commands::Check { verbose }) => cmd_check(verbose)?,
        Some(Commands::Preview) => cmd_preview()?,
        Some(Commands::Nixos { command }) => handle_nixos_command(command)?,
*/

// Handler functions:

fn cmd_setup(check: bool, verbose: u8) -> Result<()> {
    if check {
        banner("🔍 DRY RUN MODE");
        println!("  Checking what would be installed...\n");
    } else {
        banner("🚀 SETTING UP SERVER");
    }

    if verbose > 0 {
        println!("  Verbose level: {}\n", verbose);
    }

    let config = load_config(None)?;
    
    // Check if Nix is installed
    if !check_nix_installed() {
        error("nix-env not found. Please install Nix: https://nixos.org/download.html");
        return Ok(());
    }

    run_nix_env(&config, check, verbose)?;
    Ok(())
}

fn cmd_check(verbose: u8) -> Result<()> {
    banner("🔍 CONFIGURATION CHECK");
    if verbose > 0 {
        println!("  Verbose level: {}\n", verbose);
    }

    let config = load_config(None)?;
    
    if !check_nix_installed() {
        error("nix-env not found. Please install Nix: https://nixos.org/download.html");
        return Ok(());
    }

    run_nix_env(&config, true, verbose)?;
    Ok(())
}

fn cmd_preview() -> Result<()> {
    let config = load_config(None)?;
    
    header("📋 NIX CONFIGURATION PREVIEW");

    let (packages, _) = collect_packages(&config)?;
    
    section_header("Summary");
    info_line("Stacks", &config.presets.len().to_string());
    info_line("Total Packages", &packages.len().to_string());

    section_header("Generated Nix Configuration");
    let nix_config = generate_nix_config(&config)?;
    println!("{}", nix_config.bright_black());

    divider();
    println!();
    println!("  {} Run {} to preview installation without applying",
             "💡 Tip:".cyan(),
             "capsule check".cyan().bold());
    println!();

    Ok(())
}

fn handle_nixos_command(command: NixOSCommands) -> Result<()> {
    match command {
        NixOSCommands::Generate {
            output,
            hostname,
            username,
            home_manager,
            flake,
            hardware,
            all,
        } => {
            let config = load_config(None)?;
            
            let output_dir = output.unwrap_or_else(|| {
                dirs::home_dir()
                    .expect("Could not find home directory")
                    .join(".capsule/nixos")
            });

            let username = username.unwrap_or_else(|| {
                std::env::var("USER").unwrap_or_else(|_| "user".to_string())
            });

            let generator = NixOSConfigGenerator::new(None);
            
            header("🔧 NIXOS CONFIGURATION GENERATOR");

            let generate_all = !home_manager && !flake && !hardware || all;

            if generate_all {
                section_header("Generating complete NixOS configuration");
                info_line("Profile", config.description.as_ref().unwrap_or(&"Custom configuration".to_string()));
                info_line("Hostname", &hostname);
                info_line("Username", &username);
                info_line("Output", &output_dir.display().to_string());
                println!();

                let files = generator.generate_all(&config, &output_dir, &hostname, &username)?;

                for (file_type, file_path) in files {
                    success(&format!("Generated {}", file_type));
                    println!("    {}", file_path.display().to_string().bright_black());
                }
            } else {
                // Generate specific files
                std::fs::create_dir_all(&output_dir)?;

                if home_manager {
                    section_header("Generating Home Manager configuration");
                    let home_nix = generator.generate_home_manager(&config, &username)?;
                    let home_path = output_dir.join("home.nix");
                    std::fs::write(&home_path, home_nix)?;
                    success("Generated home.nix");
                    println!("    {}", home_path.display().to_string().bright_black());
                }

                if flake {
                    section_header("Generating Flake configuration");
                    let flake_nix = generator.generate_flake_nix(&config, &hostname, &username)?;
                    let flake_path = output_dir.join("flake.nix");
                    std::fs::write(&flake_path, flake_nix)?;
                    success("Generated flake.nix");
                    println!("    {}", flake_path.display().to_string().bright_black());
                }

                if hardware {
                    section_header("Generating Hardware configuration");
                    let hardware_nix = generator.generate_hardware_config()?;
                    let hardware_path = output_dir.join("hardware-configuration.nix");
                    std::fs::write(&hardware_path, hardware_nix)?;
                    success("Generated hardware-configuration.nix");
                    println!("    {}", hardware_path.display().to_string().bright_black());
                }
            }

            println!();
            success("NixOS configuration generated successfully!");

            divider();
            println!();
            println!("  {} Next Steps:", "📋".cyan());
            println!();
            println!("  1. Review the generated configuration files");
            println!("     {}", format!("cd {}", output_dir.display()).cyan());
            println!();
            println!("  2. Test configuration (recommended)");
            println!("     {}", "capsule nixos test".cyan());
            println!();
            println!("  3. Deploy to NixOS system");
            println!("     {}", format!("sudo cp {}/*.nix /etc/nixos/", output_dir.display()).cyan());
            println!("     {}", "sudo nixos-rebuild switch".cyan());
            println!();

            Ok(())
        }

        NixOSCommands::Validate { config: config_path } => {
            let config_path = config_path.unwrap_or_else(|| {
                dirs::home_dir()
                    .expect("Could not find home directory")
                    .join(".capsule/nixos/configuration.nix")
            });

            header("✓ NIXOS CONFIGURATION VALIDATION");
            info_line("Validating", &config_path.display().to_string());
            println!();

            if !config_path.exists() {
                error(&format!("Configuration file not found: {}", config_path.display()));
                return Ok(());
            }

            let (is_valid, errors) = validate_config(&config_path)?;

            if is_valid {
                success("Configuration is valid!");
                println!();
                println!("  {} Test in VM with {}", "💡 Next:".cyan(), "capsule nixos test".cyan().bold());
                println!();
            } else {
                error("Configuration validation failed!");
                println!();
                section_header("Errors");
                for err in errors {
                    println!("  {} {}", "✗".red(), err);
                }
                println!();
            }

            Ok(())
        }

        NixOSCommands::Test { config_dir } => {
            let config_dir = config_dir.unwrap_or_else(|| {
                dirs::home_dir()
                    .expect("Could not find home directory")
                    .join(".capsule/nixos")
            });

            header("🖥️  NIXOS VM TEST");
            info_line("Configuration", &config_dir.display().to_string());
            println!();

            section_header("Building VM...");
            let success_build = test_in_vm(&config_dir)?;

            if success_build {
                success("VM built successfully!");
                println!();
                println!("  {} Run the VM:", "💡".cyan());
                println!("     {}", "./result/bin/run-nixos-vm".cyan());
                println!();
            } else {
                error("Failed to build VM. Check the errors above.");
                println!();
            }

            Ok(())
        }

        NixOSCommands::Apply { config_dir, flake } => {
            let config_dir = config_dir.map(|p| p.to_path_buf());

            header("🚀 APPLYING NIXOS CONFIGURATION");

            if let Some(ref dir) = config_dir {
                info_line("Configuration", &dir.display().to_string());
            }
            info_line("Mode", if flake { "Flake" } else { "Traditional" });
            println!();

            warning("This will modify your system configuration!");
            println!();

            let code = run_nixos_rebuild("switch", config_dir.as_deref(), flake)?;

            if code == 0 {
                success("NixOS configuration applied successfully!");
                println!();
            } else {
                error("Failed to apply configuration.");
                println!();
            }

            Ok(())
        }

        NixOSCommands::Rollback => {
            header("⏮️  NIXOS ROLLBACK");
            println!();

            warning("Rolling back to previous generation...");
            println!();

            let code = run_nixos_rebuild("switch", None, false)?;

            if code == 0 {
                success("Rolled back to previous generation!");
                println!();
            } else {
                error("Failed to rollback.");
                println!();
            }

            Ok(())
        }

        NixOSCommands::ListGenerations => {
            header("📜 NIXOS GENERATIONS");
            println!();

            let generations = list_generations()?;

            if generations.is_empty() {
                warning("No generations found. Are you running NixOS?");
            } else {
                for gen in generations {
                    println!("  {}", gen);
                }
            }

            println!();
            Ok(())
        }
    }
}
