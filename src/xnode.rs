use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct XNode {
    pub id: String,
    pub name: String,
    pub status: String,
    pub ip_address: String,
    #[serde(default = "default_ssh_port")]
    pub ssh_port: u16,
    pub tunnel_port: Option<u16>,
    #[serde(default = "Utc::now")]
    pub created_at: DateTime<Utc>,
    pub region: Option<String>,
    #[serde(default)]
    pub metadata: HashMap<String, serde_json::Value>,
}

fn default_ssh_port() -> u16 {
    22
}

impl XNode {
    pub fn new(
        id: String,
        name: String,
        status: String,
        ip_address: String,
    ) -> Self {
        Self {
            id,
            name,
            status,
            ip_address,
            ssh_port: 22,
            tunnel_port: None,
            created_at: Utc::now(),
            region: None,
            metadata: HashMap::new(),
        }
    }

    pub fn is_running(&self) -> bool {
        self.status == "running"
    }

    pub fn is_stopped(&self) -> bool {
        self.status == "stopped"
    }

    pub fn is_deploying(&self) -> bool {
        self.status == "deploying"
    }
}
