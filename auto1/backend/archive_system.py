import os
import json
import hashlib
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
import logging
from pathlib import Path
import sqlite3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ArchiveRecord:
    archive_id: str
    meeting_id: str
    meeting_date: str
    archived_at: str
    file_path: str
    file_hash: str
    file_size: int
    file_type: str
    access_level: str
    retention_period: str
    description: str = ""
    metadata: Dict = field(default_factory=dict)


class ComplianceArchiveSystem:
    def __init__(self, archive_root: Optional[str] = None, db_path: Optional[str] = None):
        self.archive_root = archive_root or os.environ.get('ARCHIVE_DIR', './archive')
        self.db_path = db_path or os.path.join(self.archive_root, 'archive_index.db')
        
        os.makedirs(self.archive_root, exist_ok=True)
        self._init_database()

    def _init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS archives (
                archive_id TEXT PRIMARY KEY,
                meeting_id TEXT NOT NULL,
                meeting_date TEXT NOT NULL,
                archived_at TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_type TEXT NOT NULL,
                access_level TEXT NOT NULL,
                retention_period TEXT NOT NULL,
                description TEXT,
                metadata TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS access_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                archive_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                action TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                details TEXT,
                FOREIGN KEY (archive_id) REFERENCES archives (archive_id)
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_meeting_id ON archives(meeting_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_meeting_date ON archives(meeting_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_type ON archives(file_type)')
        
        conn.commit()
        conn.close()
        logger.info("Archive database initialized")

    def _generate_archive_id(self, meeting_id: str, file_type: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        raw = f"{meeting_id}_{file_type}_{timestamp}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _compute_file_hash(self, file_path: str) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _get_retention_period(self, file_type: str, access_level: str) -> str:
        retention_map = {
            ('audio', 'confidential'): '7 years',
            ('transcript', 'confidential'): '15 years',
            ('summary', 'official'): 'permanent',
            ('summary', 'confidential'): '25 years',
            ('markdown', 'official'): 'permanent',
            ('json', 'official'): 'permanent',
        }
        return retention_map.get((file_type, access_level), '7 years')

    def archive_file(
        self,
        file_path: str,
        meeting_id: str,
        meeting_date: str,
        file_type: str,
        access_level: str = 'confidential',
        description: str = "",
        metadata: Optional[Dict] = None
    ) -> Optional[ArchiveRecord]:
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return None
        
        logger.info(f"Archiving {file_path} for meeting {meeting_id}")
        
        date_folder = datetime.strptime(meeting_date, "%Y-%m-%d").strftime("%Y/%m")
        archive_dir = os.path.join(self.archive_root, date_folder, meeting_id)
        os.makedirs(archive_dir, exist_ok=True)
        
        file_name = os.path.basename(file_path)
        dest_path = os.path.join(archive_dir, file_name)
        
        if os.path.abspath(file_path) != os.path.abspath(dest_path):
            shutil.copy2(file_path, dest_path)
        
        file_hash = self._compute_file_hash(dest_path)
        file_size = os.path.getsize(dest_path)
        archive_id = self._generate_archive_id(meeting_id, file_type)
        retention_period = self._get_retention_period(file_type, access_level)
        
        record = ArchiveRecord(
            archive_id=archive_id,
            meeting_id=meeting_id,
            meeting_date=meeting_date,
            archived_at=datetime.now().isoformat(),
            file_path=dest_path,
            file_hash=file_hash,
            file_size=file_size,
            file_type=file_type,
            access_level=access_level,
            retention_period=retention_period,
            description=description,
            metadata=metadata or {}
        )
        
        self._save_record(record)
        self._log_access(archive_id, 'system', 'archive', f"Archived {file_name}")
        
        logger.info(f"File archived with ID: {archive_id}")
        return record

    def _save_record(self, record: ArchiveRecord):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO archives VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            record.archive_id,
            record.meeting_id,
            record.meeting_date,
            record.archived_at,
            record.file_path,
            record.file_hash,
            record.file_size,
            record.file_type,
            record.access_level,
            record.retention_period,
            record.description,
            json.dumps(record.metadata)
        ))
        
        conn.commit()
        conn.close()

    def _log_access(self, archive_id: str, user_id: str, action: str, details: str = ""):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO access_logs (archive_id, user_id, action, timestamp, details)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            archive_id,
            user_id,
            action,
            datetime.now().isoformat(),
            details
        ))
        
        conn.commit()
        conn.close()

    def retrieve_file(self, archive_id: str, user_id: str = 'anonymous') -> Optional[ArchiveRecord]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM archives WHERE archive_id = ?', (archive_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            logger.warning(f"Archive record not found: {archive_id}")
            return None
        
        record = ArchiveRecord(
            archive_id=row[0],
            meeting_id=row[1],
            meeting_date=row[2],
            archived_at=row[3],
            file_path=row[4],
            file_hash=row[5],
            file_size=row[6],
            file_type=row[7],
            access_level=row[8],
            retention_period=row[9],
            description=row[10],
            metadata=json.loads(row[11]) if row[11] else {}
        )
        
        current_hash = self._compute_file_hash(record.file_path)
        if current_hash != record.file_hash:
            logger.warning(f"File integrity check failed for {archive_id}")
        
        self._log_access(archive_id, user_id, 'retrieve', "File retrieved")
        
        return record

    def search_archives(
        self,
        meeting_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        file_type: Optional[str] = None,
        access_level: Optional[str] = None
    ) -> List[ArchiveRecord]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = 'SELECT * FROM archives WHERE 1=1'
        params = []
        
        if meeting_id:
            query += ' AND meeting_id = ?'
            params.append(meeting_id)
        if start_date:
            query += ' AND meeting_date >= ?'
            params.append(start_date)
        if end_date:
            query += ' AND meeting_date <= ?'
            params.append(end_date)
        if file_type:
            query += ' AND file_type = ?'
            params.append(file_type)
        if access_level:
            query += ' AND access_level = ?'
            params.append(access_level)
        
        query += ' ORDER BY meeting_date DESC'
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        records = []
        for row in rows:
            records.append(ArchiveRecord(
                archive_id=row[0],
                meeting_id=row[1],
                meeting_date=row[2],
                archived_at=row[3],
                file_path=row[4],
                file_hash=row[5],
                file_size=row[6],
                file_type=row[7],
                access_level=row[8],
                retention_period=row[9],
                description=row[10],
                metadata=json.loads(row[11]) if row[11] else {}
            ))
        
        return records

    def verify_integrity(self, archive_id: Optional[str] = None) -> Dict:
        results = {
            'total_files': 0,
            'verified': 0,
            'corrupted': 0,
            'missing': 0,
            'corrupted_files': [],
            'missing_files': []
        }
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if archive_id:
            cursor.execute('SELECT archive_id, file_path, file_hash FROM archives WHERE archive_id = ?', (archive_id,))
        else:
            cursor.execute('SELECT archive_id, file_path, file_hash FROM archives')
        
        rows = cursor.fetchall()
        conn.close()
        
        results['total_files'] = len(rows)
        
        for archive_id, file_path, expected_hash in rows:
            if not os.path.exists(file_path):
                results['missing'] += 1
                results['missing_files'].append(archive_id)
                continue
            
            current_hash = self._compute_file_hash(file_path)
            if current_hash == expected_hash:
                results['verified'] += 1
            else:
                results['corrupted'] += 1
                results['corrupted_files'].append(archive_id)
        
        return results

    def archive_meeting_artifacts(
        self,
        meeting_id: str,
        meeting_date: str,
        audio_path: Optional[str] = None,
        transcript_path: Optional[str] = None,
        summary_md_path: Optional[str] = None,
        summary_json_path: Optional[str] = None,
        additional_files: Optional[List[str]] = None
    ) -> Dict[str, ArchiveRecord]:
        logger.info(f"Archiving all artifacts for meeting {meeting_id}")
        
        archives = {}
        
        if audio_path and os.path.exists(audio_path):
            archives['audio'] = self.archive_file(
                audio_path, meeting_id, meeting_date, 'audio', 'confidential',
                'Original meeting audio recording'
            )
        
        if transcript_path and os.path.exists(transcript_path):
            archives['transcript'] = self.archive_file(
                transcript_path, meeting_id, meeting_date, 'transcript', 'confidential',
                'Full meeting transcript with speaker diarization'
            )
        
        if summary_md_path and os.path.exists(summary_md_path):
            archives['summary_md'] = self.archive_file(
                summary_md_path, meeting_id, meeting_date, 'markdown', 'official',
                'Structured meeting summary in Markdown format'
            )
        
        if summary_json_path and os.path.exists(summary_json_path):
            archives['summary_json'] = self.archive_file(
                summary_json_path, meeting_id, meeting_date, 'json', 'official',
                'Structured meeting summary in JSON format'
            )
        
        if additional_files:
            for i, file_path in enumerate(additional_files):
                if os.path.exists(file_path):
                    file_type = os.path.splitext(file_path)[1][1:] or 'unknown'
                    archives[f'additional_{i}'] = self.archive_file(
                        file_path, meeting_id, meeting_date, file_type, 'confidential',
                        f'Additional meeting document {i+1}'
                    )
        
        return archives
