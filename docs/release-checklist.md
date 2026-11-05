# Release checklist

Every JSR-PC release goes through these steps, in this order. The first
release comes after M7 (docs/MILESTONES.md); until then this file holds the
gate, which known-bugs.md uses now, and the shape of a release. Its steps are
written out in full, with how a release is named, before the first one.

The maintainer's shared folder, outside the repository, holds known-bugs.md
and `release-prep/`: the roadmap and each release's backlog. Each backlog's
last row, Release, says which step the release has reached.

## What a release is

A public release is source: a tag on `main`, from which a player builds
JSR-PC with their own Steam copy of the game, in one command on each OS
(M7). It carries no game files, no generated code, and no build with the
game's code compiled in. Packaged builds with compiled game code go only to
the maintainer's own test devices.

## The gate

No release ships with an open critical bug, hotfixes included. A bug is
critical when, on Windows or Linux, it stops the game starting, freezes,
hangs or crashes it, loses saves or settings, or stops a player progressing,
however rarely it happens.

- A critical bug is fixed and tested before the release build (step 7). One
  found in testing (step 8) stops the release until it's fixed.
- The gate has no waiver. The maintainer can decide that a bug isn't
  critical, with the reason written in known-bugs.md, but not ship one that
  is.
- A bug the original exe has too is marked "original" in known-bugs.md. It is
  critical only if JSR-PC makes it worse, and fixing it is a feature the
  maintainer decides on.
- The one exception is a hotfix that fixes a critical bug. It can ship while
  other critical bugs from the release it replaces are still open, if it adds
  none and lists them as known issues.

## The steps, in outline

1. **Backlog closed:** every item is done, or moved to a later release with
   the maintainer's OK.
2. **Switches retired:** every switch that turns a fix back to its old
   behaviour, from a release already out, is removed.
3. **Main ready:** the latest `origin/main`, with no unpushed commits from
   elsewhere and a clean tree.
4. **Known bugs current:** what this release fixed, anything new, and whether
   each open bug is critical. Its open bugs become the release's known
   issues.
5. **Rules review:** everything since the last release, checked against the
   project's rules. It looks for game files, generated code, game data or
   instruction text in the repo, session links in commit messages, band-aid
   fixes, address lists and sleeps. It checks that every reimplementation has
   its dual run, every override says why it isn't fixed at the source, and
   look-alike overrides (the same kind of instruction, or the same symptom)
   are fixed in the lifter or runtime instead. Code findings are fixed now,
   each in its own commit.
6. **Docs:** the README and docs/ checked against the release, with the
   credit to pcrecomp and Ned Heller, and "bring your own Steam copy".
7. **Release build:** from the release commit, on a fresh clone, with the
   game files verified and the lift made fresh, on each OS, as a player would
   build it. Every number matches `data/baseline.json`.
8. **Test:** the release's test checklist on both devices. If anything fails,
   it is fixed, the fix gets its own rules check, and the release is built
   again (step 7).
9. **Go-ahead:** the maintainer approves publishing, with every step passed
   and no open critical bug.
10. **Push and tag:** push `main`, then publish the release on GitHub with its
    tag on the release commit. It has no files attached but the source.
11. **Check the release:** the tag is on the release commit, and a fresh clone
    of it builds as step 7 did.
12. **Archive and move on:** a source backup of the repository, the backlog
    marked shipped, and the roadmap pointing at the next release.

## If a release is broken

A published tag is never moved. The fix goes in the next release, and until
then the release text lists the problem as a known issue. A hotfix, on the
maintainer's say-so, ships the fix straight away. It still passes the gate.
