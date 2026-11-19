# Concurrency
Identify the state owner, transaction boundary and actual thread/task crossing. Read Send/Sync diagnostics at their origin. Check lock scope and cancellation/failure paths before adding synchronization. Compile success alone does not establish recovery or race correctness; run the project's required concurrency/recovery tests. Do not parallelize database scenarios that share mutable state without an approved isolation mechanism.
Source: https://doc.rust-lang.org/book/ch16-00-concurrency.html
