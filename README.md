# Jet Set Radio PC: pcrecomp handoff package

This is a starting kit for statically recompiling the 2013 Steam release of Jet Set Radio
into native Windows and Linux builds, with Vulkan and OpenGL renderers, using
[pcrecomp](https://github.com/sp00nznet/pcrecomp).

**No game files or generated code are included.** You need your own copy of the
game from Steam. The scripts verify it by hash and regenerate everything from it locally.

## Quickstart (Linux, Python 3.10+, gcc, git)

```bash
scripts/00_verify_inputs.sh "/path/to/steamapps/common/Jet Set Radio"
scripts/01_fetch_pcrecomp.sh     # pinned to ef3f0da
scripts/02_lift.sh               # ~6 min: analyse, recover 18,102 functions, lift to C
scripts/03_check.sh              # syntax check + pcrecomp difftest, vs data/baseline.json
```

## Read next

- `AGENTS.md`: the brief for any agent working on this. Rules, current state, hosts, layout.
- `docs/MILESTONES.md`: the work, M0 to M7, with acceptance checks and a dependency graph.
- `docs/FINDINGS.md`: what is inside the exe.
- `docs/RUNTIME_SURFACE.md`: all 150 imports, and what each host must provide.

## Status (2026-11-04)

The whole exe has been lifted and the generated C parses with 0 errors. 7 instructions
in 4 functions still need lifter support. Nothing has been linked or run yet. The next
milestones are M1 (lifter gaps), M2 (first boot on Windows via `native32`) and M4a
(Linux shim stubs), which can run in parallel.

The case study with the full analysis is a Claude doc: "Jet Set Radio PC:
Reverse-Engineering Case Study".
