use anyhow::Result;
use flate2::write::{GzEncoder, GzDecoder};
use flate2::Compression;
use sled::Db;
use std::io::{Write, Read};
use std::path::PathBuf;

const COMPRESSION_THRESHOLD: usize = 1024; // Compress values larger than 1KB

pub struct DataStore {
    db: Db,
}

impl DataStore {
    pub fn new() -> Result<Self> {
        let data_dir = Self::get_data_dir()?;
        std::fs::create_dir_all(&data_dir)?;

        let db_path = data_dir.join("capsule.db");
        let db = sled::open(&db_path)?;

        Ok(Self { db })
    }

    fn get_data_dir() -> Result<PathBuf> {
        let home = home::home_dir()
            .ok_or_else(|| anyhow::anyhow!("Could not find home directory"))?;
        Ok(home.join(".capsule").join("data"))
    }

    /// Store a key-value pair
    pub fn set(&self, key: &str, value: &[u8]) -> Result<()> {
        let stored_value = if value.len() > COMPRESSION_THRESHOLD {
            // Compress large values
            let mut encoder = GzEncoder::new(Vec::new(), Compression::default());
            encoder.write_all(value)?;
            let compressed = encoder.finish()?;

            // Prepend magic byte to indicate compression
            let mut result = vec![0x1f]; // Magic byte for compressed data
            result.extend_from_slice(&compressed);
            result
        } else {
            // Small values stored as-is with different magic byte
            let mut result = vec![0x00]; // Magic byte for uncompressed data
            result.extend_from_slice(value);
            result
        };

        self.db.insert(key.as_bytes(), stored_value)?;
        self.db.flush()?;
        Ok(())
    }

    /// Get a value by key
    pub fn get(&self, key: &str) -> Result<Option<Vec<u8>>> {
        if let Some(stored_value) = self.db.get(key.as_bytes())? {
            let data = stored_value.to_vec();

            if data.is_empty() {
                return Ok(Some(Vec::new()));
            }

            // Check magic byte
            match data[0] {
                0x1f => {
                    // Compressed data
                    let mut decoder = GzDecoder::new(Vec::new());
                    decoder.write_all(&data[1..])?;
                    let decompressed = decoder.finish()?;
                    Ok(Some(decompressed))
                }
                0x00 => {
                    // Uncompressed data
                    Ok(Some(data[1..].to_vec()))
                }
                _ => {
                    // Unknown format, return as-is (backwards compatibility)
                    Ok(Some(data))
                }
            }
        } else {
            Ok(None)
        }
    }

    /// Delete a key
    pub fn delete(&self, key: &str) -> Result<bool> {
        let removed = self.db.remove(key.as_bytes())?;
        self.db.flush()?;
        Ok(removed.is_some())
    }

    /// List all keys
    pub fn list_keys(&self) -> Result<Vec<String>> {
        let mut keys = Vec::new();
        for item in self.db.iter() {
            let (key, _) = item?;
            if let Ok(key_str) = String::from_utf8(key.to_vec()) {
                keys.push(key_str);
            }
        }
        keys.sort();
        Ok(keys)
    }

    /// List all key-value pairs (returns keys and value sizes)
    pub fn list_all(&self) -> Result<Vec<(String, usize, bool)>> {
        let mut items = Vec::new();
        for item in self.db.iter() {
            let (key, value) = item?;
            if let Ok(key_str) = String::from_utf8(key.to_vec()) {
                let compressed = !value.is_empty() && value[0] == 0x1f;
                let size = value.len() - 1; // Subtract magic byte
                items.push((key_str, size, compressed));
            }
        }
        items.sort_by(|a, b| a.0.cmp(&b.0));
        Ok(items)
    }

    /// Store a file
    pub fn set_file(&self, key: &str, file_path: &std::path::Path) -> Result<()> {
        let data = std::fs::read(file_path)?;
        self.set(key, &data)?;
        Ok(())
    }

    /// Get a file and write it to disk
    pub fn get_file(&self, key: &str, output_path: &std::path::Path) -> Result<bool> {
        if let Some(data) = self.get(key)? {
            std::fs::write(output_path, data)?;
            Ok(true)
        } else {
            Ok(false)
        }
    }

    /// Get database stats
    pub fn stats(&self) -> Result<(usize, usize)> {
        let count = self.db.len();
        let size_on_disk = self.db.size_on_disk()?;
        Ok((count, size_on_disk as usize))
    }

    /// Clear all data
    pub fn clear(&self) -> Result<usize> {
        let count = self.db.len();
        self.db.clear()?;
        self.db.flush()?;
        Ok(count)
    }

    /// Export database to a directory
    pub fn export(&self, output_dir: &std::path::Path) -> Result<usize> {
        std::fs::create_dir_all(output_dir)?;
        let mut count = 0;

        for item in self.db.iter() {
            let (key, _) = item?;
            if let Ok(key_str) = String::from_utf8(key.to_vec()) {
                if let Some(data) = self.get(&key_str)? {
                    let safe_filename = key_str.replace(['/', '\\', ':'], "_");
                    let output_path = output_dir.join(safe_filename);
                    std::fs::write(output_path, data)?;
                    count += 1;
                }
            }
        }

        Ok(count)
    }
}
