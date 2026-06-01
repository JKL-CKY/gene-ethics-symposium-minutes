import os
import sys
import json
import luigi
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audio_processor import AudioProcessor
from transcriber import WhisperTranscriber
from speaker_diarization import SpeakerDiarizer
from summary_generator import SummaryGenerator
from email_sender import EmailSender
from archive_system import ComplianceArchiveSystem

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MeetingConfig(luigi.Config):
    meeting_id = luigi.Parameter(default="SYMP-2024-001")
    meeting_title = luigi.Parameter(default="Gene Editing Ethics Symposium")
    meeting_date = luigi.Parameter(default=datetime.now().strftime("%Y-%m-%d"))
    input_audio_path = luigi.Parameter(default="./uploads/meeting_audio.wav")
    output_dir = luigi.Parameter(default="./output")
    ethics_committee_email = luigi.Parameter(
        default=os.environ.get('ETHICS_COMMITTEE_EMAIL', 'ethics-committee@example.com')
    )
    reviewer_emails = luigi.ListParameter(
        default=json.loads(os.environ.get('REVIEWER_EMAILS', '[]'))
    )


class ProcessAudioTask(luigi.Task):
    meeting_id = luigi.Parameter()
    input_audio_path = luigi.Parameter()
    output_dir = luigi.Parameter()

    def output(self):
        return luigi.LocalTarget(
            os.path.join(self.output_dir, self.meeting_id, f"{self.meeting_id}_cleaned_audio.wav")
        )

    def run(self):
        logger.info(f"Running audio processing for meeting {self.meeting_id}")
        
        os.makedirs(os.path.dirname(self.output().path), exist_ok=True)
        
        processor = AudioProcessor()
        processor.process_audio_pipeline(
            self.input_audio_path,
            self.output().path
        )
        
        with self.output().open('w') as f:
            f.write(json.dumps({
                'status': 'completed',
                'meeting_id': self.meeting_id,
                'output_path': self.output().path,
                'processed_at': datetime.now().isoformat()
            }))


class TranscribeAudioTask(luigi.Task):
    meeting_id = luigi.Parameter()
    output_dir = luigi.Parameter()

    def requires(self):
        return ProcessAudioTask(
            meeting_id=self.meeting_id,
            input_audio_path=MeetingConfig().input_audio_path,
            output_dir=self.output_dir
        )

    def output(self):
        return luigi.LocalTarget(
            os.path.join(self.output_dir, self.meeting_id, f"{self.meeting_id}_transcript.json")
        )

    def run(self):
        logger.info(f"Running transcription for meeting {self.meeting_id}")
        
        audio_path = self.input().path.replace('.json', '.wav')
        
        transcriber = WhisperTranscriber(model_size="medium")
        full_text, segments = transcriber.transcribe_with_normalization(audio_path)
        
        output_data = {
            'meeting_id': self.meeting_id,
            'full_text': full_text,
            'segments': [
                {
                    'start': seg.start,
                    'end': seg.end,
                    'text': seg.text,
                    'confidence': seg.confidence
                }
                for seg in segments
            ],
            'transcribed_at': datetime.now().isoformat()
        }
        
        with self.output().open('w') as f:
            json.dump(output_data, f, indent=2)


class DiarizeSpeakersTask(luigi.Task):
    meeting_id = luigi.Parameter()
    output_dir = luigi.Parameter()

    def requires(self):
        return TranscribeAudioTask(
            meeting_id=self.meeting_id,
            output_dir=self.output_dir
        )

    def output(self):
        return luigi.LocalTarget(
            os.path.join(self.output_dir, self.meeting_id, f"{self.meeting_id}_diarized.json")
        )

    def run(self):
        logger.info(f"Running speaker diarization for meeting {self.meeting_id}")
        
        with self.input().open('r') as f:
            transcript_data = json.load(f)
        
        audio_path = os.path.join(
            self.output_dir, self.meeting_id, f"{self.meeting_id}_cleaned_audio.wav"
        )
        
        diarizer = SpeakerDiarizer()
        speaker_turns = diarizer.diarize(audio_path)
        
        from transcriber import TranscriptSegment
        transcript_segments = [
            TranscriptSegment(
                start=seg['start'],
                end=seg['end'],
                text=seg['text'],
                confidence=seg['confidence']
            )
            for seg in transcript_data['segments']
        ]
        
        merged = diarizer.merge_transcript_with_diarization(transcript_segments, speaker_turns)
        
        output_data = {
            'meeting_id': self.meeting_id,
            'full_text': transcript_data['full_text'],
            'merged_segments': merged,
            'diarized_at': datetime.now().isoformat()
        }
        
        with self.output().open('w') as f:
            json.dump(output_data, f, indent=2)


