use std::collections::HashMap;

/// Maps common apt package names to nixpkgs attribute names
pub struct PackageMapper {
    mappings: HashMap<String, String>,
}

impl PackageMapper {
    pub fn new() -> Self {
        let mut mappings = HashMap::new();

        // Common packages with direct mappings
        mappings.insert("nginx".to_string(), "nginx".to_string());
        mappings.insert("apache2".to_string(), "apacheHttpd".to_string());
        mappings.insert("postgresql".to_string(), "postgresql".to_string());
        mappings.insert("postgresql-client".to_string(), "postgresql".to_string());
        mappings.insert("mysql-server".to_string(), "mysql80".to_string());
        mappings.insert("redis-server".to_string(), "redis".to_string());
        mappings.insert("docker.io".to_string(), "docker".to_string());
        mappings.insert("docker-compose".to_string(), "docker-compose".to_string());

        // Programming languages
        mappings.insert("python3".to_string(), "python3".to_string());
        mappings.insert("python3-pip".to_string(), "python3Packages.pip".to_string());
        mappings.insert("nodejs".to_string(), "nodejs".to_string());
        mappings.insert("npm".to_string(), "nodejs".to_string());
        mappings.insert("golang-go".to_string(), "go".to_string());
        mappings.insert("rustc".to_string(), "rustc".to_string());
        mappings.insert("cargo".to_string(), "cargo".to_string());

        // Development tools
        mappings.insert("git".to_string(), "git".to_string());
        mappings.insert("vim".to_string(), "vim".to_string());
        mappings.insert("emacs".to_string(), "emacs".to_string());
        mappings.insert("curl".to_string(), "curl".to_string());
        mappings.insert("wget".to_string(), "wget".to_string());
        mappings.insert("htop".to_string(), "htop".to_string());
        mappings.insert("tmux".to_string(), "tmux".to_string());
        mappings.insert("screen".to_string(), "screen".to_string());

        // Build tools
        mappings.insert("build-essential".to_string(), "gcc".to_string());
        mappings.insert("gcc".to_string(), "gcc".to_string());
        mappings.insert("g++".to_string(), "gcc".to_string());
        mappings.insert("make".to_string(), "gnumake".to_string());
        mappings.insert("cmake".to_string(), "cmake".to_string());

        // Compression/Archive
        mappings.insert("tar".to_string(), "gnutar".to_string());
        mappings.insert("gzip".to_string(), "gzip".to_string());
        mappings.insert("bzip2".to_string(), "bzip2".to_string());
        mappings.insert("xz-utils".to_string(), "xz".to_string());
        mappings.insert("zip".to_string(), "zip".to_string());
        mappings.insert("unzip".to_string(), "unzip".to_string());

        // Network tools
        mappings.insert("net-tools".to_string(), "nettools".to_string());
        mappings.insert("openssh-server".to_string(), "openssh".to_string());
        mappings.insert("openssh-client".to_string(), "openssh".to_string());
        mappings.insert("netcat".to_string(), "netcat".to_string());
        mappings.insert("nmap".to_string(), "nmap".to_string());

        // System utilities
        mappings.insert("coreutils".to_string(), "coreutils".to_string());
        mappings.insert("util-linux".to_string(), "util-linux".to_string());
        mappings.insert("findutils".to_string(), "findutils".to_string());
        mappings.insert("grep".to_string(), "gnugrep".to_string());
        mappings.insert("sed".to_string(), "gnused".to_string());
        mappings.insert("awk".to_string(), "gawk".to_string());

        // Text editors and processing
        mappings.insert("nano".to_string(), "nano".to_string());
        mappings.insert("jq".to_string(), "jq".to_string());

        // Monitoring
        mappings.insert("htop".to_string(), "htop".to_string());
        mappings.insert("iotop".to_string(), "iotop".to_string());
        mappings.insert("iftop".to_string(), "iftop".to_string());

        Self { mappings }
    }

    pub fn map(&self, apt_package: &str) -> Option<String> {
        // First try exact match
        if let Some(nix_pkg) = self.mappings.get(apt_package) {
            return Some(nix_pkg.clone());
        }

        // Try without version suffix (e.g., "python3.10" -> "python3")
        if let Some(base_name) = apt_package.split('-').next() {
            if let Some(nix_pkg) = self.mappings.get(base_name) {
                return Some(nix_pkg.clone());
            }
        }

        // Try simple heuristics
        if apt_package.starts_with("lib") && apt_package.contains("-dev") {
            // Development libraries - often same name without -dev
            let base = apt_package.strip_suffix("-dev").unwrap_or(apt_package);
            return Some(base.to_string());
        }

        // If no mapping found, return the original name as fallback
        // Nix might have it under the same name
        Some(apt_package.to_string())
    }

    pub fn is_system_package(&self, package: &str) -> bool {
        // Packages that are essential and should be skipped
        matches!(
            package,
            "base-files"
                | "base-passwd"
                | "bash"
                | "coreutils"
                | "dash"
                | "debconf"
                | "dpkg"
                | "e2fsprogs"
                | "findutils"
                | "grep"
                | "gzip"
                | "hostname"
                | "init"
                | "init-system-helpers"
                | "libc6"
                | "libgcc1"
                | "login"
                | "mount"
                | "ncurses-base"
                | "ncurses-bin"
                | "perl-base"
                | "sed"
                | "sysvinit-utils"
                | "tar"
                | "ubuntu-keyring"
                | "util-linux"
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_common_mappings() {
        let mapper = PackageMapper::new();

        assert_eq!(mapper.map("nginx"), Some("nginx".to_string()));
        assert_eq!(mapper.map("apache2"), Some("apacheHttpd".to_string()));
        assert_eq!(mapper.map("python3"), Some("python3".to_string()));
        assert_eq!(mapper.map("docker.io"), Some("docker".to_string()));
    }

    #[test]
    fn test_system_packages() {
        let mapper = PackageMapper::new();

        assert!(mapper.is_system_package("bash"));
        assert!(mapper.is_system_package("coreutils"));
        assert!(!mapper.is_system_package("nginx"));
    }
}
