# Build and test reference

How JSR-PC is built, run, checked and tested, and how a change is reported.
It is written by the maintainer ("I", who never builds by hand and only runs
the builds) for whoever makes them ("you"), and goes with the project rules
and docs/project-rules.md.

Where this file and the repo's own docs or scripts disagree (README.md,
`scripts/`, `CMakeLists.txt`), trust those, and tell me about the difference.

## Test devices

- **Windows:** the desktop PC: Windows 11, i7-10700K, 32 GB DDR4, RTX 2080 Ti
  with 11 GB video memory. It is also where Windows builds are made (Where the
  work runs).
- **Linux, from M4b:** ROG Xbox Ally X: x86_64, SteamOS 3.9.5, glibc 2.43,
  Z2 Extreme with AMD Radeon Graphics, 24 GB shared memory. I test in Desktop
  Mode (KDE); ask me whether the session is X11 or Wayland. Every build must
  also work in Game Mode (gamescope).
- I only run builds you deliver. Nothing on the devices is installed or
  changed but what this file lists, unless I say so.

## Where the work runs

- **The cloud,** a thread's sandbox: the code, the diagnosis, the lift and
  `03_check.sh`, syntax checks with mingw-w64, CI's jobs run by hand, and
  every commit and push.
- **My Windows PC,** through a Remote Control session, in `Building\` in my
  JSR-PC folder there (the shared folder's `building-on-pc/README.md` gives
  its path and what's installed): the lift for Windows builds, the MSVC build,
  and running the game.

### On my PC

- **Set up:** Visual Studio Build Tools with the MSVC x86 compiler, the
  Windows SDK, and Visual Studio's own CMake and Ninja; Git for Windows, used
  by its full path; and Python 3.12 with a virtual environment in
  `Building\venv` holding the packages `scripts/01_fetch_pcrecomp.sh`
  installs. building-on-pc/README.md lists each with its version. Anything
  else, or another version, is asked for first.
- **The checkout:** `Building\src`, a clone of this repository that is only
  built from, with `core.autocrlf` off. For each build it is put at the commit
  under test, detached, with the diff under test applied, and its tree's hash
  (`git add -A`, then `git write-tree`) must be the one the cloud had. It never
  has a branch of its own, and nothing is ever committed or pushed from it.
- **Game files:** my own Steam copy, on the PC (building-on-pc/README.md
  gives the path). Script 00 copies it into `Building\src\work\input`, and
  the lift and its generated code stay in `Building\`. Neither leaves the PC,
  except the game files copied into a cloud sandbox for a lift there, where
  they stay.
- **What is written:** only `Building\`, and what the game itself writes when
  it runs (its saves and settings, Running the game). My game folder is never
  changed.
- **One job at a time:** a thread claims the PC in `PC-IN-USE.md` on the PC
  itself (building-on-pc/README.md gives its path) before its Remote Control
  session starts, and clears the claim when the session ends. Every project
  that uses the PC shares that file, so it is the only claim; read it again
  just before claiming.

### Running the game

The game may run on the PC for bring-up and tests, on these conditions:

- **Said first:** the PC-IN-USE claim says a game window will open and for how
  long, and the thread says so before it starts.
- **No input** is sent unless the task says so. A run with a time limit says
  when it ends before it starts, so a run I'm playing isn't cut short without
  warning.
- **Saves backed up first:** Steam Cloud syncs the game's saves, so a save our
  build damages reaches every device. Before any run that can write saves,
  they are copied to `Building\saves-backup\<date>\`, and never sent
  anywhere.
- **Captures** are of the game window only, never the whole desktop, and stay
  on the PC: in the build's folder, or in `Building\reference\` when kept as a
  reference for M4b and M5. The same goes for traces. The repo holds only
  what's drawn from them: counts, addresses and stage lists.
- **Logs** stay on the PC. What is copied off it holds counts and addresses
  only, with my Steam ID, account names and user paths removed.

### When the PC is busy

While another thread has the PC, work that doesn't need Windows goes on in
the sandbox: the code, the lift and its check, and a mingw-w64 i686 gcc
syntax check of changed host code, which the review pack names as a stand-in
for the MSVC build. The MSVC build, game runs and anything else that needs
Windows waits for the claim.

## Building

1. **Inputs:** `scripts/00_verify_inputs.sh <game folder>` on every new
   checkout and before every lift. A file that doesn't match
   `data/inputs.sha256` is a different build: stop and tell me.
2. **pcrecomp:** `scripts/01_fetch_pcrecomp.sh` fetches the fork at the pin.
   Set `PYTHON` to the interpreter to use (on the PC, the venv's).
3. **The lift:** `scripts/02_lift.sh`, about 6 minutes. Its counts are checked
   against `data/baseline.json`.
4. **The check:** `scripts/03_check.sh`, in the sandbox (it needs gcc): every
   generated file through `gcc -fsyntax-only`, and pcrecomp's difftest.
5. **The Windows host:** `scripts\build_win32.cmd` gives
   `build\win32\jsr-pc.exe`. `-DJSR_TRACE=ON` builds in pcrecomp's bring-up
   diagnostics; build again with `-DJSR_TRACE=OFF` afterwards, so the folder
   is back to what `main` builds.

Report each step's numbers, and the versions of Python and of the packages
pip installed, until they are pinned in the repo.

### Stand-ins

A test build may test a fix that isn't committed yet with a stand-in: a build
flag set for that one build (`CL`, `LINK`, `_LINK_`, or a CMake option), never
an edit to generated code or to a tracked file. Each stand-in is named in the
build's log and in the review pack. No committed or delivered build carries
one.

## Tests

None yet. From the first one, `tests/` holds them, with a runner that runs
each or the ones named, and this section says how to run them. Tests that
need the game's files (a dual run, anything that maps the exe) run only in a
sandbox or on the PC, and say so. Report what passed, and what didn't run and
why.

## CI

None yet. When `.github/workflows/ci.yml` exists, GitHub runs it on every push
with none of the game's files, and this section lists its jobs and how to run
each in the sandbox before a commit. Until then, the review pack's CI line
reads "CI: none yet", and the checks of docs/project-rules.md ("Before every
commit") are run by hand.

## Delivery

- **Windows:** a test build stays on the PC, in its own folder in `Building\`
  named `<date>-<commit>-<topic>`, and I run it from there.
- **Linux, from M4b:** the build is attached to your message in the thread,
  and I send its log back the same way.
- Nothing you send me carries game files or generated code, except a packaged
  build for my own devices. Public releases carry no compiled game code
  (docs/release-checklist.md).

## Test checklist (TESTING.md)

Each test build I'm to test has one, in its folder:

- **What it is:** the change in one or two lines, and the build's commit.
- **Built from:** the commit, whether the tree had uncommitted changes and its
  tree's hash, any stand-ins, the machine, the lift's numbers, and the
  toolchains.
- **Checks done here:** what ran in the sandbox and on the PC. Everything else
  is unverified.
- **What to test:** numbered steps for the areas the change's code touches,
  and nothing else. Each says exactly what to do and on which device, what I
  should see if it works, and what I'd see if it doesn't.
- **Saved runs:** none yet, so every step is tested by me.
- **Order:** the work's target platform first, until every step there passes.
  After any fix, the steps already passed that it could affect are run again.
- **What to send back:** my result for each step in the thread, and, from
  M4b, the Linux log. Windows logs are read on the PC.

## Batches

One test build can carry several items that don't change the same code, so I
test them in one go. TESTING.md and REPORT.md have a section for each item. A
failed step belongs to its item, which is fixed and built again with the rest;
if it can't be told which item a failure comes from, the next build leaves out
the items it could be. The commits are still one for each item, in the order
the build applied them, so the last commit's tree is the one I tested.

## Change report (REPORT.md)

- **Root cause:** what went wrong and the model behind it, with your
  confidence and the evidence.
- **Diagnosis:** a link to the written diagnosis, and when I agreed it.
- **History:** earlier fixes in the same code, and which of them this replaces.
- **Files touched,** with lines added and removed.
- **Why it fixes the root,** whether the same model can cause other bugs, and
  which existing helpers it reuses.
- **Regression test:** the test, and that it fails without the fix. Or why
  there isn't one, and what catches the bug again instead.
- **Overrides and reimplementations:** for each added or changed, why it
  isn't fixed at the source (an override), or its dual run (a
  reimplementation).
- **Docs** updated in the change.
- **New functions,** each with why no existing one does the job.
- **Platform impact:** Windows and Linux, saying which were built or verified
  and which were not, and from M4b, any gamescope risk.
- **What to test:** the checklist.
- **Unverified:** everything not proven here.
- **Proposed commit message.**

## Review pack

Everything I need to approve one commit, in one file: `REVIEW.md`, in a folder
for that commit in the shared folder's `review/`, with what it links to beside
it. In this order:

- **What I'm asking:** the commit, and the `origin/main` it goes on, checked
  just before writing.
- **Testing:** each step of the test list, with its device and my result, and
  every step still untested, with the device it needs.
- **The checks** (docs/project-rules.md, "Before every commit"), each with its
  result: what's staged and the audit; the diff, with its SHA-256 and whether
  it is the test build's byte for byte; the commit message; the root cause,
  its model and the regression test, or for a feature where it lives; each
  added or edited document, rendered whole; and the checks for what it
  touches, with their logs.

Nothing it needs is left to another message or file I haven't been pointed
to. In a pre-approved thread, the pack is the commit's record, written the
same way before the commit: what I'm asking becomes what is committed and
pushed, on which `origin/main`, and under which pre-approval (my words and
their time). GitHub's run on the push is added when it ends.
