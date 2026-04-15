from typing import Protocol
from sqlalchemy import Table
from theseus.keel.blueprint_engine.models import Blueprint


class SchemaGeneratorProtocol(Protocol):
    """Protocol for generating SQLAlchemy tables from Blueprints."""
    def generate_table(self, blueprint: Blueprint) -> Table: ...
