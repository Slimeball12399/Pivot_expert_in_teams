"""Email backend for development (SEND_EMAILS=False).

Django's console backend prints the raw email: the text part, then the HTML
part as quoted-printable and the logos as base64. This one prints only the
headers that matter and the text version, which is what you read the email
(and copy the code) from while developing.
"""

from django.core.mail.backends.console import EmailBackend as ConsoleBackend


class EmailBackend(ConsoleBackend):
    def write_message(self, message):
        self.stream.write(
            f"From:    {message.from_email}\n"
            f"To:      {', '.join(message.to)}\n"
            f"Subject: {message.subject}\n"
            "\n"
            f"{message.body.rstrip()}\n"
        )
        self.stream.write("-" * 79 + "\n")
