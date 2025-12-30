"""
저장소 및 파일 관리 모듈

TRD 2.9 보안/운영 요구사항:
- 저장 정책: 입력/출력 파일 자동 삭제 (24시간)
- 경로 조작 방지를 위한 파일명 정규화
- 변환 이력 관리
"""

import os
import time
import json
import shutil
import logging
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from contextlib import contextmanager

from .models import ConversionJob, Template, ConversionStatus
from .errors import JobNotFoundError, JobExpiredError, TemplateNotFoundError

logger = logging.getLogger(__name__)


class JobStorage:
    """
    변환 작업 저장소

    변환 작업의 이력을 관리하고, 파일 자동 삭제 정책을 적용합니다.

    TRD 2.9 요구사항:
    - 입력/출력 파일 24시간 자동 삭제
    - 메타데이터 중심 로그 (본문 내용 저장 금지)
    """

    def __init__(
        self,
        base_dir: Optional[str] = None,
        max_age_hours: int = 24,
        cleanup_interval_seconds: int = 3600,
    ):
        """
        저장소 초기화

        Args:
            base_dir: 기본 저장 디렉토리 (None이면 시스템 임시 디렉토리)
            max_age_hours: 파일 최대 보존 시간 (시간)
            cleanup_interval_seconds: 정리 작업 실행 간격 (초)
        """
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            import tempfile

            self.base_dir = Path(tempfile.gettempdir()) / "hwpx_converter"

        self.jobs_dir = self.base_dir / "jobs"
        self.templates_dir = self.base_dir / "templates"
        self.max_age_hours = max_age_hours
        self.cleanup_interval = cleanup_interval_seconds

        # 디렉토리 생성
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.templates_dir.mkdir(parents=True, exist_ok=True)

        # 인메모리 작업 저장소 (파일 기반으로 확장 가능)
        self._jobs: Dict[str, ConversionJob] = {}
        self._templates: Dict[str, Template] = {}
        self._lock = threading.RLock()

        # 백그라운드 정리 스레드
        self._cleanup_thread: Optional[threading.Thread] = None
        self._stop_cleanup = threading.Event()

    def start_cleanup_thread(self):
        """백그라운드 정리 스레드 시작"""
        if self._cleanup_thread is not None and self._cleanup_thread.is_alive():
            return

        self._stop_cleanup.clear()
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()
        logger.info(f"Cleanup thread started (interval: {self.cleanup_interval}s)")

    def stop_cleanup_thread(self):
        """백그라운드 정리 스레드 중지"""
        self._stop_cleanup.set()
        if self._cleanup_thread is not None:
            self._cleanup_thread.join(timeout=5)
            logger.info("Cleanup thread stopped")

    def _cleanup_loop(self):
        """정리 작업 루프"""
        while not self._stop_cleanup.wait(self.cleanup_interval):
            try:
                self.cleanup_expired_files()
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

    def cleanup_expired_files(self) -> int:
        """
        만료된 파일 정리

        Returns:
            삭제된 파일 수
        """
        deleted_count = 0
        cutoff_time = time.time() - (self.max_age_hours * 3600)

        # 작업 디렉토리 정리
        for job_dir in self.jobs_dir.iterdir():
            if job_dir.is_dir():
                try:
                    # 디렉토리 수정 시간 확인
                    if job_dir.stat().st_mtime < cutoff_time:
                        job_id = job_dir.name
                        shutil.rmtree(job_dir)
                        deleted_count += 1

                        # 메모리에서도 제거
                        with self._lock:
                            if job_id in self._jobs:
                                del self._jobs[job_id]

                        logger.info(f"Expired job deleted: {job_id}")
                except Exception as e:
                    logger.warning(f"Failed to delete job dir {job_dir}: {e}")

        if deleted_count > 0:
            logger.info(f"Cleanup completed: {deleted_count} expired jobs deleted")

        return deleted_count

    def _sanitize_filename(self, filename: str) -> str:
        """
        파일명 정규화 (경로 조작 방지)

        Args:
            filename: 원본 파일명

        Returns:
            정규화된 파일명
        """
        # 경로 구분자 제거
        safe_name = filename.replace("/", "_").replace("\\", "_")
        # 상위 디렉토리 참조 제거
        safe_name = safe_name.replace("..", "_")
        # 특수문자 제거 (유니코드 한글은 허용)
        import re

        safe_name = re.sub(r'[<>:"|?*]', "_", safe_name)
        return safe_name

    # ========================================================================
    # 작업(Job) 관리
    # ========================================================================

    def create_job(
        self,
        input_filename: str,
        template_id: str = "default",
        user_id: Optional[str] = None,
    ) -> ConversionJob:
        """
        새 변환 작업 생성

        Args:
            input_filename: 입력 파일명
            template_id: 템플릿 ID
            user_id: 사용자 식별자

        Returns:
            생성된 ConversionJob
        """
        job = ConversionJob(
            input_filename=self._sanitize_filename(input_filename),
            template_id=template_id,
            user_id=user_id,
        )

        # 작업 디렉토리 생성
        job_dir = self.jobs_dir / job.conversion_id
        job_dir.mkdir(exist_ok=True)

        with self._lock:
            self._jobs[job.conversion_id] = job

        # 메타데이터 저장 (파일 기반 백업)
        self._save_job_metadata(job)

        logger.info(f"Job created: {job.conversion_id}")
        return job

    def get_job(self, job_id: str) -> ConversionJob:
        """
        작업 조회

        Args:
            job_id: 작업 ID

        Returns:
            ConversionJob

        Raises:
            JobNotFoundError: 작업을 찾을 수 없을 때
            JobExpiredError: 작업이 만료되었을 때
        """
        with self._lock:
            if job_id in self._jobs:
                return self._jobs[job_id]

        # 파일에서 복원 시도
        job = self._load_job_metadata(job_id)
        if job is None:
            raise JobNotFoundError(job_id)

        # 만료 확인
        job_dir = self.jobs_dir / job_id
        if not job_dir.exists():
            raise JobExpiredError(job_id)

        with self._lock:
            self._jobs[job_id] = job

        return job

    def update_job(self, job: ConversionJob):
        """작업 상태 업데이트"""
        with self._lock:
            self._jobs[job.conversion_id] = job
        self._save_job_metadata(job)
        logger.debug(f"Job updated: {job.conversion_id} -> {job.status.value}")

    def get_job_dir(self, job_id: str) -> Path:
        """작업 디렉토리 경로"""
        return self.jobs_dir / job_id

    def get_input_path(self, job_id: str, filename: str) -> Path:
        """입력 파일 경로"""
        return self.jobs_dir / job_id / f"input_{self._sanitize_filename(filename)}"

    def get_output_path(self, job_id: str, filename: str) -> Path:
        """출력 파일 경로"""
        safe_name = self._sanitize_filename(filename)
        if not safe_name.endswith(".hwpx"):
            safe_name += ".hwpx"
        return self.jobs_dir / job_id / safe_name

    def _save_job_metadata(self, job: ConversionJob):
        """작업 메타데이터 파일 저장"""
        job_dir = self.jobs_dir / job.conversion_id
        job_dir.mkdir(exist_ok=True)

        meta_path = job_dir / "metadata.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(job.model_dump(mode="json"), f, ensure_ascii=False, indent=2)

    def _load_job_metadata(self, job_id: str) -> Optional[ConversionJob]:
        """작업 메타데이터 파일 로드"""
        meta_path = self.jobs_dir / job_id / "metadata.json"
        if not meta_path.exists():
            return None

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ConversionJob(**data)
        except Exception as e:
            logger.warning(f"Failed to load job metadata {job_id}: {e}")
            return None

    def list_jobs(
        self,
        limit: int = 100,
        status: Optional[ConversionStatus] = None,
    ) -> List[ConversionJob]:
        """
        작업 목록 조회

        Args:
            limit: 최대 조회 수
            status: 상태 필터

        Returns:
            ConversionJob 목록
        """
        with self._lock:
            jobs = list(self._jobs.values())

        if status is not None:
            jobs = [j for j in jobs if j.status == status]

        # 최신순 정렬
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    def delete_job(self, job_id: str) -> bool:
        """
        작업 삭제

        Args:
            job_id: 작업 ID

        Returns:
            삭제 성공 여부
        """
        job_dir = self.jobs_dir / job_id

        with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]

        if job_dir.exists():
            shutil.rmtree(job_dir)
            logger.info(f"Job deleted: {job_id}")
            return True

        return False

    # ========================================================================
    # 템플릿 관리
    # ========================================================================

    def register_template(self, template: Template) -> Template:
        """
        템플릿 등록

        Args:
            template: Template 객체

        Returns:
            등록된 Template
        """
        # 파일 존재 확인
        if not Path(template.file_path).exists():
            raise TemplateNotFoundError(template.template_id)

        with self._lock:
            # 기본 템플릿 변경 시 기존 기본 템플릿 해제
            if template.is_default:
                for t in self._templates.values():
                    t.is_default = False

            self._templates[template.template_id] = template

        logger.info(f"Template registered: {template.template_id} (v{template.version})")
        return template

    def get_template(self, template_id: str) -> Template:
        """템플릿 조회"""
        with self._lock:
            if template_id not in self._templates:
                raise TemplateNotFoundError(template_id)
            return self._templates[template_id]

    def get_default_template(self) -> Optional[Template]:
        """기본 템플릿 조회"""
        with self._lock:
            for template in self._templates.values():
                if template.is_default:
                    return template
        return None

    def list_templates(self) -> List[Template]:
        """템플릿 목록 조회"""
        with self._lock:
            return list(self._templates.values())


# 전역 저장소 인스턴스
_storage: Optional[JobStorage] = None


def get_storage() -> JobStorage:
    """전역 저장소 인스턴스 가져오기"""
    global _storage
    if _storage is None:
        _storage = JobStorage()
    return _storage


def init_storage(base_dir: Optional[str] = None, max_age_hours: int = 24) -> JobStorage:
    """저장소 초기화"""
    global _storage
    _storage = JobStorage(base_dir=base_dir, max_age_hours=max_age_hours)
    return _storage
