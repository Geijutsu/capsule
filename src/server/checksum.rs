use anyhow::{Context, Result};
use colored::*;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::io::{BufReader, Read};
use std::path::Path;

/// Represents the checksum manifest for a snapshot
#[derive(Debug, Serialize, Deserialize)]
pub struct ChecksumManifest {
    pub version: String,
    pub created_at: String,
    pub files: HashMap<String, FileChecksum>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct FileChecksum {
    pub sha256: String,
    pub size: u64,
    pub path: String,
}

impl ChecksumManifest {
    pub fn new() -> Self {
        Self {
            version: "1.0".to_string(),
            created_at: chrono::Utc::now().to_rfc3339(),
            files: HashMap::new(),
        }
    }

    /// Generate checksums for all files in a directory
    pub fn generate(snapshot_dir: &Path) -> Result<Self> {
        let mut manifest = Self::new();

        // Files to checksum
        let files_to_check = vec![
            "configuration.nix",
            "packages.nix",
            "users.nix",
            "README.md",
        ];

        for file_name in files_to_check {
            let file_path = snapshot_dir.join(file_name);
            if file_path.exists() {
                let checksum = compute_file_checksum(&file_path)?;
                manifest.files.insert(file_name.to_string(), checksum);
            }
        }

        // Checksum all service files
        let services_dir = snapshot_dir.join("services");
        if services_dir.exists() {
            for entry in fs::read_dir(&services_dir)? {
                let entry = entry?;
                let path = entry.path();

                if path.is_file() {
                    let file_name = path
                        .strip_prefix(snapshot_dir)
                        .unwrap()
                        .to_string_lossy()
                        .to_string();

                    let checksum = compute_file_checksum(&path)?;
                    manifest.files.insert(file_name, checksum);
                }
            }
        }

        // Checksum etc-overrides if present
        let etc_overrides = snapshot_dir.join("etc-overrides");
        if etc_overrides.exists() {
            Self::checksum_directory_recursive(&etc_overrides, snapshot_dir, &mut manifest)?;
        }

        Ok(manifest)
    }

    fn checksum_directory_recursive(
        dir: &Path,
        base_dir: &Path,
        manifest: &mut ChecksumManifest,
    ) -> Result<()> {
        for entry in fs::read_dir(dir)? {
            let entry = entry?;
            let path = entry.path();

            if path.is_file() {
                let relative_path = path
                    .strip_prefix(base_dir)
                    .unwrap()
                    .to_string_lossy()
                    .to_string();

                let checksum = compute_file_checksum(&path)?;
                manifest.files.insert(relative_path, checksum);
            } else if path.is_dir() {
                Self::checksum_directory_recursive(&path, base_dir, manifest)?;
            }
        }
        Ok(())
    }

    /// Save manifest to file
    pub fn save(&self, path: &Path) -> Result<()> {
        let json = serde_json::to_string_pretty(self)
            .context("Failed to serialize checksum manifest")?;

        fs::write(path, json)
            .context("Failed to write checksum manifest")
    }

    /// Load manifest from file
    pub fn load(path: &Path) -> Result<Self> {
        let content = fs::read_to_string(path)
            .context("Failed to read checksum manifest")?;

        serde_json::from_str(&content)
            .context("Failed to parse checksum manifest")
    }

    /// Validate snapshot against this manifest
    pub fn validate(&self, snapshot_dir: &Path, verbose: bool) -> Result<ValidationReport> {
        let mut report = ValidationReport {
            total_files: self.files.len(),
            valid_files: 0,
            invalid_files: 0,
            missing_files: 0,
            errors: Vec::new(),
        };

        for (file_path, expected_checksum) in &self.files {
            let full_path = snapshot_dir.join(file_path);

            if !full_path.exists() {
                report.missing_files += 1;
                report.errors.push(ValidationError {
                    file: file_path.clone(),
                    error_type: ErrorType::Missing,
                    expected: Some(expected_checksum.sha256.clone()),
                    actual: None,
                });
                continue;
            }

            match compute_file_checksum(&full_path) {
                Ok(actual_checksum) => {
                    if actual_checksum.sha256 == expected_checksum.sha256 {
                        report.valid_files += 1;
                        if verbose {
                            println!("  {} {}", "✓".green(), file_path);
                        }
                    } else {
                        report.invalid_files += 1;
                        report.errors.push(ValidationError {
                            file: file_path.clone(),
                            error_type: ErrorType::Mismatch,
                            expected: Some(expected_checksum.sha256.clone()),
                            actual: Some(actual_checksum.sha256.clone()),
                        });
                    }
                }
                Err(e) => {
                    report.invalid_files += 1;
                    report.errors.push(ValidationError {
                        file: file_path.clone(),
                        error_type: ErrorType::ReadError(e.to_string()),
                        expected: Some(expected_checksum.sha256.clone()),
                        actual: None,
                    });
                }
            }
        }

        Ok(report)
    }
}

/// Compute SHA256 checksum for a file
fn compute_file_checksum(path: &Path) -> Result<FileChecksum> {
    use sha2::{Sha256, Digest};

    let file = fs::File::open(path)
        .context(format!("Failed to open file: {}", path.display()))?;

    let metadata = file.metadata()?;
    let size = metadata.len();

    let mut reader = BufReader::new(file);
    let mut hasher = Sha256::new();
    let mut buffer = [0; 8192];

    loop {
        let count = reader.read(&mut buffer)?;
        if count == 0 {
            break;
        }
        hasher.update(&buffer[..count]);
    }

    let hash = hasher.finalize();
    let sha256 = format!("{:x}", hash);

    Ok(FileChecksum {
        sha256,
        size,
        path: path.to_string_lossy().to_string(),
    })
}

#[derive(Debug)]
pub struct ValidationReport {
    pub total_files: usize,
    pub valid_files: usize,
    pub invalid_files: usize,
    pub missing_files: usize,
    pub errors: Vec<ValidationError>,
}

#[derive(Debug)]
pub struct ValidationError {
    pub file: String,
    pub error_type: ErrorType,
    pub expected: Option<String>,
    pub actual: Option<String>,
}

#[derive(Debug)]
pub enum ErrorType {
    Missing,
    Mismatch,
    ReadError(String),
}

impl ValidationReport {
    pub fn is_valid(&self) -> bool {
        self.invalid_files == 0 && self.missing_files == 0
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    #[test]
    fn test_checksum_computation() -> Result<()> {
        let temp_dir = tempfile::tempdir()?;
        let file_path = temp_dir.path().join("test.txt");

        let mut file = fs::File::create(&file_path)?;
        file.write_all(b"Hello, world!")?;
        drop(file);

        let checksum = compute_file_checksum(&file_path)?;

        // SHA256 of "Hello, world!" should be consistent
        assert_eq!(checksum.size, 13);
        assert!(!checksum.sha256.is_empty());

        Ok(())
    }

    #[test]
    fn test_manifest_generation() -> Result<()> {
        let temp_dir = tempfile::tempdir()?;

        // Create test files
        fs::write(temp_dir.path().join("configuration.nix"), "test content")?;
        fs::write(temp_dir.path().join("packages.nix"), "packages")?;

        let manifest = ChecksumManifest::generate(temp_dir.path())?;

        assert!(manifest.files.contains_key("configuration.nix"));
        assert!(manifest.files.contains_key("packages.nix"));

        Ok(())
    }
}
