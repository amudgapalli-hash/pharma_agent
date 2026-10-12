# Pre-GitHub Commit Security Checklist

Complete this checklist before pushing to GitHub to ensure no sensitive information is exposed.

## ✅ Environment & Secrets

- [ ] `.env` file exists but is NOT staged for commit
  ```bash
  # Verify with:
  git status | grep .env
  # Should show: "On branch" but no .env listed
  ```

- [ ] `.env.example` is committed (without secrets)
  ```bash
  git add .env.example
  ```

- [ ] Generate strong JWT_SECRET locally
  ```bash
  python -c 'import secrets; print(secrets.token_urlsafe(32))'
  # Store this value in your .env file only
  ```

- [ ] No hardcoded API keys in source code
  ```bash
  # Check for potential keys:
  git diff --cached | grep -i "api.*key\|token\|secret"
  ```

## ✅ Database & Data Files

- [ ] No `.db`, `.sqlite`, `.sqlite3` files in staging
  ```bash
  git status | grep -E '\.(db|sqlite)'
  ```

- [ ] No database credentials in code
  ```bash
  git diff --cached | grep -i "postgres.*password\|mysql.*password"
  ```

- [ ] `pharma_audit_trail.db` is in `.gitignore`
  ```bash
  cat .gitignore | grep pharma_audit
  ```

- [ ] `postgres_data/`, `qdrant_data/`, `ollama_data/` are ignored
  ```bash
  cat .gitignore | grep -E "postgres_data|qdrant_data|ollama_data"
  ```

## ✅ Credentials & Keys

- [ ] No SSH private keys (`id_rsa`, `id_ed25519`, etc.)
  ```bash
  find . -name "id_rsa" -o -name "id_ed25519" -o -name "*.pem" | grep -v venv
  ```

- [ ] No AWS/GCP/Azure credentials
  ```bash
  git diff --cached | grep -E "AKIA|aws_secret|GCP|Azure"
  ```

- [ ] No OAuth tokens or refresh tokens
  ```bash
  git diff --cached | grep -i "refresh_token\|access_token\|oauth"
  ```

## ✅ Virtual Environment

- [ ] `venv/` directory is in `.gitignore`
  ```bash
  cat .gitignore | grep venv
  ```

- [ ] `venv/` is NOT staged
  ```bash
  git status | grep venv
  # Should show nothing
  ```

## ✅ Log Files

- [ ] No `.log` files staged
  ```bash
  git status | grep ".log"
  ```

- [ ] `logs/` directory is in `.gitignore`
  ```bash
  cat .gitignore | grep "^logs/"
  ```

## ✅ Python Cache & Build

- [ ] No `__pycache__/` directories
  ```bash
  git status | grep __pycache__
  ```

- [ ] No `*.pyc` files
  ```bash
  git status | grep ".pyc"
  ```

- [ ] `build/`, `dist/`, `*.egg-info` are ignored
  ```bash
  cat .gitignore | grep -E "^build/|^dist/|egg-info"
  ```

## ✅ IDE & Editor

- [ ] `.vscode/` is in `.gitignore`
  ```bash
  cat .gitignore | grep ".vscode"
  ```

- [ ] `.idea/` is in `.gitignore` (JetBrains)
  ```bash
  cat .gitignore | grep ".idea"
  ```

- [ ] No workspace files (`.code-workspace`)
  ```bash
  git status | grep ".code-workspace"
  ```

## ✅ Docker & Container

- [ ] `.dockerignore` file exists and is properly configured
  ```bash
  ls -la .dockerignore
  ```

- [ ] Docker volume data directories are ignored
  ```bash
  cat .gitignore | grep -E "postgres_data|qdrant_data|ollama_data"
  ```

## ✅ Security Files

- [ ] `SECURITY_GUARDRAILS.md` is committed (non-sensitive security docs)
  ```bash
  git add SECURITY_GUARDRAILS.md
  ```

- [ ] No sensitive security notes in other docs
  ```bash
  git diff --cached | grep -i "password\|secret\|api_key" | grep -v ".env.example"
  ```

## ✅ LLM & AI Project Specific

- [ ] No `.ollama` directories
  ```bash
  git status | grep ".ollama"
  ```

- [ ] No model checkpoints or weights
  ```bash
  git status | grep -E "\.(ckpt|bin|pt|pth|safetensors)$"
  ```

- [ ] `.langgraph_api/` is in `.gitignore`
  ```bash
  cat .gitignore | grep ".langgraph_api"
  ```

## ✅ Pre-Commit Hook

- [ ] Pre-commit hook is installed and working
  ```bash
  chmod +x scripts/pre-commit-hook.sh
  cp scripts/pre-commit-hook.sh .git/hooks/pre-commit
  ```

- [ ] Test the hook by attempting to commit a test secret
  ```bash
  echo "API_KEY=test123" >> test.py
  git add test.py
  git commit -m "test" # Should fail
  rm test.py
  git reset
  ```

## ✅ Documentation

- [ ] `README.md` includes security setup instructions
- [ ] `DEPLOYMENT.md` includes secrets management guide
- [ ] `.env.example` is comprehensive and documented
- [ ] Security guide references `.env.example` usage

## ✅ Final Verification

Before pushing to GitHub, run this comprehensive check:

```bash
# 1. Check for staged .env files
git diff --cached --name-only | grep -i env

# 2. Check for secrets in staged files
git diff --cached | grep -E "(password|secret|api_key|token|credential)" | head -20

# 3. List all staged files
git diff --cached --name-only

# 4. Verify .gitignore covers critical patterns
echo "Checking .gitignore:"
cat .gitignore | grep -E "^\.env$|^venv/$|^\*\.db$|^\*\.key$|^\*\.pem$"

# 5. Run security pre-commit checks
./scripts/pre-commit-hook.sh
```

## 🚨 If You Made a Mistake

If you accidentally committed sensitive data:

1. **Remove from history** (URGENT):
   ```bash
   git rm --cached .env
   git commit --amend --no-edit
   git push --force-with-lease
   ```

2. **Use BFG Repo-Cleaner** (for committed secrets):
   ```bash
   # Install: brew install bfg
   bfg --delete-files .env
   git reflog expire --expire=now --all && git gc --prune=now
   ```

3. **Rotate all secrets immediately**:
   ```bash
   # Generate new JWT_SECRET
   python -c 'import secrets; print(secrets.token_urlsafe(32))'
   # Update environment variables
   # Restart services
   ```

4. **Alert your team** if working in a shared repo

## 📋 After Each Commit

- [ ] Verify no sensitive files in remote: `git log --name-status`
- [ ] Monitor GitHub for exposed secrets (GitHub alerts)
- [ ] Review recent commits for accidental data

---

**Last Updated**: 2026-10-09
**Status**: Ready for GitHub ✅
