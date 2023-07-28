import time
from .credential import Credential


class UserSession:

    def __init__(self, user_id, conversation_id=None, parent_id=None, credential: Credential = None):
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.parent_id = parent_id
        self.last_time = time.time()
        self.credential = credential

    def update(self, parent_id=None, conversation_id=None):
        self.last_time = time.time()
        self.parent_id = parent_id
        self.conversation_id = conversation_id or self.conversation_id
