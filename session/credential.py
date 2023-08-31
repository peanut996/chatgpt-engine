import asyncio
import logging

import httpx
from revChatGPT.V1 import AsyncChatbot as ChatGPTBot


class Credential:
    def __init__(self, email, password, access_token=None, refresh_token=None, conversation_id=None, verbose=False):
        self.email = email
        self.password = password
        self.conversation_id = conversation_id
        self.lock = None
        self.verbose = verbose
        self.refresh_token = refresh_token
        logging.info("[Credential] init: {}".format(email))
        if refresh_token is not None:
            self.refresh_access_token()
        else:
            self.chat_gpt_bot = ChatGPTBot(config={
                'email': email,
                'password': password,
                'access_token': access_token,
                'verbose': verbose,
            }, conversation_id=conversation_id)

    def set_verbose(self, verbose):
        self.verbose = verbose
        self.chat_gpt_bot.verbose = verbose

    def refresh_access_token(self):
        if not self.refresh_token:
            return
        try:
            access_token = Credential.get_refreshed_token(self.refresh_token)
            if access_token is None:
                raise Exception("empty access token")
            self.chat_gpt_bot = ChatGPTBot(config={
                'email': self.email,
                'password': self.password,
                'access_token': access_token,
                'verbose': self.verbose,
            }, conversation_id=self.conversation_id)
            logging.info("[RefreshToken] access token refreshed: {}".format(self.email))
        except Exception as e:
            logging.error("[RefreshToken] refresh token failed" + str(e))

    @staticmethod
    def get_refreshed_token(refresh_token) -> str:
        url = "https://auth0.openai.com/oauth/token"
        headers = {
            'Content-Type': 'application/json',
        }
        data = {
            "redirect_uri": "com.openai.chat://auth0.openai.com/ios/com.openai.chat/callback",
            "grant_type": "refresh_token",
            "client_id": "pdlLIX2Y72MIl2rhLhTE9VV9bN905kBh",
            "refresh_token": refresh_token
        }
        r = httpx.post(url, json=data, headers=headers)
        return r.json()['access_token']

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
