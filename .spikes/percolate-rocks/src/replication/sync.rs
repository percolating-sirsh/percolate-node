//! Sync state machine for catchup logic.

use crate::types::Result;

/// Sync state for replica catchup.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum SyncState {
    Disconnected,
    Connecting,
    Syncing,
    Synced,
    Error,
}

/// State machine for managing replication sync.
pub struct SyncStateMachine {
    state: SyncState,
}

impl SyncStateMachine {
    /// Create new sync state machine.
    pub fn new() -> Self {
        todo!("Implement SyncStateMachine::new")
    }

    /// Get current state.
    pub fn state(&self) -> SyncState {
        self.state
    }

    /// Transition to connecting state.
    pub fn start_connecting(&mut self) {
        todo!("Implement SyncStateMachine::start_connecting")
    }

    /// Transition to syncing state.
    pub fn start_syncing(&mut self) {
        todo!("Implement SyncStateMachine::start_syncing")
    }

    /// Transition to synced state.
    pub fn mark_synced(&mut self) {
        todo!("Implement SyncStateMachine::mark_synced")
    }

    /// Transition to error state.
    pub fn mark_error(&mut self) {
        todo!("Implement SyncStateMachine::mark_error")
    }

    /// Transition to disconnected state.
    pub fn disconnect(&mut self) {
        todo!("Implement SyncStateMachine::disconnect")
    }
}
