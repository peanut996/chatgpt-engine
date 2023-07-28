import asyncio
import logging
import random
import time
from typing import List, Dict, AsyncGenerator

import OpenAIAuth
from httpx import HTTPStatusError
from revChatGPT.typings import Error as ChatGPTError

from revChatGPT.typings import ErrorType as ChatGPTErrorType

from .credential import Credential
from .user_session import UserSession


class Session:
    def __init__(self, config):
        self.used_chatgpt_credentials_indexes = []
        try:
            self.chatgpt_credentials: List[Credential] = list(
                map(Credential.parse, config["engine"]["chatgpt"]["tokens"]))
        except OpenAIAuth.Error as e:
            logging.error("Init Credential Error: status: {}, details: {}".format(e.status_code, e.details))
            raise e
        self.chat_gpt_bot = None
        self.edge_gpt_bot = None
        self.user_to_session: Dict[str, UserSession] = dict()
        self.user_to_paid_session: Dict[str, UserSession] = dict()
        self.user_to_gpt4_session: Dict[str, UserSession] = dict()

        self.verbose = config['engine'].get('debug', False)
        for c in self.chatgpt_credentials:
            c.set_verbose(self.verbose)

    def _get_random_chat_gpt_credential(self):
        length_range = len(self.chatgpt_credentials) - 1
        index = random.randint(0, length_range)
        while index in self.used_chatgpt_credentials_indexes:
            if len(self.used_chatgpt_credentials_indexes) == len(self.chatgpt_credentials):
                self.used_chatgpt_credentials_indexes = []
            index = random.randint(0, length_range)

        self.used_chatgpt_credentials_indexes.append(index)
        return self.chatgpt_credentials[index]

    def _clean_session(self, user_id):
        if user_id is None:
            return
        try:
            del self.user_to_gpt4_session[user_id]
        except Exception as _:
            pass

        try:
            del self.user_to_session[user_id]
        except Exception as _:
            pass

    def _get_user_session(self, user_id) -> UserSession:
        if user_id in self.user_to_session:
            return self.user_to_session[user_id]
        else:
            credential = self._get_random_chat_gpt_credential()
            session = UserSession(user_id=user_id, credential=credential)
            self.user_to_session[user_id] = session
            return session

    def _get_user_paid_session(self, user_id) -> UserSession:
        if user_id in self.user_to_paid_session:
            return self.user_to_paid_session[user_id]
        else:
            credential = self._get_random_chat_gpt_credential()
            session = UserSession(user_id=user_id, credential=credential)
            self.user_to_paid_session[user_id] = session
            return session

    def _get_session_from_model_and_id(self, user_id, model='text-davinci-002-render-sha'):
        if model == 'gpt-4':
            return self._get_user_gpt4_session(user_id)
        elif model == 'text-davinci-002-render-paid':
            return self._get_user_paid_session(user_id)
        else:
            return self._get_user_session(user_id)

    def _get_user_gpt4_session(self, user_id) -> UserSession:
        if user_id in self.user_to_gpt4_session:
            return self.user_to_gpt4_session[user_id]
        else:
            credential = self._get_random_chat_gpt_credential()
            session = UserSession(user_id=user_id, credential=credential)
            self.user_to_gpt4_session[user_id] = session
            return session

    def _get_credential_from_session(self, session: UserSession):
        if time.time() - session.last_time > 60 * 5:
            credential = self._get_random_chat_gpt_credential()
            session.credential = credential
        return session.credential

    async def chat_with_chatgpt(self, sentence: str, user_id=None, model='text-davinci-002-render-sha') -> str:
        session = self._get_session_from_model_and_id(user_id, model)
        credential = self._get_credential_from_session(session)
        credential.chat_gpt_bot.conversation_id = None

        if credential.lock is None:
            credential.lock = asyncio.Lock()

        async with credential.lock:
            try:
                if model is not None:
                    credential.chat_gpt_bot.config['model'] = model
                else:
                    credential.chat_gpt_bot.config['model'] = None
                res = ""
                prev_text = ""
                conversation_id = session.conversation_id
                parent_id = session.parent_id
                logging.info(
                    f"[Session] ask open ai user {user_id}, model: {model}, sentence: {sentence}, " +
                    f"conversation_id: {conversation_id}, parent_id: {parent_id} ")
                async for data in credential.chat_gpt_bot.ask(sentence,
                                                              conversation_id=conversation_id,
                                                              parent_id=parent_id):
                    message = data["message"][len(prev_text):]
                    res += message
                    prev_text = data["message"]
                    conversation_id = data["conversation_id"]
                    parent_id = data["parent_id"]
                if len(res) == 0:
                    raise Exception("empty response")
                session.update(conversation_id=conversation_id, parent_id=parent_id)
                return res
            except ChatGPTError as e:
                credential.refresh_token()
                self._clean_session(user_id)
                logging.error("[Engine] chat gpt engine get chat gpt error: {}".format(e.message))
                error_code = e.code
                if error_code >= 500:
                    e.code = ChatGPTErrorType.SERVER_ERROR
                    e.message = "OpenAI Server Error"
                elif error_code == 429:
                    e.code = ChatGPTErrorType.RATE_LIMIT_ERROR
                    e.message = "Too many requests, please retry later"
                elif error_code == ChatGPTErrorType.EXPIRED_ACCESS_TOKEN_ERROR or \
                        error_code == ChatGPTErrorType.INVALID_ACCESS_TOKEN_ERROR:
                    e.message = "OpenAI Token Invalid, please retry"
                else:
                    e.code = ChatGPTErrorType.UNKNOWN_ERROR
                    e.message = "Unknown Error"
                raise e
            except HTTPStatusError as e:
                if e.response.status_code == 429:
                    message = "😱 机器人负载过多，请稍后再试"
                    raise ChatGPTError(source="chat_with_chatgpt", message=message)
                elif e.response.status_code >= 500:
                    raise ChatGPTError(source="chat_with_chatgpt", message="OpenAI Server Error")
            except Exception as e:
                credential.refresh_token()
                self._clean_session(user_id)
                logging.error("ChatGPTBot error: {}".format(e))
                raise e

    async def chat_stream_with_chatgpt(self, sentence: str, user_id=None, model='text-davinci-002-render-sha') -> AsyncGenerator[str, None]:
        session = self._get_session_from_model_and_id(user_id, model)
        credential = self._get_credential_from_session(session)
        credential.chat_gpt_bot.conversation_id = None

        if credential.lock is None:
            credential.lock = asyncio.Lock()

        async with credential.lock:
            try:
                if model is not None:
                    credential.chat_gpt_bot.config['model'] = model
                else:
                    credential.chat_gpt_bot.config['model'] = None
                prev_text = ""
                conversation_id = session.conversation_id
                parent_id = session.parent_id
                logging.info(
                    f"[Session] ask open ai user {user_id}, model: {model}, sentence: {sentence}, " +
                    f"conversation_id: {conversation_id}, parent_id: {parent_id} ")
                async for data in credential.chat_gpt_bot.ask(sentence,
                                                              conversation_id=conversation_id,
                                                              parent_id=parent_id):
                    message = data["message"][len(prev_text):]
                    prev_text = data["message"]
                    conversation_id = data["conversation_id"]
                    parent_id = data["parent_id"]
                    session.update(conversation_id=conversation_id, parent_id=parent_id)
                    yield message

            except ChatGPTError as e:
                credential.refresh_token()
                self._clean_session(user_id)
                logging.error("[Engine] chat gpt engine get chat gpt error: {}".format(e.message))
                error_code = e.code
                if error_code >= 500:
                    e.code = ChatGPTErrorType.SERVER_ERROR
                    e.message = "OpenAI Server Error"
                elif error_code == 429:
                    e.code = ChatGPTErrorType.RATE_LIMIT_ERROR
                    e.message = "Too many requests, please retry later"
                elif error_code == ChatGPTErrorType.EXPIRED_ACCESS_TOKEN_ERROR or \
                        error_code == ChatGPTErrorType.INVALID_ACCESS_TOKEN_ERROR:
                    e.message = "OpenAI Token Invalid, please retry"
                else:
                    e.code = ChatGPTErrorType.UNKNOWN_ERROR
                    e.message = "Unknown Error"
                raise e
            except HTTPStatusError as e:
                if e.response.status_code == 429:
                    message = "😱 机器人负载过多，请稍后再试(The robot is overwhelmed, please try again later)"
                    raise ChatGPTError(source="chat_with_chatgpt", message=message)
                elif e.response.status_code >= 500:
                    raise ChatGPTError(source="chat_with_chatgpt", message="OpenAI Server Error")
            except Exception as e:
                credential.refresh_token()
                self._clean_session(user_id)
                logging.error("ChatGPTBot error: {}".format(e))
                raise e
