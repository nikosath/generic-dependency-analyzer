#!/usr/bin/env bash
# DEPRECATED: Use java-dep-graph.py instead.

# Simple concise logger (writes to stderr)
log() { printf '%s\n' "$*" >&2; }

# Print usage/help and parse optional args
usage() {
    cat <<'USAGE'
Usage: java-dep-graph.sh [ROOT_DIR]

Generates a Graphviz DOT of Java package -> import dependencies.

Arguments:
    ROOT_DIR   Optional path to search for Java files (default: current directory)

Requires: rg, awk, xargs, sort, uniq

Examples:
    java-dep-graph.sh              # scan current directory
    java-dep-graph.sh path/to/project
    java-dep-graph.sh path/to/project MyClass      # list imports from MyClass.java
    java-dep-graph.sh path/to/project com.pkg.MyClass  # list imports from fully-qualified class

Use -h or --help to show this message.
USAGE
}

# Show help and exit
if [ "${1}" = "-h" ] || [ "${1}" = "--help" ]; then
    usage
    exit 0
fi

# Root directory to search (default to current directory)
ROOT_DIR="${1:-.}"
# Optional target class (simple or fully-qualified). If provided the script
# will list the imports used by that class and exit (or show dependants with --reverse).
TARGET_CLASS=""

# Parse args for optional flags and positional ROOT_DIR/TARGET_CLASS
REVERSE=0
LEVELS=0
args=()
next_is_level=0
for a in "$@"; do
    case "$a" in
        --reverse)
            REVERSE=1
            ;;
        --levels=*)
            LEVELS="${a#--levels=}"
            ;;
        --levels)
            next_is_level=1
            ;;
        *)
            if [ "$next_is_level" -eq 1 ]; then
                LEVELS="$a"
                next_is_level=0
            else
                args+=("$a")
            fi
            ;;
    esac
done
ROOT_DIR="${args[0]:-.}"
TARGET_CLASS="${args[1]:-}"

# Ensure LEVELS is numeric (0 means unlimited)
if ! echo "$LEVELS" | grep -Eq '^[0-9]+$'; then
    log "Error: --levels expects a non-negative integer"
    exit 1
fi

# Check that the requested root directory exists
if [ ! -d "$ROOT_DIR" ]; then
    log "Error: directory '$ROOT_DIR' does not exist."
    exit 1
fi

# Locate configuration: prefer CWD config, fallback to script-dir config
SCRIPT_DIR=$(cd "$(dirname "$0")" >/dev/null 2>&1 && pwd || echo "")
CONFIG_FILE="${PWD}/java-dep-graph.conf"
if [ ! -f "$CONFIG_FILE" ] && [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/java-dep-graph.conf" ]; then
    CONFIG_FILE="$SCRIPT_DIR/java-dep-graph.conf"
fi

# Load whitelist/blacklist regexes from config if present
whitelist_regex=""
blacklist_regex=""
if [ -f "$CONFIG_FILE" ]; then
    while IFS= read -r _line; do
        # strip inline comments and surrounding whitespace
        line="${_line%%#*}"
        line="$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        case "$line" in
            whitelist_regex=*) whitelist_regex="${line#whitelist_regex=}" ;;
            blacklist_regex=*) blacklist_regex="${line#blacklist_regex=}" ;;
        esac
    done < "$CONFIG_FILE"
    [ -n "$whitelist_regex" ] && log "Loaded whitelist regex: $whitelist_regex"
    [ -n "$blacklist_regex" ] && log "Loaded blacklist regex: $blacklist_regex"
fi

# Default ripgrep exclusion globs for test directories; users can adjust in code later
EXCLUDE_RG_GLOBS=( -g "!**/test/**" -g "!**/src/test/**" -g "!**/test-classes/**" )


