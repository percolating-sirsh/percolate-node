//! Sync state machine for replica catchup logic.
//!
//! Manages state transitions during replication sync process.

use std::time::{Duration, Instant};

/// Sync state for replica catchup.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SyncState {
    /// Not connected to primary
    Disconnected,
    /// Attempting to connect to primary
    Connecting,
    /// Actively syncing WAL entries
    Syncing,
    /// Caught up and following real-time
    Synced,
    /// Error occurred, needs retry
    Error,
}

/// State machine for managing replication sync.
///
/// # State Transitions
///
/// ```text
/// Disconnected → Connecting → Syncing → Synced
///      ↑             ↓          ↓         ↓
///      └─────────── Error ←────────────────┘
/// ```
///
/// # Example
///
/// ```
/// use rem_db::replication::SyncStateMachine;
///
/// let mut sm = SyncStateMachine::new();
/// assert_eq!(sm.state(), SyncState::Disconnected);
///
/// sm.start_connecting();
/// assert_eq!(sm.state(), SyncState::Connecting);
///
/// sm.start_syncing();
/// assert_eq!(sm.state(), SyncState::Syncing);
///
/// sm.mark_synced();
/// assert_eq!(sm.state(), SyncState::Synced);
/// ```
pub struct SyncStateMachine {
    state: SyncState,
    state_entered_at: Instant,
    retry_count: u32,
}

impl SyncStateMachine {
    /// Create new sync state machine in Disconnected state.
    ///
    /// # Returns
    ///
    /// New `SyncStateMachine` instance
    ///
    /// # Example
    ///
    /// ```
    /// let sm = SyncStateMachine::new();
    /// assert_eq!(sm.state(), SyncState::Disconnected);
    /// ```
    pub fn new() -> Self {
        Self {
            state: SyncState::Disconnected,
            state_entered_at: Instant::now(),
            retry_count: 0,
        }
    }

    /// Get current state.
    ///
    /// # Returns
    ///
    /// Current `SyncState`
    ///
    /// # Example
    ///
    /// ```
    /// let sm = SyncStateMachine::new();
    /// assert_eq!(sm.state(), SyncState::Disconnected);
    /// ```
    pub fn state(&self) -> SyncState {
        self.state
    }

    /// Get time spent in current state.
    ///
    /// # Returns
    ///
    /// Duration since state was entered
    ///
    /// # Example
    ///
    /// ```
    /// let sm = SyncStateMachine::new();
    /// std::thread::sleep(std::time::Duration::from_millis(100));
    /// assert!(sm.time_in_state() >= std::time::Duration::from_millis(100));
    /// ```
    pub fn time_in_state(&self) -> Duration {
        self.state_entered_at.elapsed()
    }

    /// Get number of retry attempts.
    ///
    /// # Returns
    ///
    /// Retry count (reset on successful transition to Synced)
    pub fn retry_count(&self) -> u32 {
        self.retry_count
    }

    /// Transition to connecting state.
    ///
    /// Valid from: Disconnected, Error
    ///
    /// # Example
    ///
    /// ```
    /// let mut sm = SyncStateMachine::new();
    /// sm.start_connecting();
    /// assert_eq!(sm.state(), SyncState::Connecting);
    /// ```
    pub fn start_connecting(&mut self) {
        match self.state {
            SyncState::Disconnected | SyncState::Error => {
                self.transition_to(SyncState::Connecting);
            }
            _ => {
                // Invalid transition, stay in current state
            }
        }
    }

    /// Transition to syncing state.
    ///
    /// Valid from: Connecting
    ///
    /// # Example
    ///
    /// ```
    /// let mut sm = SyncStateMachine::new();
    /// sm.start_connecting();
    /// sm.start_syncing();
    /// assert_eq!(sm.state(), SyncState::Syncing);
    /// ```
    pub fn start_syncing(&mut self) {
        match self.state {
            SyncState::Connecting => {
                self.transition_to(SyncState::Syncing);
            }
            _ => {
                // Invalid transition, stay in current state
            }
        }
    }

    /// Transition to synced state.
    ///
    /// Valid from: Syncing, Synced (already synced)
    ///
    /// Resets retry count on successful sync.
    ///
    /// # Example
    ///
    /// ```
    /// let mut sm = SyncStateMachine::new();
    /// sm.start_connecting();
    /// sm.start_syncing();
    /// sm.mark_synced();
    /// assert_eq!(sm.state(), SyncState::Synced);
    /// assert_eq!(sm.retry_count(), 0);
    /// ```
    pub fn mark_synced(&mut self) {
        match self.state {
            SyncState::Syncing | SyncState::Synced => {
                self.transition_to(SyncState::Synced);
                self.retry_count = 0; // Reset retry count on success
            }
            _ => {
                // Invalid transition, stay in current state
            }
        }
    }

    /// Transition to error state.
    ///
    /// Valid from: Any state
    ///
    /// Increments retry count.
    ///
    /// # Example
    ///
    /// ```
    /// let mut sm = SyncStateMachine::new();
    /// sm.start_connecting();
    /// sm.mark_error();
    /// assert_eq!(sm.state(), SyncState::Error);
    /// assert_eq!(sm.retry_count(), 1);
    /// ```
    pub fn mark_error(&mut self) {
        self.transition_to(SyncState::Error);
        self.retry_count += 1;
    }

    /// Transition to disconnected state.
    ///
    /// Valid from: Any state
    ///
    /// # Example
    ///
    /// ```
    /// let mut sm = SyncStateMachine::new();
    /// sm.start_connecting();
    /// sm.disconnect();
    /// assert_eq!(sm.state(), SyncState::Disconnected);
    /// ```
    pub fn disconnect(&mut self) {
        self.transition_to(SyncState::Disconnected);
    }

