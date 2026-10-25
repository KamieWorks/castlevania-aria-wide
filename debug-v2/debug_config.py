from debug_config import debug_root
"""Local developer configuration. Values are never written into tracked files."""
import os
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]

def steam_root():
    value = os.environ.get('ARIA_STEAM_ROOT')
    if value:
        return Path(value).expanduser().resolve()
    if os.name == 'nt':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as key:
                return Path(winreg.QueryValueEx(key, 'SteamPath')[0]).resolve()
        except OSError:
            pass
    raise RuntimeError('Set ARIA_STEAM_ROOT to your local Steam installation.')

def game_exe():
    value = os.environ.get('ARIA_GAME_ROOT')
    if value:
        return Path(value).expanduser().resolve() / 'game.exe'
    try:
        steam = steam_root()
        libraries = [steam]
        config = steam / 'steamapps/libraryfolders.vdf'
        if config.is_file():
            libraries += [Path(s.replace('\\\\', '\\')) for s in re.findall(r'"path"\s+"([^"]+)"', config.read_text(encoding='utf-8'))]
        for library in libraries:
            manifest = library / 'steamapps/appmanifest_1552550.acf'
            if manifest.is_file():
                match = re.search(r'"installdir"\s+"([^"]+)"', manifest.read_text(encoding='utf-8'))
                if match:
                    return library / 'steamapps/common' / match[1] / 'game.exe'
    except RuntimeError:
        pass
    return ROOT / 'game/game.exe'

def profile_root():
    value = os.environ.get('ARIA_PROFILE_ROOT')
    if value:
        path = Path(value).expanduser().resolve()
        if not path.is_dir():
            raise RuntimeError('ARIA_PROFILE_ROOT must be an existing save directory.')
        return path
    matches = list((steam_root() / 'userdata').glob('*/1552550/remote'))
    if len(matches) != 1:
        raise RuntimeError('Set ARIA_PROFILE_ROOT explicitly when Steam has zero or multiple matching profiles.')
    return matches[0]

def debug_root():
    path = Path(os.environ.get('ARIA_DEBUG_ROOT', ROOT / 'out/debug')).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path

def depot_manifest():
    value = os.environ.get('ARIA_DEPOT_MANIFEST')
    return Path(value).resolve() if value else steam_root() / 'depotcache/1552551_8609910394922333285.manifest'

def debugger_exe():
    value = os.environ.get('ARIA_CDB') or shutil.which('cdb.exe')
    if not value:
        raise RuntimeError('Set ARIA_CDB or add the Windows x86 CDB debugger to PATH.')
    return Path(value).resolve()
