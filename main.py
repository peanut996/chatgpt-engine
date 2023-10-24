import logging

from route import app, set_session
from session.session import Session
from tool import load_config
from quart_cors import cors
from os import environ


def main():
    environ.setdefault("CHATGPT_BASE_URL", "https://ai.fakeopen.com/api/")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    app.logger.setLevel(logging.INFO)
    config = load_config()
    session = Session(config=config)
    port = config["engine"]["port"]
    debug = config["engine"].get("debug", False)
    set_session(session)

    cors_app = cors(app, allow_origin="*")
    cors_app.run(host="0.0.0.0", port=port, debug=debug)


if __name__ == "__main__":
    main()
