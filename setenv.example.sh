# Guard: must be sourced, not executed
# Works in bash, zsh, dash, sh
if [ -n "$ZSH_EVAL_CONTEXT" ]; then
    case "$ZSH_EVAL_CONTEXT" in *:file) ;; *) echo "ERROR: source this file, don't execute it: . ./setenv.sh" >&2; exit 1 ;; esac
elif [ -n "$BASH_VERSION" ]; then
    (return 0 2>/dev/null) || { echo "ERROR: source this file, don't execute it: . ./setenv.sh" >&2; exit 1; }
else
    case "$0" in */setenv.sh) echo "ERROR: source this file, don't execute it: . ./setenv.sh" >&2; exit 1 ;; esac
fi

# Required: Confluence REST API base URL
export CONFLUENCE_HOST="https://your-confluence.example.com/confluence/rest/api"

# Required: Personal Access Token for Confluence
export CONFLUENCE_TOKEN="your-token"

# Optional: Separate integration Confluence instance (defaults to CONFLUENCE_HOST)
# export CONFLUENCE_INT_HOST="https://your-confluence-int.example.com/confluence/rest/api"

# Optional: Token for integration instance (prompted interactively if unset)
# export CONFLUENCE_INT_TOKEN="your-int-token"

# Required: Confluence space key to sync into
export CONFLUENCE_SPACE="MYSPACE"

# uv wrapper: auto-run osv-scanner after lockfile-changing commands
uv() {
  command uv "$@"
  local rc=$?
  if [[ $rc -eq 0 ]]; then
    case "$1" in
      lock|add|remove|sync)
        echo "🔍 Running osv-scanner..."
        pre-commit run osv-scanner --all-files
        ;;
    esac
  fi
  return $rc
}
