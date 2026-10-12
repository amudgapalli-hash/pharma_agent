#!/bin/bash
# Pre-commit hook to prevent committing sensitive files
# Install: cp scripts/pre-commit-hook .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit

set -e

# Color codes
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🔐 Running security pre-commit checks...${NC}"

# Check for .env files
if git diff --cached --name-only | grep -E '\.env($|\..*$)' | grep -v '\.env\.example'; then
    echo -e "${RED}❌ ERROR: .env file detected in staging area!${NC}"
    echo -e "${RED}Sensitive data must not be committed.${NC}"
    echo -e "${YELLOW}This file should be ignored by .gitignore${NC}"
    exit 1
fi

# Check for AWS credentials
if git diff --cached -U0 | grep -E '(AKIA|aws_access_key|aws_secret_access_key)'; then
    echo -e "${RED}❌ ERROR: AWS credentials detected!${NC}"
    exit 1
fi

# Check for API keys
if git diff --cached -U0 | grep -E '(api_key|apiKey|api-key|API_KEY|token|secret|password)' | grep -v '.env.example'; then
    echo -e "${RED}⚠️  WARNING: Potential API key/secret detected${NC}"
    echo "Please verify this is not sensitive data"
    echo "To bypass this check (NOT RECOMMENDED): git commit --no-verify"
    exit 1
fi

# Check for database files
if git diff --cached --name-only | grep -E '\.(db|sqlite|sqlite3|pem|key|p12)$'; then
    echo -e "${RED}❌ ERROR: Database or key file detected!${NC}"
    exit 1
fi

# Check for private SSH/SSL keys
if git diff --cached --name-only | grep -E '(id_rsa|id_dsa|id_ecdsa|id_ed25519|\.pem|\.key|\.pfx)'; then
    echo -e "${RED}❌ ERROR: Private key file detected!${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Security checks passed!${NC}"
exit 0
