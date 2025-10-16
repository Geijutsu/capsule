/// API Error Types
///
/// Provides error types for API operations with proper error handling
/// for authentication, rate limiting, and other API-related failures.

use thiserror::Error;

/// Main API error type
#[derive(Error, Debug)]
pub enum ApiError {
    /// Authentication failure (401, 403)
    #[error("Authentication failed: {message}")]
    Authentication {
        message: String,
        status_code: Option<u16>,
        response: Option<String>,
    },

    /// Rate limit exceeded (429)
    #[error("Rate limit exceeded: {message}")]
    RateLimit {
        message: String,
        status_code: Option<u16>,
        response: Option<String>,
    },

    /// Resource not found (404)
    #[error("Resource not found: {message}")]
    ResourceNotFound {
        message: String,
        status_code: Option<u16>,
        response: Option<String>,
    },

    /// General API error
    #[error("API error ({status_code}): {message}")]
    General {
        message: String,
        status_code: u16,
        response: Option<String>,
    },

    /// Connection error
    #[error("Connection error: {0}")]
    Connection(String),

    /// Timeout error
    #[error("Request timeout: {0}")]
    Timeout(String),

    /// Request building error
    #[error("Request building error: {0}")]
    RequestBuild(String),

    /// JSON parsing error
    #[error("JSON parsing error: {0}")]
    JsonParse(String),

    /// Network error
    #[error("Network error: {0}")]
    Network(String),
}

/// Result type alias for API operations
pub type ApiResult<T> = Result<T, ApiError>;

impl ApiError {
    /// Create authentication error
    pub fn authentication(message: impl Into<String>, status_code: Option<u16>) -> Self {
        Self::Authentication {
            message: message.into(),
            status_code,
            response: None,
        }
    }

    /// Create rate limit error
    pub fn rate_limit(message: impl Into<String>, status_code: Option<u16>) -> Self {
        Self::RateLimit {
            message: message.into(),
            status_code,
            response: None,
        }
    }

    /// Create resource not found error
    pub fn resource_not_found(message: impl Into<String>, status_code: Option<u16>) -> Self {
        Self::ResourceNotFound {
            message: message.into(),
            status_code,
            response: None,
        }
    }

    /// Create general API error
    pub fn general(message: impl Into<String>, status_code: u16) -> Self {
        Self::General {
            message: message.into(),
            status_code,
            response: None,
        }
    }

    /// Check if this is a rate limit error
    pub fn is_rate_limit(&self) -> bool {
        matches!(self, ApiError::RateLimit { .. })
    }

    /// Get status code if available
    pub fn status_code(&self) -> Option<u16> {
        match self {
            ApiError::Authentication { status_code, .. }
            | ApiError::RateLimit { status_code, .. }
            | ApiError::ResourceNotFound { status_code, .. } => *status_code,
            ApiError::General { status_code, .. } => Some(*status_code),
            _ => None,
        }
    }
}

impl From<reqwest::Error> for ApiError {
    fn from(err: reqwest::Error) -> Self {
        if err.is_timeout() {
            ApiError::Timeout(err.to_string())
        } else if err.is_connect() {
            ApiError::Connection(err.to_string())
        } else if err.is_request() {
            ApiError::RequestBuild(err.to_string())
        } else if err.is_decode() {
            ApiError::JsonParse(err.to_string())
        } else {
            ApiError::Network(err.to_string())
        }
    }
}
