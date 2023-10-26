from gitlint.git import GitCommit
from gitlint.rules import CommitMessageTitle, LineRule, RuleViolation

# Word list from https://github.com/m1foley/fit-commit
# Copyright (c) 2015 Mike Foley
# License: MIT
# Ref: fit_commit/validators/tense.rb
TENSE_DATA = [
    (["adds", "adding", "added"], "add"),
    (["allows", "allowing", "allowed"], "allow"),
    (["amends", "amending", "amended"], "amend"),
    (["bumps", "bumping", "bumped"], "bump"),
    (["calculates", "calculating", "calculated"], "calculate"),
    (["changes", "changing", "changed"], "change"),
    (["cleans", "cleaning", "cleaned"], "clean"),
    (["commits", "committing", "committed"], "commit"),
    (["configures"], "configure"),
    (["corrects", "correcting", "corrected"], "correct"),
    (["creates", "creating", "created"], "create"),
    (["darkens", "darkening", "darkened"], "darken"),
    (["disables", "disabling", "disabled"], "disable"),
    (["displays", "displaying", "displayed"], "display"),
    (["documents", "documenting", "documented"], "document"),
    (["drys", "drying", "dried"], "dry"),
    (["ends", "ending", "ended"], "end"),
    (["enforces", "enforcing", "enforced"], "enforce"),
    (["enqueues", "enqueuing", "enqueued"], "enqueue"),
    (["extracts", "extracting", "extracted"], "extract"),
    (["finishes", "finishing", "finished"], "finish"),
    (["fixes", "fixing", "fixed"], "fix"),
    (["formats", "formatting", "formatted"], "format"),
    (["guards", "guarding", "guarded"], "guard"),
    (["handles", "handling", "handled"], "handle"),
    (["hides", "hiding", "hid"], "hide"),
    (["increases", "increasing", "increased"], "increase"),
    (["ignores", "ignoring", "ignored"], "ignore"),
    (["implements", "implementing", "implemented"], "implement"),
    (["improves", "improving", "improved"], "improve"),
    (["keeps", "keeping", "kept"], "keep"),
    (["kills", "killing", "killed"], "kill"),
    (["makes", "making", "made"], "make"),
    (["merges", "merging", "merged"], "merge"),
    (["moves", "moving", "moved"], "move"),
    (["permits", "permitting", "permitted"], "permit"),
    (["prevents", "preventing", "prevented"], "prevent"),
    (["pushes", "pushing", "pushed"], "push"),
    (["rebases", "rebasing", "rebased"], "rebase"),
    (["refactors", "refactoring", "refactored"], "refactor"),
    (["removes", "removing", "removed"], "remove"),
    (["renames", "renaming", "renamed"], "rename"),
    (["reorders", "reordering", "reordered"], "reorder"),
    (["replaces", "replacing", "replaced"], "replace"),
    (["requires", "requiring", "required"], "require"),
    (["restores", "restoring", "restored"], "restore"),
    (["sends", "sending", "sent"], "send"),
    (["sets", "setting"], "set"),
    (["separates", "separating", "separated"], "separate"),
    (["shows", "showing", "showed"], "show"),
    (["simplifies", "simplifying", "simplified"], "simplify"),
    (["skips", "skipping", "skipped"], "skip"),
    (["sorts", "sorting"], "sort"),
    (["speeds", "speeding", "sped"], "speed"),
    (["starts", "starting", "started"], "start"),
    (["supports", "supporting", "supported"], "support"),
    (["takes", "taking", "took"], "take"),
    (["testing", "tested"], "test"),  # "tests" excluded to reduce false negatives
    (["truncates", "truncating", "truncated"], "truncate"),
    (["updates", "updating", "updated"], "update"),
    (["uses", "using", "used"], "use"),
]

TENSE_CORRECTIONS = {word: imperative for words, imperative in TENSE_DATA for word in words}


# Code from https://github.com/zulip/zulip
# License: Apache
# Ref: tools/lib/gitlint_rules.py
class ImperativeMood(LineRule):
    """Rule to enforce imperative mood in the commit message title.

    This is done by checking if the first word is in `TENSE_CORRECTIONS`, if so
    show the word in the correct mood.

    """

    name = "title-imperative-mood"
    id = "Z1"
    target = CommitMessageTitle

    error_msg = (
        "The first word in commit title should be in imperative mood "
        '("{word}" -> "{imperative}"): "{title}"'
    )

    def validate(self, line: str, commit: GitCommit) -> list[RuleViolation]:
        violations = []

        # Ignore the section tag (ie `<section tag>: <message body>.`)
        words = line.split(": ", 1)[-1].split()
        first_word = words[0].lower()

        if first_word in TENSE_CORRECTIONS:
            imperative = TENSE_CORRECTIONS[first_word]
            violation = RuleViolation(
                self.id,
                self.error_msg.format(
                    word=first_word,
                    imperative=imperative,
                    title=commit.message.title,
                ),
            )

            violations.append(violation)

        return violations


class FeatureNamePrefix(LineRule):
    """Rule to enforce correct feature names as title prefixes."""

    name = "title-check-prefix"
    id = "Z2"
    target = CommitMessageTitle

    error_identifier = (
        "The prefix in commit title should a valid identifier (only [a-z-_])"
        '("{prefix}"): "{title}"'
    )
    error_conventional = (
        "The prefix in commit title should a feature name, not a conventional commit prefix "
        '("{prefix}"): "{title}"'
    )
    conventional_commit_prefixes = {
        "build",
        "chore",
        "docs",
        "feat",
        "fix",
        "perf",
        "refactor",
        "revert",
        "style",
    }

    def validate(self, line: str, commit: GitCommit) -> list[RuleViolation]:
        violations = []

        prefix = line.split(": ", 1)[0].lower()
        if not prefix.replace("-", "_").isidentifier():
            violation = RuleViolation(
                self.id,
                self.error_identifier.format(prefix=prefix, title=line),
            )
            violations.append(violation)
        elif prefix in self.conventional_commit_prefixes:
            violation = RuleViolation(
                self.id,
                self.error_conventional.format(prefix=prefix, title=line),
            )
            violations.append(violation)

        return violations
