import ssl
import certifi
from django.core.mail.backends.smtp import EmailBackend as DjangoSMTPEmailBackend


class EmailBackend(DjangoSMTPEmailBackend):
    @property
    def ssl_context(self):
        context = ssl.create_default_context(cafile=certifi.where())
        if self.ssl_certfile or self.ssl_keyfile:
            context.load_cert_chain(self.ssl_certfile, self.ssl_keyfile)
        return context