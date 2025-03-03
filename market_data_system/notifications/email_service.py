import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content
import json
from datetime import datetime
import pytz

from common.utils.config import settings
from common.logging.logger import get_logger
from common.db.mongodb import mongodb

logger = get_logger(__name__)


class EmailService:
    def __init__(self):
        self.sg = sendgrid.SendGridAPIClient(api_key=settings.sendgrid_api_key)
        self.from_email = Email(settings.alert_email_from)
        self.to_email = To(settings.alert_email_to)

    def send_email(self, subject, content_html, to_email=None):
        """Send an email."""
        if not to_email:
            to_email = self.to_email
        else:
            to_email = To(to_email)

        mail = Mail(
            from_email=self.from_email,
            to_emails=to_email,
            subject=subject,
            html_content=Content("text/html", content_html),
        )

        try:
            response = self.sg.client.mail.send.post(request_body=mail.get())
            logger.info(f"Email sent: {subject} (Status: {response.status_code})")

            # Log the notification
            mongodb.log_notification(
                notification_type="email",
                recipient=to_email.email,
                subject=subject,
                body=content_html,
            )

            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def send_system_startup_notification(self):
        """Send a system startup notification."""
        lagos_tz = pytz.timezone(settings.timezone)
        now = datetime.now(lagos_tz)

        subject = f"Market Data System Started - {now.strftime('%Y-%m-%d %H:%M:%S')}"

        content = f"""
        <h2>Market Data System Startup</h2>
        <p>The market data collection system has started successfully.</p>
        <p><strong>Time:</strong> {now.strftime('%Y-%m-%d %H:%M:%S')} WAT</p>
        <p>All data collection services are now running.</p>
        <p>You can access the monitoring dashboard at: <a href="http://your-ec2-ip:8000">http://your-ec2-ip:8000</a></p>
        """

        return self.send_email(subject, content)

    def send_system_shutdown_notification(self):
        """Send a system shutdown notification."""
        lagos_tz = pytz.timezone(settings.timezone)
        now = datetime.now(lagos_tz)

        subject = f"Market Data System Shutdown - {now.strftime('%Y-%m-%d %H:%M:%S')}"

        content = f"""
        <h2>Market Data System Shutdown</h2>
        <p>The market data collection system has shut down.</p>
        <p><strong>Time:</strong> {now.strftime('%Y-%m-%d %H:%M:%S')} WAT</p>
        <p>All data collection services have been stopped.</p>
        <p>The system will restart automatically for the next market session.</p>
        """

        return self.send_email(subject, content)

    def send_new_symbol_notification(self, symbol):
        """Send a notification about a new symbol."""
        lagos_tz = pytz.timezone(settings.timezone)
        now = datetime.now(lagos_tz)

        subject = f"New Symbol Detected: {symbol} - {now.strftime('%Y-%m-%d')}"

        content = f"""
        <h2>New Symbol Detected</h2>
        <p>A new symbol has been detected in the NGX data feed.</p>
        <p><strong>Symbol:</strong> {symbol}</p>
        <p><strong>Time:</strong> {now.strftime('%Y-%m-%d %H:%M:%S')} WAT</p>
        <p>This symbol is not currently in your database. Please add it to your system if appropriate.</p>
        """

        return self.send_email(subject, content)

    def send_inactive_symbol_notification(self, symbol, reason):
        """Send a notification about an inactive symbol."""
        lagos_tz = pytz.timezone(settings.timezone)
        now = datetime.now(lagos_tz)

        subject = f"Symbol Inactive: {symbol} - {now.strftime('%Y-%m-%d')}"

        content = f"""
        <h2>Symbol Inactive</h2>
        <p>A symbol in your database is no longer active.</p>
        <p><strong>Symbol:</strong> {symbol}</p>
        <p><strong>Reason:</strong> {reason}</p>
        <p><strong>Time:</strong> {now.strftime('%Y-%m-%d %H:%M:%S')} WAT</p>
        <p>The symbol has been marked as inactive in the system.</p>
        """

        return self.send_email(subject, content)

    def send_process_completion_notification(self, process_name, details=None):
        """Send a notification about a completed process."""
        lagos_tz = pytz.timezone(settings.timezone)
        now = datetime.now(lagos_tz)

        subject = (
            f"Process Complete: {process_name} - {now.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        content = f"""
        <h2>Process Completion</h2>
        <p>The following process has completed successfully:</p>
        <p><strong>Process:</strong> {process_name}</p>
        <p><strong>Time:</strong> {now.strftime('%Y-%m-%d %H:%M:%S')} WAT</p>
        """

        if details:
            content += f"<p><strong>Details:</strong> {details}</p>"

        return self.send_email(subject, content)

    def send_error_notification(self, component, error_message, stack_trace=None):
        """Send a notification about an error."""
        lagos_tz = pytz.timezone(settings.timezone)
        now = datetime.now(lagos_tz)

        subject = f"ERROR: {component} - {now.strftime('%Y-%m-%d %H:%M:%S')}"

        content = f"""
        <h2>Error Detected</h2>
        <p>An error has occurred in the market data system.</p>
        <p><strong>Component:</strong> {component}</p>
        <p><strong>Error:</strong> {error_message}</p>
        <p><strong>Time:</strong> {now.strftime('%Y-%m-%d %H:%M:%S')} WAT</p>
        """

        if stack_trace:
            content += (
                f"<p><strong>Stack Trace:</strong><br><pre>{stack_trace}</pre></p>"
            )

        return self.send_email(subject, content)


# Create a singleton instance
email_service = EmailService()
