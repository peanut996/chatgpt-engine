import asyncio
import json
import traceback
from dataclasses import dataclass

from OpenAIAuth import Error as OpenAIError
from quart import Quart, request, make_response
from revChatGPT.typings import Error as ChatGPTError

from session.session import Session

app = Quart(__name__)
session: Session



STREAM_TIMEOUT = 'app_quart_stream_timeout'
STREAM_DONE = 'app_quart_stream_done'


@dataclass
class ServerSentEvent:
    data: str
    event: str = 'event'
    id: int = None
    retry: int = None

    def encode(self) -> bytes:
        if self.data != '[DONE]' and self.data != '[START]' and self.data != '[KEEP]':
            self.data = json.dumps({
                'message': self.data,
            })
        message = f"data: {self.data}"
        if self.event is not None:
            message = f"{message}\nevent: {self.event}"
        if self.id is not None:
            message = f"{message}\nid: {self.id}"
        if self.retry is not None:
            message = f"{message}\nretry: {self.retry}"
        message = f"{message}\r\n\r\n"
        return message.encode('utf-8')

    @staticmethod
    def done_event():
        return ServerSentEvent("[DONE]", event="event")

    @staticmethod
    def start_event():
        return ServerSentEvent("[START]", event="event")

    @staticmethod
    def keep_event():
        return ServerSentEvent("[KEEP]", event="event")


@app.route('/chat', methods=["GET"])
async def chat():
    sentence = request.args.get("sentence")
    user_id = request.args.get("user_id")
    model = request.args.get("model") or 'text-davinci-002-render-sha'
    if model not in ['gpt-4', 'text-davinci-002-render-sha', 'text-davinci-002-render-paid']:
        raise Exception("model not supported")
    try:
        res = await session.chat_with_chatgpt(sentence, user_id=user_id, model=model)
        return {"message": res}
    except OpenAIError as e:
        app.logger.error(
            "[Engine] chat gpt engine get open api error: status: {}, details: {}".format(e.status_code, e.details))
        return {"detail": e.details, "code": e.status_code}
    except ChatGPTError as e:
        app.logger.error("[Engine] chat gpt engine get chat gpt error: {}".format(e.message))
        return {"detail": e.message, "code": e.code}
    except Exception as e:
        app.logger.error(f"[Engine] chat gpt engine get error: {traceback.format_exc()}")
        return {"detail": str(e) if len(str(e)) != 0 else "Internal Server Error", "code": 500}


@app.route('/chat-stream', methods=["POST"])
async def chat_stream():
    request_data = await request.get_json()
    sentence = request_data.get("sentence")
    user_id = request_data.get("user_id")
    model = request_data.get("model") or 'text-davinci-002-render-sha'
    if model not in ['gpt-4', 'text-davinci-002-render-sha', 'text-davinci-002-render-paid']:
        raise Exception("model not supported")
    start_time = asyncio.get_event_loop().time()

    async def send_events():
        should_stop = False

        async def put_stream_to_queue(stream, queue):
            try:
                async for message in stream:
                    if should_stop is True:
                        break
                    await queue.put(message)
            except ChatGPTError as e:
                await queue.put(e.message)
            except OpenAIError as exception:
                await queue.put(exception.details)
            except Exception as exception:
                msg = str(exception) if len(str(exception)) != 0 else "Internal Server Error"
                await queue.put(msg)
            finally:
                await queue.put(STREAM_DONE)

        try:
            yield ServerSentEvent.start_event().encode()

            stream_generator = session.chat_stream_with_chatgpt(sentence, user_id=user_id, model=model)
            queue = asyncio.Queue()
            asyncio.create_task(put_stream_to_queue(stream_generator, queue))

            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=12)
                except asyncio.TimeoutError:
                    message = STREAM_TIMEOUT

                if queue.empty() and message is STREAM_DONE:
                    break
                if message is STREAM_TIMEOUT:
                    current_time = asyncio.get_event_loop().time()
                    if current_time - start_time > 120:
                        should_stop = True
                        app.logger.warning("[Engine] chat gpt engine get stream timeout")
                        yield ServerSentEvent(
                            "😱 机器人负载过多，请稍后再试(The robot is overwhelmed, please try again later)").encode()
                        break
                    yield ServerSentEvent.keep_event().encode()
                else:
                    yield ServerSentEvent(message).encode()
        finally:
            yield ServerSentEvent.done_event().encode()

    response = await make_response(
        send_events(),
        {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache, no-transform',
            'Transfer-Encoding': 'chunked',
        },
    )
    response.timeout = None
    return response


@app.route('/ping')
def ping():
    return "pong"


def set_session(s: Session):
    global session
    session = s
