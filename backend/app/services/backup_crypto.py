"""Private backup key storage and authenticated backup envelopes."""

import asyncio
import base64
import binascii
import fcntl
import json
import os
import stat
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from sqlalchemy import select
from sqlalchemy.engine import make_url

from ..core.config_loader import config_loader
from ..models.settings import BackupEncryptionState

MARKER = "linguard-encrypted-backup"
PARAMS = {"format": MARKER, "version": 1, "kdf": "scrypt", "n": 32768, "r": 8, "p": 1, "cipher": "AES-256-GCM"}


class MissingBackupKeyError(RuntimeError):
    pass


class UnsafeBackupKeyError(RuntimeError):
    pass


class UnsafeBackupIntentError(RuntimeError):
    pass


def looks_encrypted(document):
    return isinstance(document, dict) and bool(document.keys() & {"format", "ciphertext", "cipher", "kdf", "salt", "nonce"})


def key_path():
    return Path(os.environ.get("LINGUARD_BACKUP_KEY_PATH") or config_loader.config_path.parent / "backup.key")


def intent_path():
    return key_path().parent / ".backup-key-required"


@asynccontextmanager
async def key_lock():
    descriptors = []
    try:
        # The config directory coordinates creation of a not-yet-existing key directory.
        paths = (config_loader.config_path.parent, key_path().parent)
        seen = set()
        for path in paths:
            try:
                fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            except FileNotFoundError:
                if path == config_loader.config_path.parent:
                    raise
                continue
            info = os.fstat(fd)
            identity = (info.st_dev, info.st_ino)
            if identity in seen:
                os.close(fd)
                continue
            seen.add(identity)
            descriptors.append(fd)
    except OSError as exc:
        for fd in descriptors:
            os.close(fd)
        raise RuntimeError("Cannot access backup key lock") from exc
    try:
        for fd in descriptors:
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    await asyncio.sleep(0.05)
        yield
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def _read_intent(path):
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(fd, "rb") as f:
            info = os.fstat(f.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077 or f.read(16) != b"required\n":
                raise OSError("Invalid backup encryption intent")
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise UnsafeBackupIntentError("Backup encryption intent is unsafe or unreadable; local operator action required") from exc


def _intent_required():
    current = _read_intent(intent_path())
    legacy = config_loader.config_path.parent / ".backup-key-required"
    if legacy != intent_path():
        legacy_required = _read_intent(legacy)
        return current or legacy_required
    return current


def _set_intent():
    path = intent_path()
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".backup-key-intent-", dir=path.parent)
        with os.fdopen(fd, "wb") as f:
            f.write(b"required\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
        temporary = None
        _sync_directory(path.parent)
    except OSError as exc:
        raise RuntimeError("Cannot persist backup encryption intent") from exc
    finally:
        if temporary is not None:
            os.unlink(temporary)


def configured_key():
    required = _intent_required()
    key = read_key()
    if required and key is None:
        raise MissingBackupKeyError("Configured backup key file is missing")
    if key is not None and not required:
        _set_intent()
    return key


async def persist_required(db, required):
    """Update intent in the caller's transaction; never release its locks."""
    state = (await db.execute(select(BackupEncryptionState).where(BackupEncryptionState.id == 1))).scalar_one_or_none()
    if state is None:
        state = BackupEncryptionState(id=1, required=required)
        db.add(state)
    else:
        state.required = required
    await db.flush()


async def database_configured_key(db):
    # Missing rows are migration state, not proof that encryption was disabled.
    state = (await db.execute(select(BackupEncryptionState).where(BackupEncryptionState.id == 1))).scalar_one_or_none()
    required = bool(state and state.required)
    try:
        marker = _intent_required()
    except RuntimeError:
        if not required:
            await persist_required(db, True)
        raise
    if not required:
        try:
            os.lstat(key_path())
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise RuntimeError("Cannot inspect backup key file") from exc
        else:
            await persist_required(db, True)
            required = True
            if not marker:
                _set_intent()
                marker = True
    if not required and marker:
        await persist_required(db, True)
        required = True
    if required and not marker:
        if read_key() is None:
            raise MissingBackupKeyError("Configured backup key file is missing")
        raise RuntimeError("Configured backup encryption intent file is missing")
    key = configured_key()
    if state is None and not required:
        await persist_required(db, False)
    return key


def validate_key_location(backup_dir, database_url=None):
    path = key_path().resolve()
    directory = Path(backup_dir).resolve()
    if path == directory or directory in path.parents:
        raise ValueError("Backup key file must be outside the backup directory")
    reserved = (config_loader.config_path, intent_path(), config_loader.config_path.parent / ".backup-key-required", config_loader.config_path.parent / ".backup-key-lock")
    if path in {item.resolve() for item in reserved}:
        raise ValueError("Backup key file must be separate from configuration and state files")
    if directory == intent_path().parent.resolve() or directory in intent_path().parent.resolve().parents:
        raise ValueError("Backup encryption state must be outside the backup directory")
    legacy = config_loader.config_path.parent / ".backup-key-required"
    if _read_intent(legacy) and (directory == legacy.parent.resolve() or directory in legacy.parent.resolve().parents):
        raise ValueError("Backup encryption state must be outside the backup directory")
    if database_url:
        url = make_url(str(database_url))
        if (url.get_backend_name() == "sqlite" and url.database and url.database != ":memory:"
                and path == Path(url.database).resolve()):
            raise ValueError("Backup key file must be separate from the database")


def read_key():
    try:
        fd = os.open(key_path(), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(fd, "rb") as f:
            info = os.fstat(f.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.geteuid() or info.st_nlink != 1:
                raise OSError("Unsafe backup key file")
            value = f.read(65537)
        if not value or len(value) > 65536:
            raise OSError("Invalid backup key file")
        return value.decode("utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError) as exc:
        raise UnsafeBackupKeyError("Backup key file is unsafe or unreadable; local operator action required") from exc


def _sync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def validate_key(value):
    if not value:
        raise ValueError("Use DELETE to remove the backup key")
    if len(value.encode("utf-8")) > 65536:
        raise ValueError("Backup key is too long")


def set_key(value, missing_only=False):
    validate_key(value)
    existing = read_key()  # Never replace an unreadable or unsafe existing key.
    if missing_only and existing is not None:
        raise FileExistsError("Backup key file already exists")
    # Persist intent before creating/replacing the secret, so interrupted writes fail closed.
    if not _intent_required():
        _set_intent()
    path = key_path()
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".backup-key-", dir=path.parent)
        with os.fdopen(fd, "wb") as f:
            f.write(value.encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())
        if missing_only or existing is None:
            os.link(temporary, path, follow_symlinks=False)
            os.unlink(temporary)
            temporary = None
        else:
            os.replace(temporary, path)
            temporary = None
        _sync_directory(path.parent)
    except FileExistsError:
        raise
    except OSError as exc:
        raise RuntimeError("Cannot store backup key file") from exc
    finally:
        if temporary is not None:
            os.unlink(temporary)


def clear_key():
    key = read_key()
    removed_intent = False
    try:
        path = key_path()
        if key is not None:
            os.unlink(path)
            _sync_directory(path.parent)
        # A failed key removal must never remove the encryption requirement.
        if _intent_required():
            legacy = config_loader.config_path.parent / ".backup-key-required"
            for marker in dict.fromkeys((legacy, intent_path())):
                if _read_intent(marker):
                    os.unlink(marker)
                    removed_intent = True
                    _sync_directory(marker.parent)
    except OSError as exc:
        if removed_intent:
            _set_intent()
        raise RuntimeError("Cannot remove backup key file") from exc


def _decode(value, length=None):
    if not isinstance(value, str):
        raise ValueError("Invalid encrypted backup")
    try:
        result = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("Invalid encrypted backup") from None
    if length is not None and len(result) != length:
        raise ValueError("Invalid encrypted backup")
    return result


def validate_envelope(envelope):
    if not isinstance(envelope, dict) or set(envelope) != set(PARAMS) | {"salt", "nonce", "ciphertext"}:
        raise ValueError("Invalid encrypted backup")
    if any(type(envelope[k]) is not type(v) or envelope[k] != v for k, v in PARAMS.items()):
        raise ValueError("Unsupported encrypted backup format")
    salt = _decode(envelope["salt"], 16)
    nonce = _decode(envelope["nonce"], 12)
    ciphertext = _decode(envelope["ciphertext"])
    if len(ciphertext) < 16:
        raise ValueError("Invalid encrypted backup")
    return salt, nonce, ciphertext


def _derive(key, salt):
    return Scrypt(salt=salt, length=32, n=PARAMS["n"], r=PARAMS["r"], p=PARAMS["p"]).derive(key.encode("utf-8"))


def _aad(envelope):
    return json.dumps({k: envelope[k] for k in (*PARAMS, "salt", "nonce")}, sort_keys=True, separators=(",", ":")).encode()


def encrypt_backup(data, key):
    salt, nonce = os.urandom(16), os.urandom(12)
    envelope = {**PARAMS, "salt": base64.b64encode(salt).decode(), "nonce": base64.b64encode(nonce).decode()}
    ciphertext = AESGCM(_derive(key, salt)).encrypt(nonce, data.encode("utf-8"), _aad(envelope))
    envelope["ciphertext"] = base64.b64encode(ciphertext).decode()
    return json.dumps(envelope)


def decrypt_backup(envelope, key):
    salt, nonce, ciphertext = validate_envelope(envelope)
    if not key:
        raise ValueError("Passphrase required for encrypted backup")
    try:
        return AESGCM(_derive(key, salt)).decrypt(nonce, ciphertext, _aad(envelope)).decode("utf-8")
    except (InvalidTag, UnicodeError):
        raise ValueError("Invalid passphrase or encrypted backup") from None
