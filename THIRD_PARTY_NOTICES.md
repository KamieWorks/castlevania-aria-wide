# Licensing boundaries

Original AriaWide code, authored tools and documentation use the root MIT
license. This does not relicense the game, game resources, translations,
decompiled third-party code, or software installed separately by a developer.

MinHook is pinned to commit `8af6b4acae5a9388fd742b56fa79ece89d96f823`.
Its source, HDE components and complete notices are retained in
`aria-wide/vendor/minhook/`; the file hashes are checked during `dev.py audit`.
The player README reproduces the complete bundled notices.

Node Frida and Python diagnostic dependencies are installed separately using
their own licenses. They are development tools and are not linked into the
player DLL. No game executable, ROM, translation package, save, memory dump,
downloaded reverse-engineering application or generated binary is included.
