"""Explicit migration of control state, preserving every execution project root."""
import ctypes
import errno
import os
import shutil
import sys
import tempfile
from pathlib import Path

from .core import MIGRATED_MARKER, Store, AppError, now, read_json, write_json


def publish_directory(source, destination):
    """Atomically publish a staged directory without replacing any concurrent destination."""
    source, destination = os.fsencode(source), os.fsencode(destination)
    if os.name == 'nt':
        os.rename(os.fsdecode(source), os.fsdecode(destination))  # Windows rename never replaces an existing directory
        return
    library = ctypes.CDLL(None, use_errno=True)
    if sys.platform == 'darwin':
        rename = library.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        result = rename(source, destination, 0x00000004)  # SDK sys/stdio.h: RENAME_EXCL
    elif sys.platform.startswith('linux') and hasattr(library, 'renameat2'):
        rename = library.renameat2
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        result = rename(-100, source, -100, destination, 1)  # AT_FDCWD, RENAME_NOREPLACE
    else:
        raise OSError(errno.ENOTSUP, 'This platform cannot safely publish a workspace without replacing an existing directory.')
    if result:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), os.fsdecode(destination))


def sync_directory(path):
    if os.name != 'nt':
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def migrate_workspace(source, destination):
    source = Path(source).expanduser().resolve()
    destination = Path(destination).expanduser().resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError('Source and destination must be separate directories.')
    if not (source / 'registry.json').is_file():
        raise ValueError('Source has no Folio workspace registry.')
    if destination.exists():
        raise ValueError('Destination already exists; existing data has not been changed.')
    if (source / MIGRATED_MARKER).exists():
        raise ValueError(f'Source was already migrated; delete {source / MIGRATED_MARKER} only if that migration is abandoned.')
    try:
        store = Store(source)
    except AppError as error:
        raise ValueError('Stop Folio before migrating this workspace.') from error
    staged = None
    try:
        registry = store.registry()
        if registry.get('schema_version') != 1:
            raise ValueError('Unsupported workspace schema.')
        for registration in registry['projects']:
            store.project(registration['id'])
        destination.parent.mkdir(parents=True, exist_ok=True)
        staged = Path(tempfile.mkdtemp(prefix=f'.{destination.name}-migrate-', dir=destination.parent))
        shutil.copy2(source / 'registry.json', staged / 'registry.json')
        sync = source / '.sync'
        if sync.exists():
            if sync.is_symlink() or any(path.is_symlink() for path in sync.rglob('*')):
                raise ValueError('Workspace sync state must not be a symlink.')
            shutil.copytree(sync, staged / '.sync')
        if read_json(staged / 'registry.json') != registry:
            raise ValueError('Copied registry verification failed.')
        for path in staged.rglob('*'):
            if path.is_file():
                with path.open('rb') as handle:
                    os.fsync(handle.fileno())
        for directory in sorted((path for path in staged.rglob('*') if path.is_dir()), key=lambda path: len(path.parts), reverse=True):
            sync_directory(directory)
        sync_directory(staged)
        # Disable the source durably before the destination becomes visible. A crash
        # between publication and a later marker write would otherwise permit two writers.
        marker = source / MIGRATED_MARKER
        try:
            write_json(marker, {'destination': str(destination), 'migrated_at': now()})
            sync_directory(source)
            publish_directory(staged, destination)
        except OSError:
            # An atomic publication that failed leaves the staging directory in place.
            # Never re-enable the source after publication, including a later I/O error.
            if staged.exists():
                marker.unlink(missing_ok=True)
                sync_directory(source)
            raise
        staged = None  # the visible destination is never deleted by an error handler
        sync_directory(destination.parent)
        inside = [item['path'] for item in registry['projects'] if source in Path(item['path']).resolve().parents]
        next_step = 'Use --data-dir or FOLIO_WORKSPACE for the destination; retain the registered project folders.'
        if inside:
            next_step += f' Do not delete {source}: {len(inside)} registered project folder(s) live inside it.'
        return {'workspace': str(destination), 'source_preserved': str(source),
                'retained_project_folders': [item['path'] for item in registry['projects']],
                'projects_inside_source': inside, 'next_step': next_step}
    finally:
        if staged is not None:
            shutil.rmtree(staged, ignore_errors=True)
        store.close()
