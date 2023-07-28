import asyncio
import logging

from revChatGPT.V1 import AsyncChatbot as ChatGPTBot


class Credential:
    def __init__(self, email, password, access_token=None, conversation_id=None,  verbose=False):
        self.email = email
        self.password = password
        self.conversation_id = conversation_id
        self.lock = None
        self.verbose = verbose
        logging.info("[Credential] init: {}".format(email))
        self.chat_gpt_bot = ChatGPTBot(config={
            'email': email,
            'password': password,
            'access_token': access_token,
            'verbose': verbose,
        }, conversation_id=conversation_id)

    def set_verbose(self, verbose):
        self.verbose = verbose
        self.chat_gpt_bot.verbose = verbose

    def refresh_token(self):
        self.chat_gpt_bot = ChatGPTBot(config={
            'email': self.email,
            'password': self.password,
            'verbose': self.verbose,
        }, conversation_id=self.conversation_id)
        logging.info("ChatGPTBot token refreshed: {}".format(self.email))

    @staticmethod
    def parse(credential_str: str):
        credential = credential_str.split(":")
        length = len(credential)
        if length != 2 and length != 3 and length != 4:
            raise Exception("token format error")
        if length == 2:
            return Credential(credential[0], credential[1])
        elif length == 3:
            return Credential(credential[0], credential[1], credential[2])
        else:
            return Credential(credential[0], credential[1], credential[2], credential[3])
