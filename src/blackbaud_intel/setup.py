"""Set up and tear down the Blackbaud federation prerequisites.

Lakehouse Federation connections and foreign catalogs are not supported as
Databricks Asset Bundle resources, so they are managed here in Python (per the
reusable-IP guidance: use DABs where supported, otherwise Python setup/teardown).

Secret values are never passed here; they must already exist in the secret scope
(populate them out of band, e.g. ``databricks secrets put-secret``). The federation
connection references them with ``secret(...)`` so credentials never appear in code
or logs.
"""

from dataclasses import dataclass

from databricks.sdk import WorkspaceClient


@dataclass(frozen=True)
class FederationConfig:
    """Configuration for the Blackbaud SQL Server federation prerequisites."""

    connection_name: str = "blackbaud_nxt"
    foreign_catalog: str = "blackbaud_nxt_test"
    host: str = "T01readonlyaccess.nxt.blackbaud-test.com"
    port: str = "50101"
    database: str = "5740dbrx"
    secret_scope: str = "blackbaud"
    user_secret_key: str = "bb_user"
    password_secret_key: str = "bb_password"


def _sql(client: WorkspaceClient, warehouse_id: str, statement: str) -> None:
    client.statement_execution.execute_statement(
        warehouse_id=warehouse_id, statement=statement, wait_timeout="50s"
    )


def setup(client: WorkspaceClient, warehouse_id: str, config: FederationConfig | None = None) -> None:
    """Create the federation connection and foreign catalog if they do not exist.

    The secret scope and its ``bb_user`` / ``bb_password`` keys must already exist.

    Args:
        client: Databricks WorkspaceClient for the target workspace.
        warehouse_id: SQL warehouse used to run the DDL.
        config: Federation settings; defaults to the Blackbaud test database.
    """
    config = config or FederationConfig()

    _sql(
        client,
        warehouse_id,
        f"""
        CREATE CONNECTION IF NOT EXISTS {config.connection_name} TYPE sqlserver
        OPTIONS (
          host '{config.host}',
          port '{config.port}',
          user secret('{config.secret_scope}', '{config.user_secret_key}'),
          password secret('{config.secret_scope}', '{config.password_secret_key}')
        )
        """,
    )
    _sql(
        client,
        warehouse_id,
        f"""
        CREATE FOREIGN CATALOG IF NOT EXISTS {config.foreign_catalog}
        USING CONNECTION {config.connection_name}
        OPTIONS (database '{config.database}')
        """,
    )


def teardown(client: WorkspaceClient, warehouse_id: str, config: FederationConfig | None = None) -> None:
    """Drop the foreign catalog and federation connection.

    Args:
        client: Databricks WorkspaceClient for the target workspace.
        warehouse_id: SQL warehouse used to run the DDL.
        config: Federation settings; defaults to the Blackbaud test database.
    """
    config = config or FederationConfig()
    _sql(client, warehouse_id, f"DROP CATALOG IF EXISTS {config.foreign_catalog} CASCADE")
    _sql(client, warehouse_id, f"DROP CONNECTION IF EXISTS {config.connection_name}")
