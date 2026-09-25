"""Small process-local stock caches, invalidated by files and their ancestry."""
from collections import OrderedDict
from pathlib import Path
import os
import stat
from threading import RLock


def _watch_paths(root, paths):
    watched = {root}
    for path in paths:
        if '..' in path.relative_to(root).parts:
            raise ValueError(f'Stock input escapes installation: {path}')
        watched.add(path)
        watched.update(parent for parent in path.parents if parent == root or root in parent.parents)
    return tuple(sorted(watched, key=str))


def _stamp(paths, directories=()):
    result = []
    for path in paths:
        try:
            info = path.lstat()
        except FileNotFoundError:
            result.append(None)
            continue
        # Never reuse a cache across a symbolic link/junction boundary.
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            return None
        result.append((info.st_mode, info.st_dev, info.st_ino, info.st_size,
                       info.st_mtime_ns, info.st_ctime_ns))
    # NTFS can defer directory timestamps. Explicit discovery directories need
    # a shallow name snapshot so additions cannot hide behind unchanged times.
    for directory in directories:
        try:
            with os.scandir(directory) as children:
                result.append(tuple(sorted(child.name for child in children)))
        except FileNotFoundError:
            result.append(None)
    return tuple(result)


class StockInputCache:
    """Retain only a few installations/selections; no persistent disk cache."""

    def __init__(self, capacity=4):
        self.capacity = capacity
        self.entries = OrderedDict()
        self.lock = RLock()

    def get(self, root: Path, key, paths_factory, loader):
        key = (str(root), key)
        with self.lock:
            previous = self.entries.get(key)
            if previous is not None:
                watched, directories, stamp, value = previous
                current = _stamp(watched, directories)
                if current is not None and current == stamp:
                    self.entries.move_to_end(key)
                    return value
                del self.entries[key]
            paths = tuple(paths_factory())
            watched = _watch_paths(root, paths)
            directories = tuple(dict.fromkeys(p for p in paths if p.is_dir()))
            before = _stamp(watched, directories)
            value = loader()
            after = _stamp(watched, directories)
            # Project edits can change the declared input set, not only bytes.
            if before != after or paths != tuple(paths_factory()):
                raise ValueError('Installed stock inputs changed while being read; retry preparation.')
            if before is not None:
                self.entries[key] = (watched, directories, before, value)
                while len(self.entries) > self.capacity:
                    self.entries.popitem(last=False)
            return value

    def clear(self):
        with self.lock:
            self.entries.clear()
