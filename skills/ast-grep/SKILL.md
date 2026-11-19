---
name: ast-grep
description: Use for syntax-aware structural search in explicit current-worktree files; text lookup stays with rg/read.
---
Managed-By: MyOpenCodeConfig execution

# Structural code search

This compact OpenCode adapter is authored here; official upstream skill/source commits are recorded in integrations/execution.lock.json, not copied as an unlicensed skill distribution.

Select the actual language and a small set of already located source files. Use execution_ast_search(pattern, language, files). A pattern represents syntax, not a regex or a semantic call graph. Use `$NAME` for one captured node and `$$$BODY` for a variable-length sequence when the language grammar allows it. Validate a complex pattern against a known example first. Zero results may mean wrong syntax or qualified paths, and never prove a symbol has no callers.

Read references/rule_reference.md for the supported adapter scope. No project-wide crawling, replacement, rewrite, arbitrary CLI options or original-checkout searches. If the tool is unavailable, use existing read/rg once; do not install dependencies in a model task or repeatedly retry. Keep required code context and return paths/line ranges to the implementer.

Official documentation: https://ast-grep.github.io/guide/pattern-syntax.html
Official skill source: https://github.com/ast-grep/agent-skill
