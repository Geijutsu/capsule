/// Vultr API Client
///
/// Provides API client for Vultr's cloud infrastructure platform.
/// Uses Bearer token authentication.

use super::client::ApiClient;
use super::error::ApiResult;

/// Vultr API client
pub struct VultrClient {
    client: ApiClient,
}

impl VultrClient {
    /// Create a new Vultr API client
    ///
    /// # Arguments
    ///
    /// * `api_key` - Vultr API key
    ///
    /// # Example
    ///
    /// ```no_run
    /// use capsule::api::vultr::VultrClient;
    ///
    /// let client = VultrClient::new("your-api-key").unwrap();
    /// ```
    pub fn new(api_key: impl Into<String>) -> ApiResult<Self> {
        let client = ApiClient::builder("https://api.vultr.com/v2")
            .bearer_auth(api_key)
            .build()?;

        Ok(Self { client })
    }

    /// Get reference to underlying API client
    pub fn client(&self) -> &ApiClient {
        &self.client
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_client_creation() {
        let client = VultrClient::new("test-key");
        assert!(client.is_ok());
    }
}