# Reverse mode: find dependants of a target class (transitive) using ripgrep + loops
if [ -n "$TARGET_CLASS" ] && [ "$REVERSE" -eq 1 ]; then
    if [[ "$TARGET_CLASS" == *.* ]]; then
        target_fqn="$TARGET_CLASS"
    else
        target_cls="$TARGET_CLASS"
        mapfile -t candidates < <(rg --files "${EXCLUDE_RG_GLOBS[@]}" -g "**/${target_cls}.java" "$ROOT_DIR" 2>/dev/null || true)
        if [ "${#candidates[@]}" -eq 0 ]; then
            log "Error: class file ${target_cls}.java not found under '$ROOT_DIR'."
            exit 1
        fi
        selected="${candidates[0]}"
        pkgline=$(awk '/^package /{gsub(";", "", $2); print $2; exit}' "$selected" 2>/dev/null || true)
        if [ -z "$pkgline" ]; then
            log "Error: could not determine package for $selected"
            exit 1
        fi
        target_fqn="$pkgline.$target_cls"
    fi

    log "Searching for dependants (transitively) of $target_fqn under $ROOT_DIR"

    seen_tmp=$(mktemp /tmp/java-dep-seen.XXXXXX)
    frontier_tmp=$(mktemp /tmp/java-dep-front.XXXXXX)
    next_tmp=$(mktemp /tmp/java-dep-next.XXXXXX)

    >"$seen_tmp"
    echo "$target_fqn" >>"$seen_tmp"
    echo "$target_fqn" >"$frontier_tmp"

    level=0
    while [ -s "$frontier_tmp" ] && { [ "$LEVELS" -eq 0 ] || [ "$level" -lt "$LEVELS" ]; }; do
        level=$((level+1))
        >"$next_tmp"
        while IFS= read -r cur; do
            cur_pkg="${cur%.*}"
            mapfile -d '' -t matches < <(rg -0 "${EXCLUDE_RG_GLOBS[@]}" --files-with-matches -F -g "*.java" -e "import ${cur};" -e "import ${cur_pkg}.*;" "$ROOT_DIR" 2>/dev/null || true)
            for f in "${matches[@]}"; do
                case "$f" in
                    *"/test/"*|*"\\test\\"*|*"/src/test/"*|*"\\src\\test\\"*) continue ;;
                esac
                pkgline=$(awk '/^package /{gsub(";","", $2); print $2; exit}' "$f" 2>/dev/null || true)
                cls=$(basename "$f" .java)
                if [ -n "$pkgline" ]; then
                    dep="$pkgline.$cls"
                else
                    dep="$cls"
                fi
                if grep -F -x -q "$dep" "$seen_tmp"; then
                    continue
                fi
                skip=0
                if [ -n "$whitelist_regex" ]; then
                    echo "$dep" | grep -E -q "$whitelist_regex" || skip=1
                fi
                if [ "$skip" -eq 0 ] && [ -n "$blacklist_regex" ]; then
                    echo "$dep" | grep -E -q "$blacklist_regex" && skip=1
                fi
                if [ "$skip" -eq 0 ]; then
                    echo "$dep" >> "$seen_tmp"
                    echo "$dep" >> "$next_tmp"
                fi
            done
        done < "$frontier_tmp"
        mv "$next_tmp" "$frontier_tmp"
    done

    results_tmp=$(mktemp /tmp/java-dep-results.XXXXXX)
    sort -u "$seen_tmp" | grep -F -v "$target_fqn" > "$results_tmp" || true
    count=$(wc -l < "$results_tmp" 2>/dev/null || true)
    echo "Dependants found: ${count:-0}"
    cat "$results_tmp"
    rm -f "$results_tmp" "$seen_tmp" "$frontier_tmp" "$next_tmp" || true
    exit 0
fi

# If a target class was provided, find its file and print its imports (filtered)
if [ -n "$TARGET_CLASS" ]; then
    # derive simple class name and optional package
    if [[ "$TARGET_CLASS" == *.* ]]; then
        target_pkg=${TARGET_CLASS%.*}
        target_cls=${TARGET_CLASS##*.}
    else
        target_pkg=""
        target_cls="$TARGET_CLASS"
    fi

    # find candidate files by basename
    mapfile -t candidates < <(rg --files "${EXCLUDE_RG_GLOBS[@]}" -g "**/${target_cls}.java" "$ROOT_DIR" 2>/dev/null || true)
    if [ "${#candidates[@]}" -eq 0 ]; then
        log "Error: class file ${target_cls}.java not found under '$ROOT_DIR'."
        exit 1
    fi

    # if package specified, prefer files whose package matches
    selected=""
    if [ -n "$target_pkg" ]; then
        for f in "${candidates[@]}"; do
            pkgline=$(awk '/^package /{gsub(";", "", $2); print $2; exit}' "$f" 2>/dev/null || true)
            if [ "$pkgline" = "$target_pkg" ]; then
                selected="$f"
                break
            fi
        done
    fi
    # fallback to first candidate
    if [ -z "$selected" ]; then
        selected="${candidates[0]}"
    fi

    log "Inspecting imports in: $selected"
    # extract imports, apply whitelist/blacklist, print unique
    awk '/^import /{gsub(";", "", $2); print $2}' "$selected" | {
        if [ -n "$whitelist_regex" ]; then
            grep -E "$whitelist_regex" || true
        else
            cat
        fi
    } | {
        if [ -n "$blacklist_regex" ]; then
            grep -v -E "$blacklist_regex" || true
        else
            cat
        fi
    } | sort -u

    exit 0
fi

# Check required tools are available before proceeding
required_cmds=(rg awk xargs sort uniq)
missing=
for cmd in "${required_cmds[@]}"; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "Error: required command '$cmd' not found in PATH." >&2
        missing=1
    fi
done
if [ -n "${missing}" ]; then
    echo "Please install the missing tools and re-run the script." >&2
    exit 1
fi

# 1. Use ripgrep to find all Java files fast
# 2. Use awk to parse 'package' and 'import' lines
# 3. Output Graphviz DOT format

echo "digraph Dependencies {"
echo "  node [shape=box, style=filled, color=\"#E8E8E8\"];"

# Check for Java files first (count); print explicit message if none
java_count=$(rg --files "${EXCLUDE_RG_GLOBS[@]}" -g "*.java" "$ROOT_DIR" 2>/dev/null | wc -l || true)
if [ "${java_count:-0}" -eq 0 ]; then
    log "No Java files found in '$ROOT_DIR'."
    echo "  // No Java files found"
    echo "}"
    exit 0
fi

# Use null-separated paths to safely handle spaces; reset package state per file

# Pass the exclude regex into awk and filter imports that match it
rg -0 "${EXCLUDE_RG_GLOBS[@]}" --files -g "*.java" "$ROOT_DIR" | xargs -0 awk -v whitelist="$whitelist_regex" -v blacklist="$blacklist_regex" '
FNR==1 { current_package = "" }
    /^package / {
        gsub(";", "", $2);
        current_package = $2;
    }
    /^import / {
        gsub(";", "", $2);
        imported = $2;
        if (current_package != "") {
            include = 1
            if (whitelist != "" && !(imported ~ whitelist)) include = 0
            if (blacklist != "" && (imported ~ blacklist)) include = 0
            if (include) print "  \"" current_package "\" -> \"" imported "\";"
        }
    }
' | sort | uniq

echo "}"