class GenerateSummaryTask(luigi.Task):
    meeting_id = luigi.Parameter()
    meeting_title = luigi.Parameter()
    output_dir = luigi.Parameter()

    def requires(self):
        return DiarizeSpeakersTask(
            meeting_id=self.meeting_id,
            output_dir=self.output_dir
        )

    def output(self):
        return [
            luigi.LocalTarget(
                os.path.join(self.output_dir, self.meeting_id, f"{self.meeting_id}_summary.md")
            ),
            luigi.LocalTarget(
                os.path.join(self.output_dir, self.meeting_id, f"{self.meeting_id}_summary.json")
            )
        ]

    def run(self):
        logger.info(f"Generating summary for meeting {self.meeting_id}")
        
        with self.input().open('r') as f:
            diarized_data = json.load(f)
        
        generator = SummaryGenerator()
        summary = generator.generate_full_summary(
            meeting_id=self.meeting_id,
            transcript=diarized_data['full_text'],
            merged_segments=diarized_data['merged_segments'],
            title=self.meeting_title
        )
        
        md_path, json_path = generator.save_summary(summary, os.path.join(self.output_dir, self.meeting_id))
        
        logger.info(f"Summary generated: {md_path}")


class SendInitialEmailTask(luigi.Task):
    meeting_id = luigi.Parameter()
    meeting_title = luigi.Parameter()
    output_dir = luigi.Parameter()
    ethics_committee_email = luigi.Parameter()

    def requires(self):
        return GenerateSummaryTask(
            meeting_id=self.meeting_id,
            meeting_title=self.meeting_title,
            output_dir=self.output_dir
        )

    def output(self):
        return luigi.LocalTarget(
            os.path.join(self.output_dir, self.meeting_id, f"{self.meeting_id}_email_sent.json")
        )

    def run(self):
        logger.info(f"Sending initial email for meeting {self.meeting_id}")
        
        md_path, json_path = self.input()
        
        with md_path.open('r') as f:
            summary_markdown = f.read()
        
        email_sender = EmailSender()
        success = email_sender.send_summary_email(
            to_emails=[self.ethics_committee_email],
            summary_markdown=summary_markdown,
            summary_json_path=json_path.path,
            meeting_id=self.meeting_id,
            meeting_title=self.meeting_title
        )
        
        output_data = {
            'meeting_id': self.meeting_id,
            'email_sent': success,
            'recipients': [self.ethics_committee_email],
            'sent_at': datetime.now().isoformat()
        }
        
        with self.output().open('w') as f:
            json.dump(output_data, f, indent=2)


class RequestReviewsTask(luigi.Task):
    meeting_id = luigi.Parameter()
    meeting_title = luigi.Parameter()
    output_dir = luigi.Parameter()
    reviewer_emails = luigi.ListParameter()
    review_round = luigi.IntParameter(default=1)

    def requires(self):
        return SendInitialEmailTask(
            meeting_id=self.meeting_id,
            meeting_title=self.meeting_title,
            output_dir=self.output_dir,
            ethics_committee_email=MeetingConfig().ethics_committee_email
        )

    def output(self):
        return luigi.LocalTarget(
            os.path.join(
                self.output_dir,
                self.meeting_id,
                f"{self.meeting_id}_review_round_{self.review_round}_requests.json"
            )
        )

    def run(self):
        logger.info(f"Requesting reviews (round {self.review_round}) for meeting {self.meeting_id}")
        
        md_path = os.path.join(
            self.output_dir, self.meeting_id, f"{self.meeting_id}_summary.md"
        )
        
        with open(md_path, 'r') as f:
            summary_markdown = f.read()
        
        email_sender = EmailSender()
        deadline = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        
        results = []
        for reviewer_email in self.reviewer_emails:
            success = email_sender.send_review_request(
                reviewer_email=reviewer_email,
                review_round=self.review_round,
                meeting_id=self.meeting_id,
                meeting_title=self.meeting_title,
                summary_markdown=summary_markdown,
                deadline=deadline
            )
            results.append({
                'reviewer': reviewer_email,
                'request_sent': success,
                'deadline': deadline
            })
        
        output_data = {
            'meeting_id': self.meeting_id,
            'review_round': self.review_round,
            'review_requests': results,
            'requests_sent_at': datetime.now().isoformat()
        }
        
        with self.output().open('w') as f:
            json.dump(output_data, f, indent=2)


