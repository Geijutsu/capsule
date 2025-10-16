/// Linode API Client
///
/// Provides API client for Linode's cloud infrastructure platform.
/// Uses Bearer token authentication.

use super::client::ApiClient;
use super::error::ApiResult;

/// Linode API client
pub struct LinodeClient {
    client: ApiClient,
}

impl LinodeClient {
    /// Create a new Linode API client
    ///
    /// # Arguments
    ///
    /// * `api_key` - Linode API token
    ///
    /// # Example
    ///
    /// ```no_run
    /// use capsule::api::linode::LinodeClient;
    ///
    /// let client = LinodeClient::new("your-api-token").unwrap();
    /// ```
    pub fn new(api_key: impl Into<String>) -> ApiResult<Self> {
        let client = ApiClient::builder("https://api.linode.com/v4")
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
        let client = LinodeClient::new("test-token");
        assert!(client.is_ok());
    }
}
