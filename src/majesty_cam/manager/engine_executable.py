"""Publish an explicitly requested engine patch to the selected beta executable."""
from __future__ import annotations
import hashlib
from pathlib import Path
import subprocess
import tempfile
from .elevation import directory_requires_elevation, run_elevated_hidden
from .._subprocess import no_console_window_options


def publish(source, data, *, repo_root, runner=None, elevated_runner=None, elevation_probe=None):
    source = source.resolve(strict=True)
    if source.name.casefold() != 'majestyhd.exe':
        raise ValueError('Select MajestyHD.exe')
    from .qol_service import detect_majesty_branch
    if detect_majesty_branch(source) is None:
        raise ValueError('Unsupported Majesty executable')
    previous = hashlib.sha256(source.read_bytes()).hexdigest()
    expected = hashlib.sha256(data).hexdigest()
    if previous == expected:
        return source
    from .profile import default_profile_path
    work = default_profile_path().parent / 'executable-work'
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='engine-', dir=str(work)) as folder:
        candidate = Path(folder) / 'candidate.exe'
        candidate.write_bytes(data)
        script = repo_root / 'payload/panel-engine/Publish-EngineExecutable.ps1'
        command = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script),
                   '-Target', str(source), '-Candidate', str(candidate), '-CandidateHash', expected,
                   '-PreviousHash', previous]
        if (elevation_probe or directory_requires_elevation)(source.parent):
            result = (elevated_runner or run_elevated_hidden)(command)
        else:
            result = (runner(command) if runner else subprocess.run(command, capture_output=True,
                text=True, timeout=60, **no_console_window_options()))
        if result.returncode:
            raise OSError('Could not update Majesty. Close the game if it is open. ' +
                          (result.stdout or '') + (result.stderr or ''))
    if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
        raise OSError('Engine patch publication did not produce the expected bytes')
    return source
