# Ownership
Determine the owner and required lifetime from the actual callers. Check whether a borrow suffices, whether a value is intentionally consumed, and whether the existing interface expresses that intent. Cloning is justified only when independent values are required; shared ownership changes the lifetime model and needs domain justification. Validate the precise original error with the same compiler check and exercise affected behavior.
Source for further reading: https://doc.rust-lang.org/book/ch04-00-understanding-ownership.html
