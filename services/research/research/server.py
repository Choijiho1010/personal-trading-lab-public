import logging

from .http_adapter import create_server


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    with create_server() as server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
