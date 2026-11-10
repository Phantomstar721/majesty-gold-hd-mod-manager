"""Isolated alpha executable publication; the selected original stays read-only."""
from __future__ import annotations
import hashlib
from pathlib import Path
import tempfile
from .elevation import directory_requires_elevation, run_elevated_hidden
from .._subprocess import no_console_window_options
import subprocess
import json

NAME='MajestyHD.PanelEngineAlpha.exe'


def target_for(source):
    return source.with_name(NAME)


def current_path(source):
    target=target_for(source)
    return target if target.is_file() else source


def publish(source, data, *, repo_root, runner=None, elevated_runner=None, elevation_probe=None,ui_files=None):
    """Publish only the fixed sibling name through a checked atomic replacement.

    Invoked by the app after an explicit QoL action or Launch. This helper is
    never called by scan, build, dependency discovery or profile switching.
    """
    source=source.resolve(strict=True)
    if source.name.casefold()!='majestyhd.exe':raise ValueError('Select the original MajestyHD.exe')
    from .qol_service import detect_majesty_branch
    branch=detect_majesty_branch(source)
    if branch is None:raise ValueError('Unsupported original Majesty executable')
    target=target_for(source)
    if ui_files is None:
        # Snapshot native layouts with the alpha executable, including the
        # first engine installation/launch. Later beta QoL changes must not
        # make its EXE and shared layout files disagree with each other.
        originals=tuple((source.parent/'Data').glob('UIData_*.dat'))
        if originals:
            from .alpha_ui import rewrite,names
            data,private=rewrite(data,repo_root,branch,private=True)
            ui_files={}
            for path in originals:
                shadow=path.with_name(names(path.name))
                if not private:
                    if shadow.exists():raise ValueError('Unowned alpha resolution-layout file already exists')
                    ui_files[path.name]=path.read_bytes()
                elif not shadow.exists():ui_files[path.name]=path.read_bytes()
    previous=hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else 'absent'
    expected=hashlib.sha256(data).hexdigest()
    ui_files=ui_files or {}
    if previous==expected and not ui_files:return target
    # User-owned per-edition state; never write a temporary game/profile there.
    from .profile import default_profile_path
    work=default_profile_path().parent/'executable-work'
    work.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='publish-',dir=str(work)) as folder:
        candidate=Path(folder)/'candidate.exe';candidate.write_bytes(data)
        script=repo_root/'payload/panel-engine/Publish-AlphaExecutable.ps1'
        command=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script),
                 '-Original',str(source),'-Candidate',str(candidate),'-CandidateHash',expected,
                 '-PreviousHash',previous]
        if ui_files:
            from .alpha_ui import names
            rows=[]
            for index,(name,contents) in enumerate(sorted(ui_files.items())):
                private_name=names(name)
                destination=source.parent/'Data'/private_name
                old=hashlib.sha256(destination.read_bytes()).hexdigest() if destination.is_file() else 'absent'
                digest=hashlib.sha256(contents).hexdigest()
                if old==digest:continue
                path=Path(folder)/('ui-'+str(index)+'.dat');path.write_bytes(contents)
                rows.append(dict(name=private_name,candidate=str(path),sha256=digest,previous=old))
            manifest=Path(folder)/'ui-files.json'
            manifest.write_text(json.dumps(rows),encoding='utf8')
            command.extend(('-UIManifest',str(manifest)))
        if (elevation_probe or directory_requires_elevation)(source.parent):
            result=(elevated_runner or run_elevated_hidden)(command)
        elif runner:result=runner(command)
        else:result=subprocess.run(command,capture_output=True,text=True,timeout=60,**no_console_window_options())
        if result.returncode:raise OSError('Could not update the alpha executable. Close Majesty if it is open. '+
                                           (result.stdout or '')+(result.stderr or ''))
    if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest()!=expected:
        raise OSError('Alpha executable publication did not produce the expected bytes')
    if ui_files:
        from .alpha_ui import names
        for name,contents in ui_files.items():
            if (source.parent/'Data'/names(name)).read_bytes()!=contents:
                raise OSError('Alpha layout publication did not produce the expected bytes')
    return target
