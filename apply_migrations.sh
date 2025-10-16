#!/bin/bash

# Script to apply database migrations to Supabase
# Usage: ./apply_migrations.sh

set -e

echo "========================================="
echo "SnSD Database Migration Script"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Please create a .env file with SUPABASE_DB_URL"
    exit 1
fi

# Load environment variables
source .env

if [ -z "$SUPABASE_DB_URL" ]; then
    echo -e "${RED}Error: SUPABASE_DB_URL not set in .env${NC}"
    echo "Example: SUPABASE_DB_URL=postgresql://postgres:[PASSWORD]@[HOST]:[PORT]/postgres"
    exit 1
fi

# Array of migration files in order
migrations=(
    "001_tenant_users.sql"
    "002_permissions.sql"
    "003_invitations.sql"
    "004_subscriptions.sql"
)

echo -e "${YELLOW}Will apply the following migrations:${NC}"
for migration in "${migrations[@]}"; do
    echo "  - $migration"
done
echo ""

read -p "Continue? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "Applying migrations..."
echo ""

for migration in "${migrations[@]}"; do
    echo -e "${YELLOW}Applying $migration...${NC}"

    if [ ! -f "migrations/$migration" ]; then
        echo -e "${RED}Error: migrations/$migration not found${NC}"
        exit 1
    fi

    if psql "$SUPABASE_DB_URL" < "migrations/$migration"; then
        echo -e "${GREEN}✓ $migration applied successfully${NC}"
    else
        echo -e "${RED}✗ Failed to apply $migration${NC}"
        exit 1
    fi
    echo ""
done

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}All migrations applied successfully!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Verify tables were created: psql \"\$SUPABASE_DB_URL\" -c '\dt'"
echo "2. Check permissions count: psql \"\$SUPABASE_DB_URL\" -c 'SELECT COUNT(*) FROM permissions;'"
echo "3. Assign default subscriptions to existing tenants (see migrations/README.md)"
echo ""
