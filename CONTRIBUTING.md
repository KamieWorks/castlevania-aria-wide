# Contributing

Use the root `DEV_ROOT` and portable `dev.py` entry. Keep changes small enough
to review against one reproducible problem. The shipping code is in
`aria-wide/src/`; retain the frozen MinHook source and its notices.

Run `python dev.py audit`, `build`, `test`, and `package`. For a player ZIP run
`python tools/check_package.py out/releases/AriaWide-v26-release.zip --dll out/build/d3d9.dll`.
Before proposing a public update, run `python tools/check_publication.py --staged`.
Commit with a public/noreply identity and do not import private Git history.

For rendering fixes record the supported EXE hash, original/translated region,
room and native raster timing, expected/observed behavior, and scoped evidence.
Moving-edge regressions need consecutive frames, including frames while the
native camera continues and the wide viewport has clamped. Check layer and
sprite motion independently, as well as relevant HUD/rewind behavior.

Do not attach game archives, ROMs, personal saves, full memory dumps or private
account/configuration data to an issue or PR. Generate fixtures locally from
your own installation. Explain which results are compile/offline checks,
runtime rendering checks, or actual gameplay. Do not describe a room-loading
or event-replay test as a complete playthrough.

The independent public-source tree contains portability adaptations to the
original development tools. When refreshing a release, update the exact source
mapping and public manifest after review, without silently changing the
recorded shipping binary hash.
