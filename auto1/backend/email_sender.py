import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.utils import formataddr
from typing import List, Optional, Dict
import logging
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class EmailConfig:
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    use_tls: bool = True
    sender_name: str = "Ethics Symposium Minutes System"


class EmailSender:
    def __init__(self, config: Optional[EmailConfig] = None):
        self.config = config or self._load_config_from_env()

    def _load_config_from_env(self) -> EmailConfig:
        return EmailConfig(
            smtp_host=os.environ.get('SMTP_HOST', 'smtp.example.com'),
            smtp_port=int(os.environ.get('SMTP_PORT', 587)),
            smtp_user=os.environ.get('SMTP_USER', ''),
            smtp_password=os.environ.get('SMTP_PASSWORD', ''),
            use_tls=os.environ.get('SMTP_USE_TLS', 'true').lower() == 'true',
            sender_name=os.environ.get('SMTP_SENDER_NAME', 'Ethics Symposium Minutes System')
        )

    def send_summary_email(
        self,
        to_emails: List[str],
        summary_markdown: str,
        summary_json_path: Optional[str] = None,
        meeting_id: str = "unknown",
        meeting_title: str = "Gene Editing Ethics Symposium",
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None
    ) -> bool:
        logger.info(f"Sending summary email for meeting {meeting_id} to {len(to_emails)} recipients")
        
        try:
            msg = MIMEMultipart()
            msg['From'] = formataddr((self.config.sender_name, self.config.smtp_user))
            msg['To'] = ', '.join(to_emails)
            if cc_emails:
                msg['Cc'] = ', '.join(cc_emails)
            if bcc_emails:
                msg['Bcc'] = ', '.join(bcc_emails)
            msg['Subject'] = f"[Ethics Minutes] {meeting_title} - Meeting Summary"
            
            html_body = self._generate_html_email(summary_markdown, meeting_title, meeting_id)
            msg.attach(MIMEText(html_body, 'html'))
            
            if summary_json_path and os.path.exists(summary_json_path):
                with open(summary_json_path, 'rb') as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(summary_json_path))
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(summary_json_path)}"'
                msg.attach(part)
            
            all_recipients = to_emails + (cc_emails or []) + (bcc_emails or [])
            
            if self.config.use_tls:
                context = ssl.create_default_context()
                with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                    server.starttls(context=context)
                    server.login(self.config.smtp_user, self.config.smtp_password)
                    server.sendmail(self.config.smtp_user, all_recipients, msg.as_string())
            else:
                with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                    server.login(self.config.smtp_user, self.config.smtp_password)
                    server.sendmail(self.config.smtp_user, all_recipients, msg.as_string())
            
            logger.info(f"Email sent successfully to {len(all_recipients)} recipients")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def _generate_html_email(self, markdown_content: str, meeting_title: str, meeting_id: str) -> str:
        import markdown
        
        html_content = markdown.markdown(
            markdown_content,
            extensions=['tables', 'fenced_code', 'sane_lists']
        )
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{meeting_title} - Meeting Summary</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
                    color: white;
                    padding: 20px;
                    border-radius: 8px;
                    margin-bottom: 20px;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 24px;
                }}
                .meeting-id {{
                    font-size: 12px;
                    opacity: 0.8;
                    margin-top: 8px;
                }}
                .content {{
                    background: white;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                h1, h2, h3, h4 {{
                    color: #1e3a5f;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 15px 0;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 12px;
                    text-align: left;
                }}
                th {{
                    background-color: #f5f5f5;
                    font-weight: bold;
                }}
                tr:nth-child(even) {{
                    background-color: #f9f9f9;
                }}
                .warning {{
                    background-color: #fff3cd;
                    border-left: 4px solid #ffc107;
                    padding: 12px;
                    margin: 15px 0;
                }}
                .danger {{
                    background-color: #f8d7da;
                    border-left: 4px solid #dc3545;
                    padding: 12px;
                    margin: 15px 0;
                }}
                .success {{
                    background-color: #d4edda;
                    border-left: 4px solid #28a745;
                    padding: 12px;
                    margin: 15px 0;
                }}
                hr {{
                    border: none;
                    border-top: 1px solid #eee;
                    margin: 20px 0;
                }}
                .footer {{
                    text-align: center;
                    color: #666;
                    font-size: 12px;
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #eee;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🧬 {meeting_title}</h1>
                <div class="meeting-id">Meeting ID: {meeting_id}</div>
            </div>
            <div class="content">
                {html_content}
            </div>
            <div class="footer">
                <p>This is an automated message from the Ethics Symposium Minutes System.</p>
                <p>Please do not reply directly to this email.</p>
                <p>For questions, contact the Ethics Committee Administrator.</p>
            </div>
        </body>
        </html>
        """
        return html

    def send_review_request(
        self,
        reviewer_email: str,
        review_round: int,
        meeting_id: str,
        meeting_title: str,
        summary_markdown: str,
        deadline: str
    ) -> bool:
        logger.info(f"Sending review request for round {review_round} to {reviewer_email}")
        
        try:
            msg = MIMEMultipart()
            msg['From'] = formataddr((self.config.sender_name, self.config.smtp_user))
            msg['To'] = reviewer_email
            msg['Subject'] = f"[REVIEW REQUIRED] Round {review_round} - {meeting_title} Summary"
            
            review_instructions = f"""
            ## Review Request - Round {review_round}

            You have been requested to review the meeting summary for:
            **{meeting_title}** (Meeting ID: {meeting_id})

            **Review Deadline:** {deadline}

            Please review the following summary and provide your feedback.
            Pay special attention to:
            - Accuracy of technical information
            - Completeness of ethical analysis
            - Appropriateness of recommendations

            The full summary is provided below:

            ---

            {summary_markdown}

            ---

            Please submit your review through the ethics committee portal or reply to this email with your comments.
            """
            
            html_body = self._generate_html_email(review_instructions, f"Review Request - Round {review_round}", meeting_id)
            msg.attach(MIMEText(html_body, 'html'))
            
            if self.config.use_tls:
                context = ssl.create_default_context()
                with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                    server.starttls(context=context)
                    server.login(self.config.smtp_user, self.config.smtp_password)
                    server.sendmail(self.config.smtp_user, [reviewer_email], msg.as_string())
            else:
                with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                    server.login(self.config.smtp_user, self.config.smtp_password)
                    server.sendmail(self.config.smtp_user, [reviewer_email], msg.as_string())
            
            logger.info(f"Review request sent to {reviewer_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send review request: {e}")
            return False
