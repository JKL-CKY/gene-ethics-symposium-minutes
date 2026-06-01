import os
import sys
import json
import uuid
import asyncio
from datetime import datetime
from typing import List, Optional, Dict
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audio_processor import AudioProcessor
from transcriber import WhisperTranscriber
from speaker_diarization import SpeakerDiarizer
from summary_generator import SummaryGenerator, MeetingSummary, GeneLocus
from email_sender import EmailSender
from archive_system import ComplianceArchiveSystem, ArchiveRecord
from workflow_tasks import run_workflow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Gene Editing Ethics Symposium Minutes API",
    description="API for processing and managing gene editing ethics symposium minutes",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.environ.get('AUDIO_UPLOAD_DIR', './uploads')
OUTPUT_DIR = os.environ.get('OUTPUT_DIR', './output')
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


class MeetingInfo(BaseModel):
    meeting_id: str = Field(default_factory=lambda: f"SYMP-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}")
    title: str = "Gene Editing Ethics Symposium"
    date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    participants: Optional[List[Dict]] = None
    description: Optional[str] = None


class MeetingStatusResponse(BaseModel):
    meeting_id: str
    status: str
    current_task: Optional[str] = None
    progress: float = 0.0
    error_message: Optional[str] = None
    created_at: str
    updated_at: str


class GeneLocusResponse(BaseModel):
    gene_name: str
    chromosome: str
    position: str
    rs_id: Optional[str] = None
    function: str
    discussion_points: List[str]


class MeetingSummaryResponse(BaseModel):
    meeting_id: str
    meeting_date: str
    title: str
    participants: List[Dict]
    gene_loci: List[GeneLocusResponse]
    technical_feasibility: Dict
    ethical_risks: List[Dict]
    social_impact: Dict
    conclusions: List[str]
    action_items: List[Dict]


processing_status: Dict[str, Dict] = {}


@app.get("/")
async def root():
    return {
        "name": "Gene Editing Ethics Symposium Minutes API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "POST /api/meetings/upload": "Upload audio file and process",
            "GET /api/meetings/{meeting_id}/status": "Get processing status",
            "GET /api/meetings/{meeting_id}/summary": "Get meeting summary",
            "GET /api/meetings/{meeting_id}/gene-loci": "Get gene loci discussed",
            "GET /api/meetings": "List all meetings",
            "GET /api/archives": "Search archives",
            "GET /api/archives/{archive_id}": "Get archive record"
        }
    }


@app.post("/api/meetings/upload", response_model=Dict)
async def upload_and_process(
    background_tasks: BackgroundTasks,
    audio_file: UploadFile = File(...),
    meeting_title: Optional[str] = None,
    meeting_date: Optional[str] = None
):
    meeting_id = f"SYMP-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    
    file_extension = os.path.splitext(audio_file.filename)[1]
    audio_path = os.path.join(UPLOAD_DIR, f"{meeting_id}{file_extension}")
    
    with open(audio_path, "wb") as f:
        content = await audio_file.read()
        f.write(content)
    
    processing_status[meeting_id] = {
        "meeting_id": meeting_id,
        "status": "queued",
        "current_task": "Waiting to start",
        "progress": 0.0,
        "error_message": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "audio_path": audio_path,
        "title": meeting_title or "Gene Editing Ethics Symposium",
        "date": meeting_date or datetime.now().strftime("%Y-%m-%d")
    }
    
    background_tasks.add_task(process_meeting_background, meeting_id, audio_path, meeting_title)
    
    return {
        "meeting_id": meeting_id,
        "status": "processing_started",
        "message": "Audio uploaded successfully. Processing has started in the background.",
        "status_endpoint": f"/api/meetings/{meeting_id}/status"
    }


