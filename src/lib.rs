// Core modules for the CLI framework
pub mod config;
pub mod openmesh;
pub mod providers;
pub mod ui;

// Monitoring system - READY FOR INTEGRATION
pub mod monitoring;

// Inventory and cost tracking modules
pub mod xnode;
pub mod inventory;
pub mod cost;
pub mod openmesh_cli;

// API clients and HTTP integration
pub mod api;

// Nix integration modules
pub mod nix;
pub mod nixos;

// Re-export for convenience
pub use config::*;
pub use openmesh::*;
pub use providers::*;
pub use ui::*;

// Re-export inventory types
pub use xnode::XNode;
pub use inventory::{XNodeInventory, XNodeEntry, XNodeUpdate, InventoryStatistics};
pub use cost::{CostReport, DeploymentRecord};
