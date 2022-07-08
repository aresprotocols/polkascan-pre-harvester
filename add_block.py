from sqlalchemy import create_engine
from sqlalchemy.orm import session as session_orm
from sqlalchemy.orm import sessionmaker, scoped_session

from app.processors.converters import PolkascanHarvesterService
from app.settings import DB_CONNECTION, DEBUG, TYPE_REGISTRY, TYPE_REGISTRY_FILE

if __name__ == '__main__':

    print("DB_CONNECTION=%s, DEBUG=%s, TYPE_REGISTRY=%s, TYPE_REGISTRY_FILE=%s" % (DB_CONNECTION, DEBUG, TYPE_REGISTRY, TYPE_REGISTRY_FILE))



    # module_id = SystemNewAccountEventProcessor.module_id
    # event_id = SystemNewAccountEventProcessor.event_id
    engine = create_engine(DB_CONNECTION, echo=DEBUG, isolation_level="READ_UNCOMMITTED", pool_pre_ping=True)
    session_factory = sessionmaker(engine, autoflush=False, autocommit=False)
    scoped_session = scoped_session(session_factory)
    session: session_orm = scoped_session()
    harvester = PolkascanHarvesterService(
        db_session=session,
        type_registry=TYPE_REGISTRY,
        type_registry_file=TYPE_REGISTRY_FILE
    )
    substrate = harvester.substrate
    block_hash = substrate.get_block_hash(330)
    substrate.init_runtime(block_hash=block_hash)
    harvester.add_block(block_hash=block_hash)
    session.commit()
    session.close()