async def process_meeting_background(meeting_id: str, audio_path: str, meeting_title: Optional[str]):
    try:
        processing_status[meeting_id]["status"] = "processing"
        processing_status[meeting_id]["current_task"] = "Processing audio"
        processing_status[meeting_id]["progress"] = 0.1
        processing_status[meeting_id]["updated_at"] = datetime.now().isoformat()
        
        processor = AudioProcessor()
        cleaned_audio_path = os.path.join(OUTPUT_DIR, meeting_id, f"{meeting_id}_cleaned_audio.wav")
        os.makedirs(os.path.dirname(cleaned_audio_path), exist_ok=True)
        processor.process_audio_pipeline(audio_path, cleaned_audio_path)
        
        processing_status[meeting_id]["current_task"] = "Transcribing audio"
        processing_status[meeting_id]["progress"] = 0.3
        processing_status[meeting_id]["updated_at"] = datetime.now().isoformat()
        
        transcriber = WhisperTranscriber(model_size="medium")
        full_text, segments = transcriber.transcribe_with_normalization(cleaned_audio_path)
        
        processing_status[meeting_id]["current_task"] = "Diarizing speakers"
        processing_status[meeting_id]["progress"] = 0.5
        processing_status[meeting_id]["updated_at"] = datetime.now().isoformat()
        
        diarizer = SpeakerDiarizer()
        speaker_turns = diarizer.diarize(cleaned_audio_path)
        merged_segments = diarizer.merge_transcript_with_diarization(segments, speaker_turns)
        
        processing_status[meeting_id]["current_task"] = "Generating summary"
        processing_status[meeting_id]["progress"] = 0.7
        processing_status[meeting_id]["updated_at"] = datetime.now().isoformat()
        
        generator = SummaryGenerator()
        summary = generator.generate_full_summary(
            meeting_id=meeting_id,
            transcript=full_text,
            merged_segments=merged_segments,
            title=meeting_title or "Gene Editing Ethics Symposium"
        )
        
        md_path, json_path = generator.save_summary(summary, os.path.join(OUTPUT_DIR, meeting_id))
        
        processing_status[meeting_id]["current_task"] = "Sending emails and archiving"
        processing_status[meeting_id]["progress"] = 0.9
        processing_status[meeting_id]["updated_at"] = datetime.now().isoformat()
        
        ethics_email = os.environ.get('ETHICS_COMMITTEE_EMAIL', 'ethics-committee@example.com')
        email_sender = EmailSender()
        email_sender.send_summary_email(
            to_emails=[ethics_email],
            summary_markdown=summary.full_markdown,
            summary_json_path=json_path,
            meeting_id=meeting_id,
            meeting_title=summary.title
        )
        
        archiver = ComplianceArchiveSystem()
        archiver.archive_meeting_artifacts(
            meeting_id=meeting_id,
            meeting_date=summary.meeting_date,
            audio_path=cleaned_audio_path,
            summary_md_path=md_path,
            summary_json_path=json_path
        )
        
        processing_status[meeting_id]["status"] = "completed"
        processing_status[meeting_id]["current_task"] = None
        processing_status[meeting_id]["progress"] = 1.0
        processing_status[meeting_id]["updated_at"] = datetime.now().isoformat()
        processing_status[meeting_id]["summary_path"] = md_path
        processing_status[meeting_id]["summary_json_path"] = json_path
        
        logger.info(f"Processing completed for meeting {meeting_id}")
        
    except Exception as e:
        logger.error(f"Error processing meeting {meeting_id}: {str(e)}")
        processing_status[meeting_id]["status"] = "failed"
        processing_status[meeting_id]["error_message"] = str(e)
        processing_status[meeting_id]["updated_at"] = datetime.now().isoformat()


@app.get("/api/meetings/{meeting_id}/status", response_model=MeetingStatusResponse)
async def get_meeting_status(meeting_id: str):
    if meeting_id not in processing_status:
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found")
    
    status = processing_status[meeting_id]
    return MeetingStatusResponse(
        meeting_id=status["meeting_id"],
        status=status["status"],
        current_task=status.get("current_task"),
        progress=status.get("progress", 0.0),
        error_message=status.get("error_message"),
        created_at=status["created_at"],
        updated_at=status["updated_at"]
    )


