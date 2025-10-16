// Terminal UI utilities for Capsule

use colored::Colorize;

/// Print a header banner
pub fn header(text: &str) {
    println!();
    println!("{}", "═".repeat(70).bright_blue());
    println!("  {}", text.bold().bright_cyan());
    println!("{}", "═".repeat(70).bright_blue());
    println!();
}

/// Print a section header
pub fn section_header(text: &str) {
    println!();
    println!("  {}", text.bold().bright_white());
    println!("  {}", "─".repeat(text.len()).bright_black());
}

/// Print a divider
pub fn divider() {
    println!("{}", "─".repeat(70).bright_black());
}

/// Print a success message
pub fn success(text: &str) {
    println!("  {} {}", "✓".green().bold(), text.green());
}

/// Print an error message
pub fn error(text: &str) {
    eprintln!("  {} {}", "✗".red().bold(), text.red());
}

/// Print a warning message
pub fn warning(text: &str) {
    println!("  {} {}", "⚠".yellow().bold(), text.yellow());
}

/// Print an info line with label and value
pub fn info_line(label: &str, value: &str) {
    println!("  {}: {}", label.bright_black(), value);
}

/// Print a banner with ASCII art
pub fn banner(text: &str) {
    println!();
    println!("{}", "╔═══════════════════════════════════════════════════════════╗".bright_blue());
    println!("{}  {:<57}  {}", "║".bright_blue(), text.bright_cyan().bold(), "║".bright_blue());
    println!("{}", "╚═══════════════════════════════════════════════════════════╝".bright_blue());
    println!();
}

/// Print the Capsule logo
pub fn print_logo() {
    let logo = r#"
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║      ██████╗ █████╗ ██████╗ ███████╗██╗   ██╗██╗         ║
    ║     ██╔════╝██╔══██╗██╔══██╗██╔════╝██║   ██║██║         ║
    ║     ██║     ███████║██████╔╝███████╗██║   ██║██║         ║
    ║     ██║     ██╔══██║██╔═══╝ ╚════██║██║   ██║██║         ║
    ║     ╚██████╗██║  ██║██║     ███████║╚██████╔╝███████╗    ║
    ║      ╚═════╝╚═╝  ╚═╝╚═╝     ╚══════╝ ╚═════╝ ╚══════╝    ║
    ║                                                           ║
    ║              Nix-Powered Configuration                   ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    "#;
    println!("{}", logo.bright_blue());
}

/// Print a preset/stack item with active indicator
pub fn preset_item(name: &str, description: &str, active: bool) {
    let (icon, name_colored) = if active {
        ("●".green().bold(), format!("{:14}", name).green().bold())
    } else {
        ("○".cyan(), format!("{:14}", name).cyan())
    };

    if description.is_empty() {
        println!("  {} {}", icon, name_colored);
    } else {
        println!("  {} {} {}", icon, name_colored, description.white());
    }
}

/// Print a package item
pub fn package_item(name: &str) {
    let icon = "◆".magenta().bold();
    let name_colored = name.magenta().bold();
    println!("  {} {}", icon, name_colored);
}
