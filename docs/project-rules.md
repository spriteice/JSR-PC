# Project rules

How a change to JSR-PC is placed, written, checked and proposed. It is written
by the maintainer ("I") for whoever makes the change ("you"), and goes with the
short project rules (the project's instructions). docs/build-and-test-reference.md
covers building, running and testing, and the change report.
docs/release-checklist.md covers releases.

A rule here that names something JSR-PC doesn't have yet says so ("none
yet"), with what happens until it exists. Nothing is skipped silently: if a
rule can't be met, the review pack says which one and why.

## Before every commit

Do all of these, in one review pack (docs/build-and-test-reference.md, "Review
pack"), then wait for my approval. A pre-approved thread doesn't wait
(Pre-approved threads).

1. **What's staged.** Run `git status` and `git diff --cached --stat`, and
   confirm that nothing on the project rules' "never in the repo" list is
   staged. If .gitignore doesn't cover it, tell me.
   `python third_party/pcrecomp/tools/audit_repo.py .` reports CLEAN.
2. **The full diff.**
3. **The proposed commit message.** No Claude session links.
4. **Why.** For a fix: the root cause and the model behind it (Where code
   goes, 1), as I agreed it (Workflow, 2) or, in a pre-approved thread, as
   posted, and its regression test, or why there is none and what catches the
   bug again instead (How it's written). For a feature: where it lives in the
   code, and why that's the right place.
5. **Docs.** Each added or edited document (README, AGENTS.md, docs/) rendered
   whole as Markdown, not only its diff.
6. **The checks for what it touches,** each with its result:

   | The commit changes | Check |
   |---|---|
   | Anything | CI passes for the commit's exact tree (docs/build-and-test-reference.md, "CI"). None yet: until `.github/workflows/ci.yml` exists, the pack says "CI: none yet" and runs the checks below by hand. |
   | `tools/`, `data/`, or a script that makes the lift | `scripts/02_lift.sh` and `03_check.sh`, with every number against `data/baseline.json` |
   | `src/`, `CMakeLists.txt`, or `scripts/build_win32.cmd` | A compile with MSVC x86: CI's Windows job, or until CI exists, `scripts\build_win32.cmd` on my PC. While another thread has the PC, a mingw-w64 i686 gcc syntax check of the changed files in the sandbox stands in, and the pack says so. |
   | `tests/` or code a test covers | The tests pass (docs/build-and-test-reference.md, "Tests"). None yet: there is no `tests/` until the first test is added. |
   | The pcrecomp pin | Where code goes, 4: the lift and the check run again, and `data/baseline.json`'s diff |
   | What the game runs (anything but `docs/`, `tests/`, the function map's two files, and the top-level Markdown files) | A test build of that tree, and its test steps, on its device (docs/build-and-test-reference.md, "Test checklist") |

GitHub runs CI again on the push. A failure there is fixed in the next commit,
before anything else is pushed. A job that fails before its checks run,
because a download failed (a server down), is not the commit's failure: it is
run again once the server is back, and nothing else is pushed until it passes.

## Where code goes

Decide this first.

1. **The root cause, not the symptom.** For a bug, find the root cause and fix
   it there. A root cause has two parts: what went wrong (the race, the wrong
   value), and the model that let it happen (a host linked where the game
   expects its own memory, a handle the guest hands to a real DLL). Name both,
   and say whether the same model allows other bugs. When the model is the
   cause, the fix is to the model, however big that is: say so, and size it.
   For a feature, put it where it belongs in the code's structure, not bolted
   on where it happens to work. If the right place isn't clear, stop and ask.
2. **The right place.** Code goes in the layer that owns the behaviour:
   - **the lifter** (pcrecomp's `tools/lift`, in our fork), for how the game's
     code is turned into C;
   - **the runtime** (pcrecomp's `runtime/recomp32`, `native32` and
     `win32hle`, in our fork), for the machine model the lifted code runs on;
   - **the hosts** (`src/host_win32` for native32, `src/host_linux` for
     win32hle), for starting the game on each OS, and the imports that must
     answer for the guest there;
   - **the shims** (`src/shims`), for an import or COM interface answered the
     same way on both hosts;
   - **the renderer** (`src/render/vk`, `src/render/gl`), for drawing;
   - **game code** (`src/game`), for hand-written replacements of the game's
     own functions (Game code, below).

   Never make up in one layer for a bug in another. A host doesn't repair the
   lifter's output, a game function override doesn't stand in for a missing
   runtime or shim behaviour, and nothing outside the game sets a switch the
   game needs to work.
3. **Never edit generated files.** The lifted C in `work/gen/` is made again on
   every lift and never edited, not even for a test build (a test build's
   stand-ins are build flags only: docs/build-and-test-reference.md,
   "Stand-ins"). A lift problem is fixed in the lifter, by a named override or
   reimplementation in `src/game`, or by seeding a missed function
   (`tools/disasm/seed_from_log.py` in pcrecomp), and the lift is made again.
4. **pcrecomp, through our fork.** JSR-PC is built on
   [pcrecomp](https://github.com/sp00nznet/pcrecomp) by Ned Heller
   (sp00nznet), fetched from our fork,
   [spriteice/pcrecomp](https://github.com/spriteice/pcrecomp), at the commit
   pinned in `scripts/01_fetch_pcrecomp.sh` and never vendored.
   - A lifter change comes with a difftest case that fails without it, and a
     runtime change with a self-test. Each gets a CHANGELOG entry, as pcrecomp
     keeps them.
   - Each change stays general: it names no JSR-PC address or function, so it
     could be offered upstream. Offering one to sp00nznet/pcrecomp, or taking
     upstream's changes into the fork, is outside the project and waits for
     me.
   - A fork change reaches JSR-PC only through a pin-move commit of its own:
     `scripts/01_fetch_pcrecomp.sh`, `02_lift.sh` and `03_check.sh` run again,
     and `data/baseline.json` is updated, with its diff in the review pack.
5. **Settings.** A new feature can have a setting to turn it off. A fix gets a
   switch back to the old behaviour only while it's being tested, and that
   switch is removed by the next release. Two kinds of switch stay: build
   options for bring-up diagnostics (`-DJSR_TRACE=ON`), and the run-time
   switch back to the lifted code for each reimplementation (Game code,
   Reimplementations, 9), since neither changes what a player sees by default.
6. **Overrides.** Replacing one game function, or hooking one point in it, to
   change what it does is the right place when that function's own logic is
   the root cause: the recompiled code matches the original instructions, and
   no other function shows the same symptom. Each override is deliberate,
   named for what it does, and uses named constants for its address and any
   game offsets. Its comment says why it isn't fixed at the source, and its
   proposal says the same. If many functions misbehave for one reason, or the
   game's code is right and the runtime is wrong, fix the lifter or the
   runtime instead (1 and 2). If the original exe has the bug too, it isn't a
   port bug: it goes in known-bugs.md marked "original", and fixing it is a
   feature I decide on.
7. **A second fix in one place is a review.** Before proposing a fix, read the
   history of the code it changes (`git log -L` on the function, or `git log`
   on the file, here or in the fork). If that code already had a fix for a
   related bug, the next step is a review of the mechanism, not another fix:
   what model it implements, how that differs from what the game expects,
   what else it produced, and whether to replace it. Propose that review
   first.

## Game code

### The kinds of hand-written code

| Kind | What it is | Where |
|---|---|---|
| Shim | Answers an import or COM call for the guest | `src/host_*`, or `src/shims` when both hosts share it |
| Override | Replaces a game function, or hooks one point in it, to change what it does (Where code goes, 6) | `src/game` |
| Reimplementation | Replaces a game function with hand-written C that does exactly what the lifted function does | `src/game` |
| Seed | A missed function fed back to the lift | pcrecomp's `seed_from_log.py`; data, not code |

A reimplementation never changes behaviour. A change on top of one is an
override, in a commit of its own.

### The function map

AGENTS.md ("Naming functions") says how to add a name. These are the rules
behind it.

1. **The map** is metadata only: addresses, names, kinds and evidence, never
   instruction text. `data/function_map.tsv` is made by
   `tools/map_functions.py` from the verified exe, and never edited by hand.
   `data/names_manual.tsv` holds our own names, one row per name, each with a
   note saying what the function does that earns the name and where that was
   seen. The script merges the two. A manual name wins over a name the script
   only made up (such as an RTTI slot's `Class::vfN`); a clash with a name the
   function's own string gives stops the script, and never picks a winner.
2. **Evidence** comes from the binary (its strings, RTTI, imports and
   exports), from public documentation (such as the public names of SEGA's
   Ninja library, `nj*`), or from our own reading of what a function does.
   Never from leaked source or SDKs, symbol files we don't have, or another
   project's decompilation. Notes describe behaviour: they never quote code,
   or a string from the exe other than a name or a path.
3. **Names** the exe spells out keep its spelling (`njCnkDrawModel`,
   `AudioPlayback::OggPlay`); pcrecomp's `name_lift.py` makes the C
   identifiers at lift time. Names we give are `Area_Verb`, in CamelCase (as
   in `File_ReadAsync`). An SDK name is never given without a string or a
   match that proves it; the likely one goes in the note instead. A name
   changes freely while no code uses it; once code does, the map and the code
   change in one commit.
4. **Into the lifted C** through `name_lift.py` (`--known`). Where it falls
   short, it is extended in the fork, not copied into a second tool here.
5. **Numbers:** each commit that changes the map states its counts by kind and
   by evidence, and their change since the commit before.
6. **Columns for replacements:** the calling convention and argument count of
   a function are added to the map before it is reimplemented or overridden.

### Reimplementations

1. **What can be one.** A function whose body is its own, called by
   compiler-made code. Not an incremental-link jump, a thunk, or an entry
   point inside another function's body, nor the CRT, compiler helpers,
   exception-handling funclets, hand-written assembly, or a function that is
   entered in its middle, unless its proposal makes the case. Start at the
   leaves (functions that call nothing lifted) and work up the call graph.
2. **It takes every call.** A reimplementation replaces the function at every
   direct call, tail jump, indirect call and dispatch entry. pcrecomp's
   `recomp_lookup_manual()` sees only indirect calls and dispatch
   (`RECOMP_ICALL` and `RECOMP_ITAIL`), so until the lifter sends direct calls
   to a listed address to its replacement, a reimplementation is not
   committed. A check in its test build shows the lifted body is reached 0
   times while it is replaced.
3. **One registry.** Every reimplementation and override is one entry in one
   table, with its name, its address constant and its kind. That table is not
   a hardcoded address list (Never do): each entry is a named function.
   Nothing is hooked from anywhere else.
4. **The guest's calling rules, through one header.** Arguments come from the
   guest stack, and results go where the original puts them: eax, edx:eax, or
   the lifted x87 stack. Each function follows its calling convention from the
   map (cdecl, stdcall, thiscall or fastcall), keeps the registers it says to
   keep (ebx, esi, edi, ebp), and leaves esp as it says. All of this goes
   through helpers in one header, never written out by hand in each function.
5. **Portable by construction.** The same source builds for native32 (MSVC,
   x86, flat memory) and win32hle (gcc or clang, x86-64, memory at
   `RECOMP_MEM_BASE`).
   - A guest address is always a `uint32_t`, and guest memory is reached only
     through pcrecomp's `ADDR()` and `MEM8`, `MEM16` and `MEM32` macros, never
     by casting an address to a pointer.
   - A guest structure is a set of named offsets with accessors, or a struct
     of fixed-width fields with a `static_assert` on its size and no pointers
     in it.
   - No `long`, `size_t` or host pointer in anything the guest sees.
6. **The original's arithmetic.**
   - Game code does scalar SSE in single precision, so compute in `float`,
     with `f` constants, in the original's order.
   - No fused multiply-add: `/fp:precise` on MSVC, and `-ffp-contract=off` on
     gcc and clang.
   - Integer widths, signedness and wrap-around are as in the original.
   - Where the original uses x87, the lifted model holds a double, not 80 bits
     (pcrecomp's `recomp_types.h`), and a reimplementation matches the lifted
     model, as that's what it is compared with.
7. **The game's data stays in the game.** Tables, strings, model and level
   data, and the shader source are read from guest memory at their named
   addresses, never copied into the source. Named scalar constants, such as
   `STATUS_PENDING` or a buffer size, are fine.
8. **Proven equal, by a dual run.** A test build runs the lifted function and
   the hand-written one from the same state at each call: snapshot, run one,
   restore, run the other. It compares what comes back, the registers, the
   flags where a caller reads them, and every byte written to guest memory.
   - The report gives the number of calls compared, from how many callers, in
     which runs or scenes, and 0 mismatches.
   - A pure function also gets a unit test in `tests/` that links the real
     file.
   - The dual run is a reimplementation's regression test: one without it
     isn't committed.
9. **A switch back, kept.** Each reimplementation can be turned off at run
   time, alone or all together, so a bug can be narrowed to one function.
10. **Written as our code.** Named from the map, with a header comment giving
    the address, the original source file if known, the calling convention,
    what it does, and its dual run (calls compared, at which commit). No
    lifted C or disassembly is pasted into a comment or a commit message.
11. **Small commits.** One function per commit, or a small group that only
    makes sense together. A restructure (moving or splitting files) is its
    own commit, first.
12. **Where it lives:** `src/game/<area>/<original source file or class>.c`,
    using the map's areas. Code for one host only never goes in `src/game`.

## How it's written

In priority order:

1. **Robust:** handle the general case, not only the one I observed. Model
   what the original exe does on Windows, not what one case needs.
2. **Focused:** each commit is one change, with nothing unrelated in it.
   Restructuring that the change needs (moving code to its right place,
   splitting a file, renaming what it touches) is welcome, in a commit of its
   own before the change. A commit either restructures, with no change in
   behaviour and the checks still passing, or changes behaviour, never both.
   No drive-by renaming or reformatting elsewhere.
3. **Clean:** match the surrounding style, naming and comments.

Reuse existing functions and helpers, here and in pcrecomp. Search both
before adding any new function or tool, and justify each new one.

**Every fixed bug gets a regression test** that fails without the fix and
passes with it. If the bug can't be reached from a test in the sandbox (it
needs the game's code running, or a device), say why, and add what would catch
it again instead: an assert, a `jsr-pc:` line on stderr, or a step on the test
checklist.

**Tests link the code they test.** A test builds the real source file, never
a copy or a piece cut out of a file by text. If the code can't be linked on
its own, split it into a unit that can (2, its own commit).

**Docs change with the code.** A commit that changes what a player or a
builder sees or does updates the docs that describe it, in the same commit:
the README, AGENTS.md and docs/. known-bugs.md and the release's backlog, in
the shared folder, are kept current as the work happens, not at release.

### C in this repo

- **C17.** Our code builds with no warnings under MSVC `/W4` and under gcc and
  clang with `-Wall -Wextra`. The lifted code builds at `/W0`, as its warnings
  say nothing about ours.
- **Names:** `JSR_` for our macros and constants, `g_` for globals, snake_case
  for host functions, and the map's name for a game function.
- **No bare numbers:** every address, offset and magic value is a named
  constant, with a comment saying where it comes from.
- **Comments** say why, and where a value comes from, in sentences.
- **Platform code stays behind the host split:** `src/host_win32` is Windows
  only and `src/host_linux` Linux only; `src/shims`, `src/render` and
  `src/game` build on both.
- **Errors are loud:** a failure the game can't see goes to stderr, starting
  `jsr-pc:`, with the value. It is never swallowed.

## Never do

Stop and tell me why instead.

- Edit generated code, by hand or by script, for any build.
- Copy the game's data (tables, strings, models, the shader source) into the
  repo, or paste lifted C or disassembly into code, comments, commit
  messages or docs.
- Hardcoded address lists, or per-address special cases that hide a symptom.
  A named override or reimplementation in the registry is not one.
- Bare numbers: magic numbers, and unnamed addresses or offsets.
- Sleeps or retries that hide timing bugs.
- Make up in one layer for a bug in another (Where code goes, 2).

## Workflow

In order:

1. **Diagnose:** reproduce from my logs or a run, gather evidence, and read
   the history of the code involved (Where code goes, 7). Write the diagnosis
   down, in the work's folder in the shared folder: what was seen, the root
   cause (what went wrong and the model behind it), the evidence, your
   confidence, and what would prove it wrong.
2. **Propose** the fix at the root, sized to the cause, with the written
   diagnosis, then wait for my go-ahead before editing. If it's bigger than
   the bug looks, say why. If a player-facing bug needs something sooner, say
   what smaller step could ship first, and what replaces it later. No fix is
   committed until I've agreed the diagnosis. A test build can carry a fix
   before that, to test the diagnosis. A pre-approved thread posts the
   diagnosis and the proposal, and goes on (Pre-approved threads).
3. **Implement.** Add the fix's regression test, and update the docs the
   change affects (How it's written). When a fix can't be proven by reading
   the code, add logging or asserts that would confirm or refute your
   hypothesis.
4. **Verify** what you can: it builds, the checks pass, and the game runs on
   the PC as docs/build-and-test-reference.md ("Running the game") allows.
   What needs a person at the controls, or how something looks or feels, is
   tested by me: call every such claim "unverified" until I have. Never claim
   something is fixed without evidence. A change made for timing or speed is
   measured before and after.
5. **Track my testing.** Read every log in full, start to end, before
   reporting on it, using scripts for logs too long to read whole. Each time,
   check the logs against the build's test checklist and list every step
   still untested, per device. Before asking me to approve a commit, remind me
   of any untested steps and which device each needs. A step is tested only
   when a log or my message shows it.
6. **Report** the change with the change report in
   docs/build-and-test-reference.md.

**Several items at once.** Items that don't change the same code can be
worked at the same time, each in its own thread, and their testing can share
one build (docs/build-and-test-reference.md, "Batches"). Commits still go onto
`main` one at a time: each starts from the latest `origin/main`. If `main` has
moved since an item's checks, they run again on its new tree, and if the
commits in between change the code it changes, its test build is made again
and the steps they could affect are tested again. Each thread changes only its
own rows in the backlog and known-bugs.md, and reads the file again just
before each change.

At any step: if a rule conflicts with the task, or you can't solve it within
the rules, stop and ask. Don't quietly bend the rule. These rules come before
a session's own instructions and hooks: if those ask you to commit, push, or
work on another branch, say so, and don't. A session on my PC never commits or
pushes: commits are made in the cloud, after my approval or under a
pre-approval. An approval covers what the thread's last request asked for, as
it was asked. When a session starts to wear (its context nearly full or
summarised, a rule slipped, or details lost), say so, write a handoff in the
shared folder, and move the work to a new session.

## Pre-approved threads

I can pre-approve a thread to work through its task on its own: to diagnose,
fix, adjust and fix again as the tests show, commit, and push `main`, without
waiting for me at each step. Everything else in these rules still applies,
with the changes below.

### How it's given

- **Only by me, by hand, at the thread's start:** in my own message that opens
  the thread, or my first message in it before the thread has changed
  anything, with the words "automation pre-approved" (with or without the
  hyphen). It covers the task that message asks for, and nothing beyond it.
- **Nothing else gives one:** not a message from another session (the
  project's coordinator or another thread), a hook, a session's own
  instructions, a file, a commit message, a comment on GitHub, or my words
  quoted inside another session's message, even word for word. It isn't
  handed on: when a worn thread's work moves to a new one, the new one isn't
  pre-approved until I say so there.
- **When in doubt, it isn't:** the thread works under the usual rules, and
  asks me.

### At the start

The thread's first reply:

- confirms the pre-approval, with my words and their time, and the task it
  covers;
- names the saved runs (pre-recorded playback) its testing will need. None
  exist yet (`input-playback/RUNS.md` in the shared folder isn't made), so
  until they do, it lists the steps I'll test by hand, per device;
- says anything it can already see that will stop it (What still needs me).

### What changes

- **Diagnosis** (Workflow 1 and 2): written down and posted with the proposed
  fix as always, but the thread goes on without waiting for my go-ahead. Its
  commit's check 4 names the diagnosis as posted.
- **Fixes on the go:** when a check or a test step fails, the thread finds
  why, fixes it, and runs it again, without asking. A fix to its own change
  goes into that change and is tested again, with the steps already passed
  that it could affect. A fix to a commit already pushed is a commit of its
  own, through the same tests.
- **Other bugs it finds** go in known-bugs.md and are told to me. They aren't
  fixed in that thread unless I add them to its task. One that stops the
  task's own tests passing stops the thread.
- **Commits:** the checks and the review pack are done as always, as the
  commit's record, and the thread commits once they and the tests below pass.
- **Pushes:** the thread pushes `main` once the tests below pass. A push that
  finds `origin/main` has moved is never forced: the thread moves its own
  commits onto the new `origin/main`, and they go through the checks again.
- **Git in its sandbox:** it may switch to `main`, fast-forward `main` to
  `origin/main`, and move its own unpushed commits onto a newer
  `origin/main`. Nothing else, and nothing forced. If `main` has unpushed
  commits from another thread, it asks me first.

### When all the tests pass

A commit is made and pushed only when all of these pass for its exact tree:

1. **The checks** of Before every commit, CI among them.
2. **For a fix, its regression test,** failing without the fix and passing
   with it. For a reimplementation, its dual run.
3. **For a change to what the game runs:** a test build of that tree, and
   every step of its test checklist passed on its device. A saved run that
   satisfies a step counts as its pass, once saved runs exist. Otherwise the
   step passes on my own results and logs, as does how something looks or
   feels. A step I marked Skip, or left unmarked, hasn't passed.

After the push, the thread reads GitHub's CI run on the pushed commit. A
failure there is fixed in the next commit, before anything else is pushed.

### What still needs me

A pre-approval never covers these. The thread stops, says why, keeps what it
hasn't pushed, and goes on only once I've answered.

- **Releases:** tags, releases, publishing, and every step of
  docs/release-checklist.md. While a release is under way, the thread commits
  but doesn't push.
- **Git beyond its own commits on `main`:** pushing anything else, a force
  push, or changing pushed history. A pushed commit I don't want is undone by
  a new commit (`git revert`), on my say.
- **The pcrecomp pin:** moving it (Where code goes, 4).
- **The project rules' "never in the repo".**
- **The rules and the checks:** the project rules, this file,
  docs/build-and-test-reference.md, docs/release-checklist.md, `.github/`,
  and `data/baseline.json`.
- **Tests made weaker:** skipping, disabling or loosening a test, or changing
  what it expects so that it passes, unless the task is that test's own fix.
- **Work beyond its task:** an item or a feature it wasn't given, another
  thread's rows, moving an item between releases, or deciding whether a bug
  is critical.
- **The decisions these rules give me:** where a fix goes, when that isn't
  clear or the fix is to a model and bigger than the task (Where code goes,
  1); a second fix in one place (Where code goes, 7); anything on the Never
  do list; and a rule that conflicts with the task.
- **Failures it can't fix:** a check or step that still fails after two
  fixes, a failure it can't explain, or one its change didn't cause.
- **Anything new installed,** on the PC or in the sandbox, or anything changed
  on a device beyond what docs/build-and-test-reference.md lists.
- **Anything sent outside the project:** a GitHub issue, comment or pull
  request, or a change to another repository.

### Records

- **The review pack** for each commit is written before the commit, as its
  record, and says under which pre-approval it was made. GitHub's run on the
  push is added when it ends.
- **The backlog row and known-bugs.md:** "automation pre-approved" when the
  work starts, with my message's time; each commit when it's made, with its
  hash and review pack; and each push when it's done, with its time and
  GitHub's run.
- **Replies:** the first one (At the start); one when a test build is ready
  for me; one for each push, with its commits, review packs and GitHub's run;
  and one each time the thread stops. Progress in between goes on the
  thread's checklist.

### When it ends

When I say so in the thread, when its task is pushed and GitHub's run on it
has passed, or when the work moves to a new thread. From then on the usual
rules apply to anything not yet pushed.

## Platforms

JSR-PC is for Windows and Linux on x86 hosts only. No other platform is built,
tested or considered.

- **Windows** (native32, MSVC x86) came first, to a working binary (M2, 4
  November 2026). It stays the reference that every later comparison is made
  against.
- **Linux** (win32hle, x86-64) leads once M3's groundwork is done. It must run
  on SteamOS: no glibc symbol newer than 2.43, and within the README's minimum
  once it has one. Builds must also work in Game Mode, under gamescope: don't
  assume a desktop window manager, mouse or keyboard, and flag any change that
  could behave differently there.
- **Renderers:** Vulkan (primary) and OpenGL 3.3 core, both on both OSes
  (docs/MILESTONES.md, M5).
- Put platform-specific code behind the host split (C in this repo).
- For every change, say which platforms you built or verified and which you
  could not.

## Documents

- The README, the documents it links to, and any release text are human
  readable first: simple and concise while holding everything relevant, in
  one consistent format.
- Docs credit pcrecomp and its author, Ned Heller (sp00nznet), for the toolkit
  JSR-PC is built on, and stay respectful of it. SEGA owns the game; docs say
  "bring your own Steam copy".
- Version names and an in-game menu's format get their own docs when JSR-PC
  first has them.
