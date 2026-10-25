# Community development rules

- Start with README.md, docs/SOURCE_MAP.md, docs/BUILDING.md and
  docs/RENDERING.md. `aria-wide/src/` is the sole shipping core. Historical
  snapshots are research material, not an alternative active implementation.
- Keep the exact executable hash and entry signatures. Do not accept an
  unknown game build by replacing a hash without doing the required analysis.
- Preserve genuine horizontal expansion, native pixel proportions, the
  four-corner HUD, original gameplay/collision bounds and native animation.
  Fixed rooms/artwork stay centered; retain the complete opt-in
  ExtendFixedRooms implementation, disabled by default.
- Viewport, BG parallax and OBJ cloud fractions must describe the same raster.
  Cloud objects have native camera rate 1/12 and independent self-drift.
  Birds sharing their palette/priority are not clouds. See RENDERING.md.
- Build and generated data belong in ignored out/. Never commit game assets,
  ROMs, saves, personal configuration, logs/dumps, local paths or credentials.
  Preserve upstream licenses and review exact staged blobs before publication.
- Runtime tests require explicit authorization, a verified process identity,
  current-profile protection and a bounded run. Default to hidden, muted,
  process-local input and native-surface screenshots; never steal focus or
  send global input. Keep Steam write/stat protection until the game exits.
- Do not attach Frida/Gum listeners at instruction addresses inside functions.
  Use the register-preserving native input guard. Full function entry/return
  hooks are permitted. Restore diagnostic writes and snapshots in finally.
- Only one controller may operate a game at a time. Do not replace a loaded
  DLL or close an unrelated/user-owned game. Restore game mute only after the
  verified diagnostic process exits, retaining and checking its audio interface.
- Preserve source/data rollback before installation. Build success, frame
  presentation, room-loading smoke and full gameplay are different evidence.
- Record durable rules here, architecture/evidence in docs/, plans separately
  and behavioral requirements in meaningful tests. Never record secrets or
  turn private diagnostic state into a public fixture.
