# ISSUE-007: Comparable verification evidence across languages

A specification must not look satisfied when its implementation check was
skipped, a sibling case failed, or only an independently written model passed.
Keep one requirement ID across backends and admit evidence from real execution
in each native runner. Avoid coupling project tests to a portable AST or test
runner. Publish diagnostics as data so CI can distinguish missing, inconclusive
and failed checks.
