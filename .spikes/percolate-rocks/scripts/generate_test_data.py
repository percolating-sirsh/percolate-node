#!/usr/bin/env python3
"""Generate test data for REM database testing.

Creates JSONL files with realistic content for testing semantic search,
SQL queries, and graph traversal.
"""

import json
import random
from datetime import datetime, timedelta

# Sample content for articles
RUST_CONTENT = [
    "Rust is a systems programming language that runs blazingly fast, prevents segfaults, and guarantees thread safety. It achieves memory safety without garbage collection.",
    "The Rust ownership system is a set of rules that the compiler checks at compile time. It ensures memory safety and prevents data races in concurrent code.",
    "Async programming in Rust uses the async/await syntax and the tokio runtime for building scalable network applications.",
    "Rust's type system and ownership model guarantee memory safety and thread safety without a garbage collector.",
    "Building command-line tools in Rust is straightforward with crates like clap and structopt for argument parsing.",
]

PYTHON_CONTENT = [
    "Python is a high-level, interpreted programming language known for its simplicity and readability. It's widely used in data science and web development.",
    "Data analysis in Python uses libraries like pandas, numpy, and matplotlib to process and visualize data efficiently.",
    "Web frameworks in Python include Django for full-featured applications and Flask for microservices and APIs.",
    "Python's dynamic typing and extensive standard library make it ideal for rapid prototyping and scripting tasks.",
    "Machine learning in Python leverages frameworks like scikit-learn, TensorFlow, and PyTorch for building intelligent applications.",
]

DATABASE_CONTENT = [
    "RocksDB is an embeddable persistent key-value store optimized for fast storage. It's based on LevelDB with performance enhancements.",
    "Vector databases use HNSW (Hierarchical Navigable Small World) graphs for approximate nearest neighbor search in high-dimensional spaces.",
    "SQL databases provide ACID guarantees for transactional workloads, while NoSQL databases trade consistency for availability and partition tolerance.",
    "Graph databases like Neo4j excel at traversing relationships, making them ideal for social networks and recommendation systems.",
    "Document databases store data in JSON-like formats, providing flexible schemas for rapidly evolving applications.",
]

CATEGORIES = {
    "rust": RUST_CONTENT,
    "python": PYTHON_CONTENT,
    "database": DATABASE_CONTENT,
}

def generate_articles(num_articles=100):
    """Generate article test data."""
    articles = []
    categories = list(CATEGORIES.keys())

    for i in range(num_articles):
        category = random.choice(categories)
        content = random.choice(CATEGORIES[category])

        created_date = datetime.now() - timedelta(days=random.randint(0, 365))

        article = {
            "name": f"{category.title()} Tutorial {i+1}",
            "content": content,
            "category": category,
            "author": random.choice(["alice", "bob", "charlie", "diana"]),
            "views": random.randint(10, 10000),
            "rating": round(random.uniform(1.0, 5.0), 1),
            "created_at": created_date.isoformat() + "Z",  # Add UTC timezone
            "tags": random.sample(["tutorial", "beginner", "advanced", "performance", "best-practices"], k=random.randint(1, 3))
        }

        articles.append(article)

    return articles

def generate_users(num_users=50):
    """Generate user test data."""
    users = []
    roles = ["admin", "engineer", "analyst", "designer"]
    statuses = ["active", "inactive"]

    names = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Henry"]

    for i in range(num_users):
        name = random.choice(names)
        user = {
            "name": f"{name} {i}",
            "email": f"{name.lower()}{i}@company.com",
            "age": random.randint(22, 60),
            "role": random.choice(roles),
            "status": random.choice(statuses),
            "department": random.choice(["engineering", "product", "sales", "marketing"])
        }
        users.append(user)

    return users

def write_jsonl(filename, data):
    """Write data to JSONL file."""
    with open(filename, 'w') as f:
        for item in data:
            f.write(json.dumps(item) + '\n')
    print(f"✓ Generated {filename} ({len(data)} items)")

if __name__ == "__main__":
    import sys
    import os

    # Create test-data directory if it doesn't exist
    os.makedirs("test-data", exist_ok=True)

    # Generate test data
    articles = generate_articles(100)
    users = generate_users(50)

    # Write to JSONL files
    write_jsonl("test-data/articles.jsonl", articles)
    write_jsonl("test-data/users.jsonl", users)

    print(f"\n✓ Test data generation complete!")
    print(f"  Articles: test-data/articles.jsonl (100 items)")
    print(f"  Users: test-data/users.jsonl (50 items)")
    print(f"\nUsage:")
    print(f"  rem ingest test-data/articles.jsonl --schema articles")
    print(f"  rem ingest test-data/users.jsonl --schema users")
