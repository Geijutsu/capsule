use anyhow::Result;
use clap::{Parser, Subcommand};
use colored::*;

use capsule::config::*;
use capsule::openmesh::*;
use capsule::ui::*;

#[derive(Parser)]
#[command(name = "capsule")]
#[command(version = "0.1.0")]
#[command(about = "🌱 Capsule - User-friendly server configuration tool", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Option<Commands>,
}

#[derive(Subcommand)]
enum Commands {
    /// Show current configuration
    Show,

    /// List available technology stacks
    Stacks,

    /// Add a technology stack to current profile
    Add {
        /// Stack name to add
        stack: String,
    },

    /// Remove a technology stack from current profile
    Remove {
        /// Stack name to remove
        stack: String,
    },

    /// List all profiles
    Profiles,

    /// Profile management commands
    Profile {
        #[command(subcommand)]
        command: ProfileCommands,
    },

    /// Package management commands
    Pkg {
        #[command(subcommand)]
        command: PkgCommands,
    },

    /// OpenMesh xNode deployment and management
    #[command(after_help = "\n\
╔═══════════════════════════════════════════════════════════════╗\n\
║                   🌐  OPENMESH PLATFORM  🌐                   ║\n\
╚═══════════════════════════════════════════════════════════════╝\n\
\n\
  Deploy and manage OpenMesh xNode infrastructure across multiple\n\
  cloud providers with a unified, beautiful interface.\n\
\n\
  Main Commands:\n\
    xnode        🌐 Deploy and manage xNode instances\n\
    provider     🔧 Configure cloud provider credentials\n\
\n\
  Quick Examples:\n\
    capsule openmesh xnode providers       → List 7 cloud providers\n\
    capsule openmesh xnode templates       → Browse 31 templates\n\
    capsule openmesh xnode deploy          → Smart deployment\n\
    capsule openmesh provider configure    → Set API keys\n\
\n\
  What You Get:\n\
    ✓ 7 cloud providers (AWS, DigitalOcean, Vultr, Hivelocity...)\n\
    ✓ 31 instance templates (budget $0.004/hr to enterprise GPU)\n\
    ✓ 50+ datacenter regions worldwide\n\
    ✓ GPU templates (Tesla V100, RTX 6000, H100)\n\
    ✓ Cost tracking and analytics\n\
    ✓ Inventory management with CSV export\n\
\n\
  💡 Tip: Run 'capsule openmesh xnode --help' for all xNode commands\n\
")]
    Openmesh {
        #[command(subcommand)]
        command: OpenMeshCommands,
    },
}

#[derive(Subcommand)]
enum ProfileCommands {
    /// Create a new profile
    New {
        /// Profile name
        name: String,
    },

    /// Switch to a different profile
    Use {
        /// Profile name
        name: String,
    },

    /// Copy a profile
    Copy {
        /// Source profile name
        src: String,
        /// Destination profile name
        dst: String,
    },

    /// Delete a profile
    Delete {
        /// Profile name
        name: String,
    },
}

#[derive(Subcommand)]
enum PkgCommands {
    /// Add custom packages
    Add {
        /// Package names
        packages: Vec<String>,
    },

