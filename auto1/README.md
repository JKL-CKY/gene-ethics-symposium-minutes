# Gene Editing Ethics Symposium - Transparent Minutes System

A full-stack application for processing and managing gene editing ethics symposium minutes.

## Features

### Backend
- **Audio Processing**: Uses librosa to eliminate lab equipment noise with spectral subtraction and Wiener filtering
- **Speech Recognition**: Whisper for accurate transcription with specialized gene editing term normalization
- **Speaker Diarization**: pyannote-audio to distinguish between scientists and ethicists
- **AI Summary Generation**: OpenAI GPT-4 to generate structured summaries covering:
  - Technical feasibility assessment
  - Ethical risk analysis
  - Social impact evaluation
- **Email Notifications**: Automated summaries sent to ethics committee
- **Compliance Archiving**: Secure, integrity-verified document archiving system
- **Workflow Orchestration**: Luigi for multi-round review task management

### Frontend
- **Interactive Genome Browser**: D3.js visualization of gene loci discussed in meetings
- **Meeting Management**: Upload audio, track processing status
- **Summary Visualization**: Structured display of technical, ethical, and social analyses
- **Responsive Design**: Modern UI with Tailwind CSS

## Project Structure

```
├── backend/
│   ├── main.py                 # FastAPI application
│   ├── audio_processor.py      # librosa noise reduction
│   ├── transcriber.py          # Whisper transcription
│   ├── speaker_diarization.py  # pyannote speaker separation
│   ├── summary_generator.py    # OpenAI summary generation
│   ├── email_sender.py         # Email notifications
│   ├── archive_system.py       # Compliance archiving
│   └── workflow_tasks.py       # Luigi workflow tasks
├── frontend/
│   └── index.html              # Interactive genome browser UI
├── Dockerfile                  # Backend Docker configuration
├── docker-compose.yml          # Full stack orchestration
├── nginx.conf                  # Reverse proxy configuration
├── requirements.txt            # Python dependencies
└── package.json                # Frontend dependencies
```

## Quick Start

### Using Docker (Recommended)

```bash
# Copy environment file
cp .env.example .env

# Edit .env with your API keys and configuration

# Start all services
./start.sh
```

Access the application:
- Frontend: http://localhost
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Luigi Scheduler: http://localhost:8082

### Manual Setup

#### Backend

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your API keys

# Run the API
uvicorn backend.main:app --reload --port 8000
```

#### Frontend

```bash
# Install dependencies (if using npm)
npm install

# Or simply open frontend/index.html in a browser
# The frontend uses CDN links, no build required
```

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key for summary generation |
| `OPENAI_MODEL` | OpenAI model to use (default: gpt-4-turbo-preview) |
| `PYANNOTE_AUTH_TOKEN` | HuggingFace token for pyannote-audio |
| `SMTP_HOST` | SMTP server hostname |
| `SMTP_PORT` | SMTP server port (default: 587) |
| `SMTP_USER` | SMTP username |
| `SMTP_PASSWORD` | SMTP password |
| `ETHICS_COMMITTEE_EMAIL` | Email address for ethics committee notifications |
| `DATABASE_URL` | Database connection string |
| `ARCHIVE_DIR` | Directory for archived documents |
| `AUDIO_UPLOAD_DIR` | Directory for uploaded audio files |

## API Endpoints

### Audio Processing
- `POST /api/meetings/upload` - Upload audio and start processing
- `GET /api/meetings/{meeting_id}/status` - Get processing status
- `GET /api/meetings/{meeting_id}/summary` - Get meeting summary
- `GET /api/meetings/{meeting_id}/gene-loci` - Get gene loci discussed

### Meetings
- `GET /api/meetings` - List all meetings

### Archives
- `GET /api/archives` - Search archived documents
- `GET /api/archives/{archive_id}` - Get archive record

## Workflow Pipeline

The Luigi workflow processes meetings in these stages:

1. **ProcessAudioTask** - Noise reduction using librosa
2. **TranscribeAudioTask** - Speech-to-text with Whisper
3. **DiarizeSpeakersTask** - Speaker separation with pyannote
4. **GenerateSummaryTask** - AI-powered structured summary
5. **SendInitialEmailTask** - Notify ethics committee
6. **RequestReviewsTask** - Send review requests
7. **ArchiveArtifactsTask** - Archive all documents to compliance system

## Gene Loci Visualization

The genome browser displays:
- Chromosome selection dropdown
- Visual representation of chromosome bands
- Gene positions with interactive tooltips
- Detailed gene information and discussion points
- Click-to-navigate between genes

## License

This project is for research and educational purposes.
