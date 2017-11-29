import asyncio
import logging
import time
import typing

from faker import Faker

from threat9_test_bed.scenarios import TelnetScenario

logger = logging.getLogger(__name__)
faker = Faker()


def authorized(func):
    def _wrapper(self, data):
        message = data.decode().strip()
        if not self.authorized:
            if not self.login:
                self.login = message
                self.transport.write(b"Password: ")
                return
            else:
                self.password = message

            if (self.login, self.password) in self.creds:
                self.authorized = True
                self.transport.write(self.prompt.encode())
            else:
                self.transport.write(b"\r\nLogin incorrect\r\ntarget login: ")
                self.login = None
                self.password = None
            return
        else:
            func(self, data)

    return _wrapper


class GreedyTuple(tuple):
    def __contains__(self, item):
        return True


class TelnetServerClientProtocol(asyncio.Protocol):
    def __init__(self, scenario: TelnetScenario):
        self.transport = None
        self.remote_address = None
        self.scenario = scenario

        self.login = None
        self.password = None
        self.authorized = False

        self._command_mocks = {}

        if self.scenario == TelnetScenario.NOT_AUTHORIZED:
            self.creds = ()
        elif self.scenario == TelnetScenario.AUTHORIZED:
            self.creds = GreedyTuple()
        elif self.scenario == TelnetScenario.GENERIC:
            self.creds = (
                ("admin", "admin"),
                ("kocia", "dupa"),
            )
        else:
            raise ValueError("You have to pass valid login scenario!")

    @property
    def prompt(self):
        return f"{self.login}@target:~$ "

    def connection_made(self, transport: asyncio.Transport):
        if self.scenario == TelnetScenario.TIMEOUT:
            time.sleep(60 * 60)

        self.remote_address = transport.get_extra_info('peername')
        self.transport = transport
        self.transport.write(b"Login: ")
        logger.debug(f"Connection from {self.remote_address}")

    @authorized
    def data_received(self, data: bytes):
        logger.debug(f'{self.remote_address} send: {data}')
        command = data.decode().strip()
        handler = self._command_mocks.get(
            command, lambda: faker.paragraph(variable_nb_sentences=True)
        )
        self.transport.write(
            f"{handler()}\r\n"f"{self.prompt}".encode()
        )

    def add_command_handler(self, command: str, handler: typing.Callable):
        self._command_mocks[command] = handler