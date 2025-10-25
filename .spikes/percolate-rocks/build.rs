fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Only compile proto files when python feature is enabled
    // (gRPC not needed for pure Rust library usage)
    #[cfg(feature = "python")]
    {
        tonic_build::configure()
            .build_server(true)
            .build_client(true)
            .compile(&["proto/replication.proto"], &["proto"])?;
    }

    Ok(())
}
