import gzip
import os
import re
import shutil
import time
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

from config import (
    LOG_DIR,
    LOG_ROTATION_BACKUP_COUNT,
    LOG_ROTATION_COMPRESS,
    LOG_ROTATION_INTERVAL,
    LOG_ROTATION_MAX_BYTES,
    LOG_ROTATION_MODE,
    LOG_ROTATION_WHEN,
)


class SmartRotatingFileHandler(TimedRotatingFileHandler):
    """支持按时间/大小轮转并压缩旧日志的处理器。"""

    _ROLLOVER_RE = re.compile(
        r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_\d{6}(?:\.gz)?$"
    )

    def __init__(self, filename, mode="a", encoding="utf-8", delay=False):
        del mode  # TimedRotatingFileHandler 不使用 mode，保留仅为兼容 logging.ini args

        if not os.path.isabs(filename) and not os.path.dirname(filename):
            filename = os.path.join(LOG_DIR, filename)

        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)

        rotation_when = LOG_ROTATION_WHEN or "D"
        rotation_interval = max(1, LOG_ROTATION_INTERVAL)
        backup_count = max(0, LOG_ROTATION_BACKUP_COUNT)

        super().__init__(
            filename=filename,
            when=rotation_when,
            interval=rotation_interval,
            backupCount=backup_count,
            encoding=encoding,
            delay=delay,
        )

        rotation_mode = (LOG_ROTATION_MODE or "both").lower()
        self.enable_time_rotation = rotation_mode in ("time", "both")
        self.enable_size_rotation = rotation_mode in ("size", "both")
        self.max_bytes = max(0, LOG_ROTATION_MAX_BYTES)
        self.compress_backups = LOG_ROTATION_COMPRESS

    def shouldRollover(self, record):
        if self.enable_time_rotation and super().shouldRollover(record):
            return 1

        if self.enable_size_rotation and self.max_bytes > 0:
            if self.stream is None:
                self.stream = self._open()

            msg = f"{self.format(record)}\n"
            self.stream.seek(0, os.SEEK_END)
            if self.stream.tell() + len(msg.encode(self.encoding or "utf-8", errors="replace")) >= self.max_bytes:
                return 1

        return 0

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None

        if os.path.exists(self.baseFilename):
            rollover_name = self._build_rollover_filename()
            self.rotate(self.baseFilename, rollover_name)

        current_time = int(time.time())
        self.rolloverAt = self.computeRollover(current_time)
        while self.rolloverAt <= current_time:
            self.rolloverAt += self.interval

        if not self.delay:
            self.stream = self._open()

        for old_file in self.getFilesToDelete():
            if os.path.exists(old_file):
                os.remove(old_file)

    def rotate(self, source, dest):
        if not os.path.exists(source):
            return

        os.replace(source, dest)
        if self.compress_backups:
            self._compress_file(dest)

    def getFilesToDelete(self):
        if self.backupCount <= 0:
            return []

        dir_name, base_name = os.path.split(self.baseFilename)
        prefix = f"{base_name}."
        candidates = []

        for filename in os.listdir(dir_name or "."):
            if not filename.startswith(prefix):
                continue
            suffix = filename[len(prefix):]
            if self._ROLLOVER_RE.match(suffix):
                candidates.append(os.path.join(dir_name, filename))

        candidates.sort()
        if len(candidates) <= self.backupCount:
            return []
        return candidates[: len(candidates) - self.backupCount]

    def _build_rollover_filename(self):
        base = f"{self.baseFilename}.{datetime.now().strftime('%Y-%m-%d_%H-%M-%S_%f')}"
        candidate = base
        serial = 1

        while os.path.exists(candidate) or os.path.exists(f"{candidate}.gz"):
            candidate = f"{base}_{serial}"
            serial += 1

        return candidate

    def _compress_file(self, file_path):
        gz_path = f"{file_path}.gz"
        with open(file_path, "rb") as src, gzip.open(gz_path, "wb") as dst:
            shutil.copyfileobj(src, dst)
        os.remove(file_path)
