from contextlib import contextmanager
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
from time import monotonic, sleep

import pymysql
import pytest
from sqlalchemy import URL, create_engine


ROOT = Path(__file__).resolve().parents[1]
WINDOWS_MYSQL = Path("C:/Program Files/MySQL/MySQL Server 8.0/bin")


def mysql_executable(name):
    directory = os.environ.get("DIPPIE_TEST_MYSQL_BIN")
    if directory:
        executable = Path(directory) / (name + ".exe" if os.name == "nt" else name)
    else:
        location = shutil.which(name)
        executable = Path(location) if location else WINDOWS_MYSQL / (name + ".exe")
    if not executable.is_file():
        raise RuntimeError(f"Không tìm thấy {name}. Đặt DIPPIE_TEST_MYSQL_BIN tới thư mục bin của MySQL 8.0.")
    return str(executable.resolve())


class MySQLSandbox:
    def __init__(self, home):
        self.home = home
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            self.port = listener.getsockname()[1]
        self.password = ""
        self.flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.ini = home / "client.ini"
        self.server = None

    def connection(self, database=None, user="root", password=None):
        return pymysql.connect(
            host="127.0.0.1", port=self.port, user=user, password=self.password if password is None else password,
            database=database, charset="utf8mb4", autocommit=True, connect_timeout=2,
        )

    def start(self):
        mysqld = mysql_executable("mysqld")
        command = [mysqld, "--no-defaults", f"--datadir={self.home / 'data'}", "--character-set-server=utf8mb4",
                   "--collation-server=utf8mb4_unicode_ci"]
        if os.name == "nt":
            command.append(f"--basedir={Path(mysqld).parent.parent}")
        with (self.home / "mysqld.log").open("wb") as log:
            subprocess.run([*command, "--initialize-insecure"], stdout=log, stderr=subprocess.STDOUT,
                           check=True, timeout=65, creationflags=self.flags)
            self.server = subprocess.Popen(
                [*command, "--console", "--bind-address=127.0.0.1", f"--port={self.port}",
                 "--mysqlx=OFF", "--skip-log-bin"],
                stdout=log, stderr=subprocess.STDOUT, creationflags=self.flags,
            )
        deadline = monotonic() + 25
        while self.server.poll() is None:
            try:
                admin = self.connection()
            except pymysql.OperationalError:
                if monotonic() >= deadline:
                    break
                sleep(0.25)
            else:
                with admin, admin.cursor() as cursor:
                    cursor.execute("SELECT VERSION()")
                    version = cursor.fetchone()[0]
                    assert version.startswith("8.0."), version
                    password = secrets.token_hex(32)
                    cursor.execute("ALTER USER CURRENT_USER() IDENTIFIED BY %s", (password,))
                    self.password = password
                self.ini.write_text("[client]\npassword=" + self.password + "\n", encoding="ascii")
                return
        raise RuntimeError(f"MySQL không khởi động được. Nhật ký ở {self.home / 'mysqld.log'}.")

    def close(self):
        if not self.server or self.server.poll() is not None:
            return
        try:
            with self.connection() as admin, admin.cursor() as cursor:
                cursor.execute("SHUTDOWN")
            self.server.wait(timeout=15)
        except (pymysql.MySQLError, subprocess.TimeoutExpired):
            self.server.terminate()
            self.server.wait(timeout=10)

    @contextmanager
    def schema(self):
        name = "dippie_test_" + secrets.token_hex(8)
        with self.connection() as admin, admin.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        engine = create_engine(URL.create(
            "mysql+pymysql", username="root", password=self.password, host="127.0.0.1",
            port=self.port, database=name, query={"charset": "utf8mb4"},
        ))
        try:
            yield engine
        finally:
            engine.dispose()
            with self.connection() as admin, admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{name}`")

    def run_sql(self, name, source, *, check=True, env=None, timeout=80):
        script = source.read_bytes() if isinstance(source, Path) else source.encode("utf-8")
        result = subprocess.run(
            [mysql_executable("mysql"), f"--defaults-extra-file={self.ini}", "--host=127.0.0.1",
             f"--port={self.port}", "--user=root", "--default-character-set=utf8mb4", "--batch", name],
            input=script, capture_output=True, timeout=timeout, env=env, creationflags=self.flags,
        )
        if check and result.returncode:
            raise AssertionError(result.stderr.decode("utf-8", errors="replace"))
        return result


@pytest.fixture(scope="session")
def mysql_database(tmp_path_factory):
    if os.environ.get("DIPPIE_RUN_MYSQL_TESTS") != "1":
        pytest.skip("Đặt DIPPIE_RUN_MYSQL_TESTS=1 để chạy kiểm thử MySQL 8.0.")
    sandbox = MySQLSandbox(tmp_path_factory.mktemp("mysql-server"))
    try:
        sandbox.start()
        yield sandbox
    finally:
        sandbox.close()
