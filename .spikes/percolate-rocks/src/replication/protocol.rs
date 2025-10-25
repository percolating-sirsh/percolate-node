//! gRPC protocol definitions for replication.
//!
//! Generated from proto/replication.proto by tonic-build.

use crate::replication::WalOperation;

// Include generated protobuf code
#[cfg(feature = "python")]
pub mod pb {
    tonic::include_proto!("replication");
}

#[cfg(feature = "python")]
pub use pb::*;

/// Convert WAL operation to protobuf.
#[cfg(feature = "python")]
pub fn to_proto_op(op: &WalOperation) -> pb::WalOperationProto {
    use pb::wal_operation_proto::Operation;

    let operation = match op {
        WalOperation::Insert { tenant_id, entity } => {
            Operation::Insert(pb::InsertOp {
                tenant_id: tenant_id.clone(),
                entity: serde_json::to_vec(entity).unwrap_or_default(),
            })
        }
        WalOperation::Update { tenant_id, entity_id, changes } => {
            Operation::Update(pb::UpdateOp {
                tenant_id: tenant_id.clone(),
                entity_id: entity_id.clone(),
                changes: serde_json::to_vec(changes).unwrap_or_default(),
            })
        }
        WalOperation::Delete { tenant_id, entity_id } => {
            Operation::Delete(pb::DeleteOp {
                tenant_id: tenant_id.clone(),
                entity_id: entity_id.clone(),
            })
        }
    };

    pb::WalOperationProto {
        operation: Some(operation),
    }
}

/// Convert protobuf to WAL operation.
#[cfg(feature = "python")]
pub fn from_proto_op(proto: pb::WalOperationProto) -> Result<WalOperation, String> {
    use pb::wal_operation_proto::Operation;

    match proto.operation {
        Some(Operation::Insert(op)) => {
            let entity = serde_json::from_slice(&op.entity)
                .map_err(|e| format!("Failed to parse entity: {}", e))?;
            Ok(WalOperation::Insert {
                tenant_id: op.tenant_id,
                entity,
            })
        }
        Some(Operation::Update(op)) => {
            let changes = serde_json::from_slice(&op.changes)
                .map_err(|e| format!("Failed to parse changes: {}", e))?;
            Ok(WalOperation::Update {
                tenant_id: op.tenant_id,
                entity_id: op.entity_id,
                changes,
            })
        }
        Some(Operation::Delete(op)) => {
            Ok(WalOperation::Delete {
                tenant_id: op.tenant_id,
                entity_id: op.entity_id,
            })
        }
        None => Err("Missing operation in protobuf".to_string()),
    }
}
