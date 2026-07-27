"""A proving ground for Stella's adaptive-context lifecycle.

The claim under test: with the lifecycle enabled, performance on tasks the
agent has never seen improves as a function of experience accumulated on
different tasks. Transfer, not memorization — which is why it is only ever
measured on a held-out pool.
"""

__all__ = ["arms", "config", "epoch", "leakage", "runner", "scoreboard", "stats", "tasks"]
