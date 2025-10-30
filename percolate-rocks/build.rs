fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Replication enabled for v0.3.0
    // Protobuf compilation now active

    #[cfg(feature = "python")]
    {
        tonic_build::configure()
            .build_server(true)
            .build_client(true)
            .compile_protos(&["proto/replication.proto"], &["proto"])?;
    }

    Ok(())
}
