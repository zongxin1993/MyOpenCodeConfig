# Supported adapter scope
Inputs: one syntax pattern, one of rust/python/typescript/tsx/javascript, and 1..64 explicit text source files below 1MiB each in the current linked worktree. The host checks native read permissions for every file, feeds checked text to ast-grep stdin, and returns up to 100 matches with 1-based source line/column. Match snippets may be truncated; inspect the actual source for complete context.

The adapter does not accept YAML rules, configuration files, custom grammars or rewriting. For advanced rule design, consult the official documentation separately; do not pass unsupported fields to this tool.

Docs: https://ast-grep.github.io/guide/pattern-syntax.html
