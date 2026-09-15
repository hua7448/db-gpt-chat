import sys
from unittest.mock import Mock

from sqlalchemy.engine import make_url

from dbgpt_ext.datasource.rdbms.conn_oracle import (
    OracleConnector,
    OracleParameters,
    initialize_oracle_client,
)


def test_service_name_and_special_password():
    params = OracleParameters(
        host="172.16.176.154",
        port=1530,
        user="reader",
        password="test@:/?#",
        service_name="LSRSDB",
        database="LSRSDB",
    )
    url = make_url(params.db_url())
    assert url.password == "test@:/?#"
    assert url.query["service_name"] == "LSRSDB"
    assert url.database is None


def test_thick_initialization_once(monkeypatch):
    driver = Mock()
    driver.is_thin_mode.side_effect = [True, False]
    monkeypatch.setitem(sys.modules, "oracledb", driver)
    monkeypatch.setenv("ORACLE_THICK_MODE", "true")
    initialize_oracle_client()
    initialize_oracle_client()
    driver.init_oracle_client.assert_called_once_with()


def test_11g_database_name():
    connector = Mock()
    connector._engine.dialect.server_version_info = (11, 2, 0, 4)
    session = Mock()
    connector.session_scope.return_value.__enter__ = Mock(return_value=session)
    connector.session_scope.return_value.__exit__ = Mock(return_value=False)
    session.execute.return_value.scalar.return_value = "LSRSDB"
    assert OracleConnector.get_database_names(connector) == ["LSRSDB"]
    sql = str(session.execute.call_args.args[0])
    assert "DB_NAME" in sql and "V$" not in sql