    /// Calculate backoff duration for retries.
    ///
    /// Uses exponential backoff with jitter:
    /// - Retry 1: 1s
    /// - Retry 2: 2s
    /// - Retry 3: 4s
    /// - Retry 4: 8s
    /// - Max: 60s
    ///
    /// # Returns
    ///
    /// Duration to wait before retry
    ///
    /// # Example
    ///
    /// ```
    /// let mut sm = SyncStateMachine::new();
    /// sm.mark_error(); // retry_count = 1
    /// let backoff = sm.backoff_duration();
    /// assert!(backoff >= Duration::from_secs(1));
    /// assert!(backoff <= Duration::from_secs(2));
    /// ```
    pub fn backoff_duration(&self) -> Duration {
        let base_ms = 1000; // 1 second
        let max_ms = 60_000; // 60 seconds

        // Exponential backoff: 2^(retry_count - 1) seconds
        let backoff_ms = if self.retry_count == 0 {
            base_ms
        } else {
            base_ms * 2_u64.pow(self.retry_count.saturating_sub(1))
        };

        let backoff_ms = backoff_ms.min(max_ms);

        Duration::from_millis(backoff_ms)
    }

    /// Check if retry should be attempted.
    ///
    /// Returns true if:
    /// - State is Error
    /// - Retry count < max retries (10)
    ///
    /// # Returns
    ///
    /// `true` if retry should be attempted
    pub fn should_retry(&self) -> bool {
        self.state == SyncState::Error && self.retry_count < 10
    }

    /// Internal helper to transition state.
    fn transition_to(&mut self, new_state: SyncState) {
        self.state = new_state;
        self.state_entered_at = Instant::now();
    }
}

impl Default for SyncStateMachine {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::thread::sleep;

    #[test]
    fn test_initial_state() {
        let sm = SyncStateMachine::new();
        assert_eq!(sm.state(), SyncState::Disconnected);
        assert_eq!(sm.retry_count(), 0);
    }

    #[test]
    fn test_valid_transitions() {
        let mut sm = SyncStateMachine::new();

        // Disconnected → Connecting
        sm.start_connecting();
        assert_eq!(sm.state(), SyncState::Connecting);

        // Connecting → Syncing
        sm.start_syncing();
        assert_eq!(sm.state(), SyncState::Syncing);

        // Syncing → Synced
        sm.mark_synced();
        assert_eq!(sm.state(), SyncState::Synced);
        assert_eq!(sm.retry_count(), 0);
    }

    #[test]
    fn test_error_transition() {
        let mut sm = SyncStateMachine::new();

        sm.start_connecting();
        sm.mark_error();

        assert_eq!(sm.state(), SyncState::Error);
        assert_eq!(sm.retry_count(), 1);
    }

    #[test]
    fn test_retry_from_error() {
        let mut sm = SyncStateMachine::new();

        sm.start_connecting();
        sm.mark_error();
        assert_eq!(sm.retry_count(), 1);

        // Error → Connecting (retry)
        sm.start_connecting();
        assert_eq!(sm.state(), SyncState::Connecting);
        assert_eq!(sm.retry_count(), 1); // Retry count preserved
    }

    #[test]
    fn test_disconnect() {
        let mut sm = SyncStateMachine::new();

        sm.start_connecting();
        sm.start_syncing();
        sm.disconnect();

        assert_eq!(sm.state(), SyncState::Disconnected);
    }

    #[test]
    fn test_invalid_transitions() {
        let mut sm = SyncStateMachine::new();

        // Can't go directly to Syncing from Disconnected
        sm.start_syncing();
        assert_eq!(sm.state(), SyncState::Disconnected);

        // Can't go directly to Synced from Disconnected
        sm.mark_synced();
        assert_eq!(sm.state(), SyncState::Disconnected);
    }

    #[test]
    fn test_time_in_state() {
        let sm = SyncStateMachine::new();
        sleep(Duration::from_millis(100));

        let elapsed = sm.time_in_state();
        assert!(elapsed >= Duration::from_millis(100));
        assert!(elapsed < Duration::from_millis(200));
    }

    #[test]
    fn test_backoff_duration() {
        let mut sm = SyncStateMachine::new();

        // First retry: ~1s
        sm.mark_error();
        let backoff = sm.backoff_duration();
        assert_eq!(backoff, Duration::from_secs(1));

        // Second retry: ~2s
        sm.mark_error();
        let backoff = sm.backoff_duration();
        assert_eq!(backoff, Duration::from_secs(2));

        // Third retry: ~4s
        sm.mark_error();
        let backoff = sm.backoff_duration();
        assert_eq!(backoff, Duration::from_secs(4));

        // Fourth retry: ~8s
        sm.mark_error();
        let backoff = sm.backoff_duration();
        assert_eq!(backoff, Duration::from_secs(8));
    }

    #[test]
    fn test_should_retry() {
        let mut sm = SyncStateMachine::new();

        // Not in error state
        assert!(!sm.should_retry());

        // Error state, retry count < 10
        sm.mark_error();
        assert!(sm.should_retry());

        // Max retries exceeded
        for _ in 0..10 {
            sm.mark_error();
        }
        assert!(!sm.should_retry());
    }

    #[test]
    fn test_retry_count_reset_on_success() {
        let mut sm = SyncStateMachine::new();

        // Accumulate errors
        sm.start_connecting();
        sm.mark_error();
        sm.mark_error();
        assert_eq!(sm.retry_count(), 2);

        // Successful sync resets retry count
        sm.start_connecting();
        sm.start_syncing();
        sm.mark_synced();
        assert_eq!(sm.retry_count(), 0);
    }
}
