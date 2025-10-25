#!/bin/bash

REM="./target/release/rem --db-path test-db"

echo "Testing different SQL query patterns..."
echo ""

echo "1. Equality (rating = 5.0):"
$REM query "SELECT name, rating FROM articles WHERE rating = 5.0 LIMIT 3"
echo ""

echo "2. Not equal (rating != 5.0):"
$REM query "SELECT name, rating FROM articles WHERE rating != 5.0 LIMIT 3"
echo ""

echo "3. Less than (rating < 2.0):"
$REM query "SELECT name, rating FROM articles WHERE rating < 2.0 LIMIT 3"
echo ""

echo "4. Greater than (rating > 4.5):"
$REM query "SELECT name, rating FROM articles WHERE rating > 4.5 LIMIT 3"
echo ""

echo "5. AND operator (category='rust' AND rating > 4.0):"
$REM query "SELECT name, category, rating FROM articles WHERE category = 'rust' AND rating > 4.0 LIMIT 3"
echo ""

echo "6. OR operator (category='python' OR category='rust'):"
$REM query "SELECT name, category FROM articles WHERE category = 'python' OR category = 'rust' LIMIT 5"
echo ""

echo "7. ORDER BY ASC:"
$REM query "SELECT name, views FROM articles ORDER BY views ASC LIMIT 5"
echo ""

echo "8. ORDER BY DESC:"
$REM query "SELECT name, views FROM articles ORDER BY views DESC LIMIT 5"
echo ""

echo "9. Multiple ORDER BY:"
$REM query "SELECT name, category, rating FROM articles ORDER BY category ASC, rating DESC LIMIT 8"
echo ""

echo "10. Complex query (WHERE + ORDER BY + LIMIT):"
$REM query "SELECT name, category, views, rating FROM articles WHERE views > 5000 AND rating > 3.0 ORDER BY rating DESC LIMIT 5"