class ArchiveArtifactsTask(luigi.Task):
    meeting_id = luigi.Parameter()
    meeting_date = luigi.Parameter()
    output_dir = luigi.Parameter()

    def requires(self):
        return RequestReviewsTask(
            meeting_id=self.meeting_id,
            meeting_title=MeetingConfig().meeting_title,
            output_dir=self.output_dir,
            reviewer_emails=MeetingConfig().reviewer_emails
        )

    def output(self):
        return luigi.LocalTarget(
            os.path.join(self.output_dir, self.meeting_id, f"{self.meeting_id}_archive_complete.json")
        )

    def run(self):
        logger.info(f"Archiving artifacts for meeting {self.meeting_id}")
        
        audio_path = os.path.join(
            self.output_dir, self.meeting_id, f"{self.meeting_id}_cleaned_audio.wav"
        )
        transcript_path = os.path.join(
            self.output_dir, self.meeting_id, f"{self.meeting_id}_diarized.json"
        )
        summary_md_path = os.path.join(
            self.output_dir, self.meeting_id, f"{self.meeting_id}_summary.md"
        )
        summary_json_path = os.path.join(
            self.output_dir, self.meeting_id, f"{self.meeting_id}_summary.json"
        )
        
        archiver = ComplianceArchiveSystem()
        archives = archiver.archive_meeting_artifacts(
            meeting_id=self.meeting_id,
            meeting_date=self.meeting_date,
            audio_path=audio_path,
            transcript_path=transcript_path,
            summary_md_path=summary_md_path,
            summary_json_path=summary_json_path
        )
        
        output_data = {
            'meeting_id': self.meeting_id,
            'archived_at': datetime.now().isoformat(),
            'archive_ids': {
                key: record.archive_id if record else None
                for key, record in archives.items()
            }
        }
        
        with self.output().open('w') as f:
            json.dump(output_data, f, indent=2)
        
        logger.info(f"Archive complete for meeting {self.meeting_id}")


class FullProcessingWorkflow(luigi.WrapperTask):
    meeting_id = luigi.Parameter(default=MeetingConfig().meeting_id)
    meeting_title = luigi.Parameter(default=MeetingConfig().meeting_title)
    meeting_date = luigi.Parameter(default=MeetingConfig().meeting_date)
    input_audio_path = luigi.Parameter(default=MeetingConfig().input_audio_path)
    output_dir = luigi.Parameter(default=MeetingConfig().output_dir)
    ethics_committee_email = luigi.Parameter(default=MeetingConfig().ethics_committee_email)
    reviewer_emails = luigi.ListParameter(default=MeetingConfig().reviewer_emails)

    def requires(self):
        yield ArchiveArtifactsTask(
            meeting_id=self.meeting_id,
            meeting_date=self.meeting_date,
            output_dir=self.output_dir
        )


def run_workflow(
    meeting_id: str,
    input_audio_path: str,
    meeting_title: Optional[str] = None,
    output_dir: Optional[str] = None,
    local_scheduler: bool = True
):
    logger.info(f"Starting workflow for meeting {meeting_id}")
    
    params = {
        'meeting_id': meeting_id,
        'input_audio_path': input_audio_path,
    }
    
    if meeting_title:
        params['meeting_title'] = meeting_title
    if output_dir:
        params['output_dir'] = output_dir
    
    if local_scheduler:
        luigi.build(
            [FullProcessingWorkflow(**params)],
            local_scheduler=True,
            detailed_summary=True
        )
    else:
        luigi.build(
            [FullProcessingWorkflow(**params)],
            workers=1,
            detailed_summary=True
        )
    
    logger.info(f"Workflow completed for meeting {meeting_id}")


if __name__ == '__main__':
    luigi.run()