@app.get("/api/meetings/{meeting_id}/summary")
async def get_meeting_summary(meeting_id: str):
    if meeting_id not in processing_status:
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found")
    
    status = processing_status[meeting_id]
    if status["status"] != "completed":
        return {
            "meeting_id": meeting_id,
            "status": status["status"],
            "message": "Summary not yet available. Processing is still in progress."
        }
    
    json_path = status.get("summary_json_path")
    if not json_path or not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="Summary not found")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        summary_data = json.load(f)
    
    return summary_data


@app.get("/api/meetings/{meeting_id}/summary/markdown")
async def get_meeting_summary_markdown(meeting_id: str):
    if meeting_id not in processing_status:
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found")
    
    status = processing_status[meeting_id]
    if status["status"] != "completed":
        return {
            "meeting_id": meeting_id,
            "status": status["status"],
            "message": "Summary not yet available. Processing is still in progress."
        }
    
    md_path = status.get("summary_path")
    if not md_path or not os.path.exists(md_path):
        raise HTTPException(status_code=404, detail="Summary not found")
    
    return FileResponse(md_path, media_type='text/markdown', filename=f"{meeting_id}_summary.md")


@app.get("/api/meetings/{meeting_id}/gene-loci", response_model=List[GeneLocusResponse])
async def get_gene_loci(meeting_id: str):
    if meeting_id not in processing_status:
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found")
    
    status = processing_status[meeting_id]
    if status["status"] != "completed":
        raise HTTPException(status_code=400, detail="Processing not complete")
    
    json_path = status.get("summary_json_path")
    if not json_path or not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="Summary not found")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        summary_data = json.load(f)
    
    gene_loci = summary_data.get("gene_loci", [])
    return [GeneLocusResponse(**locus) for locus in gene_loci]


@app.get("/api/meetings")
async def list_meetings():
    meetings = []
    for meeting_id, status in processing_status.items():
        meetings.append({
            "meeting_id": meeting_id,
            "title": status.get("title", "Untitled"),
            "date": status.get("date", ""),
            "status": status["status"],
            "progress": status.get("progress", 0.0),
            "created_at": status["created_at"],
            "updated_at": status["updated_at"]
        })
    
    meetings.sort(key=lambda x: x["created_at"], reverse=True)
    return {"meetings": meetings, "total": len(meetings)}


@app.get("/api/archives")
async def search_archives(
    meeting_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    file_type: Optional[str] = None,
    access_level: Optional[str] = None
):
    archiver = ComplianceArchiveSystem()
    records = archiver.search_archives(
        meeting_id=meeting_id,
        start_date=start_date,
        end_date=end_date,
        file_type=file_type,
        access_level=access_level
    )
    
    return {
        "archives": [
            {
                "archive_id": r.archive_id,
                "meeting_id": r.meeting_id,
                "meeting_date": r.meeting_date,
                "archived_at": r.archived_at,
                "file_type": r.file_type,
                "file_size": r.file_size,
                "access_level": r.access_level,
                "retention_period": r.retention_period,
                "description": r.description
            }
            for r in records
        ],
        "total": len(records)
    }


@app.get("/api/archives/{archive_id}")
async def get_archive(archive_id: str):
    archiver = ComplianceArchiveSystem()
    record = archiver.retrieve_file(archive_id)
    
    if not record:
        raise HTTPException(status_code=404, detail=f"Archive {archive_id} not found")
    
    return {
        "archive_id": record.archive_id,
        "meeting_id": record.meeting_id,
        "meeting_date": record.meeting_date,
        "archived_at": record.archived_at,
        "file_path": record.file_path,
        "file_hash": record.file_hash,
        "file_size": record.file_size,
        "file_type": record.file_type,
        "access_level": record.access_level,
        "retention_period": record.retention_period,
        "description": record.description,
        "metadata": record.metadata
    }


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "audio_processor": "available",
            "transcriber": "available",
            "speaker_diarizer": "available",
            "summary_generator": "available",
            "email_sender": "available",
            "archive_system": "available"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
