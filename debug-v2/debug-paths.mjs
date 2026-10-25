import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root = fileURLToPath(new URL('..', import.meta.url));
export const debugRoot = path.resolve(process.env.ARIA_DEBUG_ROOT || path.join(root, 'out/debug'));
// Standalone Node diagnostics require an explicit game directory; Python
// launchers can also discover the Steam library via debug_config.py.
export const gameExe = path.resolve(process.env.ARIA_GAME_ROOT || path.join(root, 'game'), 'game.exe');
