from django.db import models

from .crypto import ENCRYPTED_PREFIX, decrypt_message, encrypt_message


class EncryptedTextField(models.TextField):
    description = "Text encrypted at rest with the chat message key"

    def from_db_value(self, value, expression, connection):
        if value is None or not value.startswith(ENCRYPTED_PREFIX):
            return value
        return decrypt_message(value)

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None or value == "" or value.startswith(ENCRYPTED_PREFIX):
            return value
        return encrypt_message(value)
