"""Run the real alpha entry in fresh processes, with private game/state fixtures."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def verify(application=None, *, beta=False):
    from majesty_cam.manager.alpha_ui import rewrite, names
    from majesty_cam.manager.qol_service import detect_majesty_branch
    from majesty_cam import engine_module
    from majesty_cam._subprocess import no_console_window_options
    parent = ROOT / ('local/panel-engine-beta/cold-start' if beta else 'local/panel-engine-alpha/cold-start')
    parent.mkdir(parents=True, exist_ok=True)
    evidence = []
    for branch in ('public', 'beta2', 'gog'):
        fixture = Path(os.environ['MAJESTY_' + branch.upper() + '_EXE'])
        stock = Path(os.environ['MAJESTY_BCD_GOG_GAME' if branch == 'gog' else 'MAJESTY_BCD_GAME'])
        for private in (False, True):
            with tempfile.TemporaryDirectory(prefix=branch+'-', dir=parent) as temporary:
                root = Path(temporary)
                game = root / 'game'; game.mkdir()
                shutil.copyfile(fixture, game / 'MajestyHD.exe')
                shutil.copytree(stock / 'Data/_custom_quest_button_originals', game / 'Data/_custom_quest_button_originals') if (stock / 'Data/_custom_quest_button_originals').is_dir() else None
                (game / 'Data').mkdir(exist_ok=True)
                for path in (stock / 'Data').glob('UIData_*.dat'):
                    shutil.copyfile(path, game / 'Data' / path.name)
                if not tuple((game/'Data').glob('UIData_*.dat')):
                    raise ValueError('Missing resolution archive fixtures for '+branch)
                if private:
                    data = fixture.read_bytes()
                    for service in ('window-engine', 'script-functions'):
                        bundle = ROOT/'local/panel-engine-alpha/native-modules'/(service+'-'+branch+'.mmne')
                        data = engine_module.install(data, bundle.read_bytes(), branch)
                    if beta:
                        (game/'MajestyHD.exe').write_bytes(data)
                    else:
                        data, _ = rewrite(data, ROOT, detect_majesty_branch(fixture), private=True)
                        (game/'MajestyHD.PanelEngineAlpha.exe').write_bytes(data)
                        for path in (game/'Data').glob('UIData_*.dat'):
                            shutil.copyfile(path, path.with_name(names(path.name)))
                case = root / 'case.json'
                case.write_text(json.dumps(dict(branch=branch,private=private)), encoding='utf8')
                command = ([str(application / (application.name+'.exe'))] if application else
                    [sys.executable, str(ROOT/('scripts/mod_manager_entry.py' if beta else 'scripts/panel_engine_alpha_entry.py'))])
                env = dict(os.environ, PYTHONPATH=str(ROOT/'src'), LOCALAPPDATA=str(root/'appdata'),
                    TEMP=str(root), TMP=str(root), QT_QPA_PLATFORM='offscreen')
                if beta:
                    env.pop('MAJESTY_MANAGER_EDITION', None)
                result = subprocess.run(command+['--check-qol-startup', str(case)], env=env,
                    capture_output=True, text=True, timeout=150, **no_console_window_options())
                output = root/'startup-result.json'
                report = json.loads(output.read_bytes()) if output.is_file() else {}
                if result.returncode or not report.get('ok'):
                    raise RuntimeError(branch+' private='+str(private)+': '+
                        report.get('error', result.stdout+result.stderr or 'No startup receipt'))
                if not report.get('captures') or any(row.get('launchRendering') != 'synthetic-ready-and-blocked'
                                                   for row in report['captures']):
                    raise ValueError('Packaged startup did not exercise the launch-button renderer')
                evidence.append(dict(branch=branch, private=private, captures=report['captures']))
    target = parent / ('packaged.json' if application else 'source.json')
    record = dict(packaged=bool(application), cases=evidence)
    if application:
        exe = application / (application.name+'.exe')
        record['executableSHA256'] = hashlib.sha256(exe.read_bytes()).hexdigest()
    target.write_text(json.dumps(record, indent=2), encoding='utf8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--application', type=Path)
    parser.add_argument('--beta', action='store_true')
    args = parser.parse_args()
    try:
        verify(args.application, beta=args.beta)
    except Exception as exc:
        print('Alpha cold-start check failed: '+str(exc), file=sys.stderr)
        raise SystemExit(1)
