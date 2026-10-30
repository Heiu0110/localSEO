from alembic import context

from app.db.models import Base
from app.ai import models as ai_models
from app.research import models as research_models
from app.visibility import models as visibility_models
from app.visibility import live_models as visibility_live_models
from app.keywords import models as keyword_models
from app.technical import models  # Register additive models for future autogeneration.

connection = context.config.attributes.get("connection")
if connection is None:
    from app.db.database import Database
    with Database().engine.begin() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
else:
    context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()