    /// Remove custom packages
    Remove {
        /// Package names
        packages: Vec<String>,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();

    match cli.command {
        None => show_overview()?,
        Some(Commands::Show) => show_config()?,
        Some(Commands::Stacks) => list_stacks()?,
        Some(Commands::Add { stack }) => add_stack(&stack)?,
        Some(Commands::Remove { stack }) => remove_stack(&stack)?,
        Some(Commands::Profiles) => list_profiles()?,
        Some(Commands::Profile { command }) => handle_profile_command(command)?,
        Some(Commands::Pkg { command }) => handle_pkg_command(command)?,
        Some(Commands::Openmesh { command }) => handle_openmesh_command(command)?,
    }

    Ok(())
}

fn show_overview() -> Result<()> {
    print_logo();

    let active_name = get_active_config_name()?;
    println!(
        "  {} {}\n",
        "Active Profile:".white(),
        active_name.green().bold()
    );

    section_header("🚀 Quick Start");
    println!(
        "    {} {} {}",
        "▸".green().bold(),
        "capsule stacks".cyan().bold(),
        "          List available stacks".white()
    );
    println!(
        "    {} {} {} {}",
        "▸".green().bold(),
        "capsule add".cyan().bold(),
        "<stack>".cyan(),
        "         Add a technology stack".white()
    );
    println!(
        "    {} {} {}",
        "▸".green().bold(),
        "capsule show".cyan().bold(),
        "           View configuration".white()
    );
    println!(
        "    {} {} {}",
        "▸".green().bold(),
        "capsule setup".cyan().bold(),
        "           Install packages".white()
    );

    section_header("📁 Configuration Profiles");
    println!(
        "    {} {} {}",
        "○".cyan(),
        "capsule profiles".cyan().bold(),
        "        List all profiles".white()
    );
    println!(
        "    {} {} {} {}",
        "○".cyan(),
        "capsule profile new".cyan().bold(),
        "<name>".cyan(),
        "    Create new profile".white()
    );
    println!(
        "    {} {} {} {}",
        "○".cyan(),
        "capsule profile use".cyan().bold(),
        "<name>".cyan(),
        "    Switch profile".white()
    );

    section_header("🔧 Main Commands");
    println!(
        "    {} {} {}",
        "•".magenta().bold(),
        "bootstrap".cyan().bold(),
        "          Install dependencies".white()
    );
    println!(
        "    {} {} {}",
        "•".magenta().bold(),
        "config".cyan().bold(),
        "             Manage configuration".white()
    );
    println!(
        "    {} {} {}",
        "•".magenta().bold(),
        "setup".cyan().bold(),
        "              Install configured packages".white()
    );
    println!(
        "    {} {} {}",
        "•".magenta().bold(),
        "check".cyan().bold(),
        "              Dry run / preview changes".white()
    );
    println!(
        "    {} {} {}",
        "•".magenta().bold(),
        "preview".cyan().bold(),
        "            Show generated configuration".white()
    );
    println!(
        "    {} {} {}",
        "•".magenta().bold(),
        "list".cyan().bold(),
        "               List package status".white()
    );
    println!(
        "    {} {} {}",
        "•".magenta().bold(),
        "plant".cyan().bold(),
        "              Deploy to remote server".white()
    );
    println!(
        "    {} {} {}",
        "•".magenta().bold(),
        "docs".cyan().bold(),
        "               Interactive documentation".white()
    );
    println!(
        "    {} {} {}",
        "•".magenta().bold(),
        "update".cyan().bold(),
        "             Update to latest version".white()
    );
    println!(
        "    {} {} {}",
        "•".magenta().bold(),
        "backup".cyan().bold(),
        "             Backup package list".white()
    );
    println!(
        "    {} {} {}",
        "•".magenta().bold(),
        "restore".cyan().bold(),
        "            Restore from backup".white()
    );

    section_header("🌱 Sprouts (Quick Install)");
    println!(
        "    {} {} {}",
        "▸".green().bold(),
        "sprouts".cyan().bold(),
        "           List available sprouts".white()
    );
    println!(
        "    {} {} {} {}",
        "▸".green().bold(),
        "sprout".cyan().bold(),
        "<name>".cyan(),
        "      Install a sprout".white()
    );

    divider();
    println!();
    println!(
        "  {} Run {} for detailed command list",
        "💡 Tip:".cyan(),
        "capsule --help".cyan().bold()
    );
    println!();

    Ok(())
}

fn show_config() -> Result<()> {
    let active_name = get_active_config_name()?;
    let config = load_config(None)?;

    header("⚙  CONFIGURATION");

    println!(
        "  {} {}\n",
        "Active Profile:".white(),
        active_name.cyan().bold()
    );

    section_header("Technology Stacks");
    if !config.presets.is_empty() {
        for preset in &config.presets {
            if preset == "base" {
                preset_item(preset, "(core packages)", true);
            } else {
                // In a real implementation, we'd load preset data from files
                preset_item(preset, "", true);
            }
        }
    } else {
        println!("{}", "  No stacks configured".white());
    }

    if !config.custom_packages.is_empty() {
        section_header("Individual Packages");
        for pkg in &config.custom_packages {
            package_item(pkg);
        }
    }

    section_header("Settings");
    let editor_value = config.editor.as_deref().unwrap_or("vim");
    info_line("Editor", &editor_value.cyan().to_string());

    // Show config source
    if is_builtin_profile(&active_name) {
        info_line(
            "Source",
            &"Built-in profile (read-only)".yellow().to_string(),
        );
    } else {
        let config_path = get_config_file(None)?;
        info_line("Config File", &config_path.display().to_string().white());
    }
    println!();

    Ok(())
}

fn list_stacks() -> Result<()> {
    header("📦 TECHNOLOGY STACKS");

    section_header("Languages & Runtimes 🔧");
    println!("  {} {:14} {}", "○".cyan(), "python", "Python 3.x development".white());
    println!("  {} {:14} {}", "○".cyan(), "nodejs", "Node.js & npm".white());
    println!("  {} {:14} {}", "○".cyan(), "golang", "Go programming language".white());
    println!("  {} {:14} {}", "○".cyan(), "rust", "Rust programming language".white());

    section_header("Development Tools 🛠");
    println!("  {} {:14} {}", "○".cyan(), "devtools", "General dev utilities".white());
    println!("  {} {:14} {}", "○".cyan(), "cli-tools", "CLI productivity tools".white());
    println!("  {} {:14} {}", "○".cyan(), "github", "GitHub CLI & tools".white());

    section_header("Infrastructure 🏗");
    println!("  {} {:14} {}", "○".cyan(), "docker", "Docker & docker-compose".white());
    println!("  {} {:14} {}", "○".cyan(), "database", "PostgreSQL, MySQL, Redis".white());
    println!("  {} {:14} {}", "○".cyan(), "webserver", "Nginx, Apache".white());

    section_header("Security & Monitoring 🔒");
    println!("  {} {:14} {}", "○".cyan(), "security", "Security tools".white());
    println!("  {} {:14} {}", "○".cyan(), "monitoring", "System monitoring".white());

    section_header("AI/ML 🤖");
    println!("  {} {:14} {}", "○".cyan(), "machine-learning", "ML frameworks & tools".white());
    println!("  {} {:14} {}", "○".cyan(), "ollama", "Local LLM runtime".white());
    println!("  {} {:14} {}", "○".cyan(), "cuda", "NVIDIA CUDA support".white());

    divider();
    println!();
    println!(
        "  {} Use {} to add a stack",
        "💡 Tip:".cyan(),
        "capsule add <stack>".cyan().bold()
    );
    println!();

    Ok(())
}

fn add_stack(stack: &str) -> Result<()> {
    let active_name = get_active_config_name()?;

    if is_builtin_profile(&active_name) {
        error(&format!(
            "Cannot modify built-in profile '{}'. Create a new profile first.",
            active_name
        ));
        return Ok(());
    }

    add_preset(stack, None)?;
    success(&format!("Added stack '{}' to profile '{}'", stack, active_name));

    Ok(())
}

fn remove_stack(stack: &str) -> Result<()> {
    let active_name = get_active_config_name()?;

    if is_builtin_profile(&active_name) {
        error(&format!(
            "Cannot modify built-in profile '{}'. Create a new profile first.",
            active_name
        ));
        return Ok(());
    }

    remove_preset(stack, None)?;
    success(&format!(
        "Removed stack '{}' from profile '{}'",
        stack, active_name
    ));

    Ok(())
}

fn list_profiles() -> Result<()> {
    header("📁 CONFIGURATION PROFILES");

    let active = get_active_config_name()?;

    section_header("Built-in Profiles");
    for name in list_builtin_profiles() {
        let is_active = name == active;
        if let Some(profile) = get_builtin_profile(&name) {
            let desc = profile.description.unwrap_or_default();
            preset_item(&name, &desc, is_active);
        }
    }

    let user_configs = list_all_configs()?;
    if !user_configs.is_empty() {
        section_header("User Profiles");
        for name in user_configs {
            let is_active = name == active;
            preset_item(&name, "", is_active);
        }
    }

    divider();
    println!();
    println!(
        "  {} Active profile: {}",
        "▸".cyan(),
        active.green().bold()
    );
    println!(
        "  {} Use {} to switch profiles",
        "💡 Tip:".cyan(),
        "capsule profile use <name>".cyan().bold()
    );
    println!();

    Ok(())
}

fn handle_profile_command(command: ProfileCommands) -> Result<()> {
    match command {
        ProfileCommands::New { name } => {
            ensure_config(Some(&name))?;
            success(&format!("Created new profile '{}'", name));
        }
        ProfileCommands::Use { name } => {
            // Check if profile exists (either built-in or user)
            if !is_builtin_profile(&name) {
                let user_configs = list_all_configs()?;
                if !user_configs.contains(&name) {
                    error(&format!("Profile '{}' not found", name));
                    return Ok(());
                }
            }

            set_active_config_name(&name)?;
            success(&format!("Switched to profile '{}'", name));
        }
        ProfileCommands::Copy { src, dst } => {
            copy_profile(&src, &dst)?;
            success(&format!("Copied profile '{}' to '{}'", src, dst));
        }
        ProfileCommands::Delete { name } => {
            delete_profile(&name)?;
            success(&format!("Deleted profile '{}'", name));
        }
    }

    Ok(())
}

fn handle_pkg_command(command: PkgCommands) -> Result<()> {
    let active_name = get_active_config_name()?;

    if is_builtin_profile(&active_name) {
        error(&format!(
            "Cannot modify built-in profile '{}'. Create a new profile first.",
            active_name
        ));
        return Ok(());
    }

    match command {
        PkgCommands::Add { packages } => {
            add_packages(&packages, None)?;
            success(&format!(
                "Added {} package(s) to profile '{}'",
                packages.len(),
                active_name
            ));
        }
        PkgCommands::Remove { packages } => {
            remove_packages(&packages, None)?;
            success(&format!(
                "Removed {} package(s) from profile '{}'",
                packages.len(),
                active_name
            ));
        }
    }

    Ok(())
}
