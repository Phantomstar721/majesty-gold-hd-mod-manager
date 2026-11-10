"""Headless packaged-alpha regression entry; never launches Majesty or a window.

The case directory owns every writable path and a disposable game copy. This
is deliberately a separate process: the ordinary suite pre-imports modules.
"""
import hashlib
import json
import os
from pathlib import Path
import traceback


def run(case_path):
    case_path = Path(case_path).resolve(strict=True)
    root = case_path.parent
    receipt = root / 'startup-result.json'
    try:
        case = json.loads(case_path.read_bytes())
        game = root / 'game'
        if not (game / 'MajestyHD.exe').is_file():
            raise ValueError('A disposable game fixture is required')
        os.environ['LOCALAPPDATA'] = str(root / 'appdata')
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        from dataclasses import replace
        from .paths import detect_manager_paths
        from .controller import ManagerController
        from .qol_service import QolService, QolUtilityState
        from .app import QApplication, _QolPage, ManagerWindow
        from types import SimpleNamespace
        paths = replace(detect_manager_paths(game_path=game,
            documents_root=root / 'documents', local_appdata=root / 'appdata'),
            workshop_roots=())
        before = _files(game)
        application = QApplication.instance() or QApplication(['alpha-startup-check', '-platform', 'offscreen'])
        page = _QolPage()
        captures = []
        for attempt in range(2):
            controller = ManagerController(paths=paths)
            controller.qol_service = QolService(repo_root=paths.repo_root,
                game_executable=paths.game_executable,
                prefs_path=root / 'documents/My Games/MajestyHD/MajXPrefs')
            snapshot = controller.scan()
            page.populate(snapshot.qol_utilities)
            if snapshot.notices:
                raise ValueError('Startup notices: ' + repr(snapshot.notices))
            if snapshot.game_build is None or snapshot.game_build.key != case['branch']:
                raise ValueError('Startup lost the recognized game version')
            expected = {spec.key for spec in controller.qol_service.specs}
            if {card.key for card in page.cards} != expected:
                raise ValueError('Startup did not render every QoL helper')
            bad = {item.key: item.detail for item in snapshot.qol_utilities
                   if not item.applicable or item.installed is None}
            if bad:
                raise ValueError('QoL inspection failed: ' + repr(bad))
            # Exercise the real main-window renderer, not only the cards.
            # Ready/blocked snapshots are synthetic UI inputs: no merged
            # package is constructed and no launch action is invoked.
            view = SimpleNamespace(paths=paths, profile=controller.profile,
                                   detected_installations=lambda: ())
            window = ManagerWindow(view)
            ready = replace(snapshot, can_launch=True, build_required=False,
                plan=replace(snapshot.plan, selected_merge=(object(),)),
                managed_build=SimpleNamespace(output_root=paths.merged_output_root),
                qol_utilities=tuple(replace(item, installed=True, state=QolUtilityState.INSTALLED)
                    if item.required_for_manager else item for item in snapshot.qol_utilities))
            try:
                window._render_build_state(ready)
                if not window.launch_button.isEnabled():
                    raise ValueError('Ready alpha setup rendered a disabled Launch button')
                window._render_build_state(replace(ready, can_launch=False, build_required=True))
                if window.launch_button.isEnabled():
                    raise ValueError('Unprepared setup rendered an enabled Launch button')
            finally:
                window.close()
            captures.append(dict(branch=snapshot.game_build.key,
                rows={item.key: item.state.value for item in snapshot.qol_utilities},
                launchRendering='synthetic-ready-and-blocked'))
        if before != _files(game) or paths.merged_output_root.exists():
            raise ValueError('Startup mutated game inputs or constructed an output profile')
        receipt.write_text(json.dumps(dict(ok=True, captures=captures), indent=2), encoding='utf8')
        return 0
    except Exception:
        receipt.write_text(json.dumps(dict(ok=False, error=traceback.format_exc()), indent=2), encoding='utf8')
        return 1


def _files(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}
