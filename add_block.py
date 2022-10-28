from sqlalchemy import create_engine
from sqlalchemy.orm import session as session_orm
from sqlalchemy.orm import sessionmaker, scoped_session

from app.models.data import BlockTotal
from app.processors.converters import PolkascanHarvesterService
from app.settings import DB_CONNECTION, DEBUG, TYPE_REGISTRY, TYPE_REGISTRY_FILE, SUBSTRATE_RPC_URL



if __name__ == '__main__':

    print("DB_CONNECTION=%s, DEBUG=%s, TYPE_REGISTRY=%s, TYPE_REGISTRY_FILE=%s" % (DB_CONNECTION, DEBUG, TYPE_REGISTRY, TYPE_REGISTRY_FILE))
    print("SUBSTRATE_RPC_URL=%s" % (SUBSTRATE_RPC_URL))

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

    # ('76743', '83942', '91142', '115127')
    substrate = harvester.substrate
    # block_hash = substrate.get_block_hash(40486) # 40486 是 NewPurchasedRequest 调用区块
    # block_hash = substrate.get_block_hash(571618)  # 40779 是 EndOfAskEra 调用的区块
    # block_hash = substrate.get_block_hash(571611)
    # block_hash = substrate.get_block_hash(714888)
    # block_hash = substrate.get_block_hash(724954)
    # block_hash = substrate.get_block_hash(724304)
    # block_hash = substrate.get_block_hash(682743)
    # block_hash = substrate.get_block_hash(788001)
    # block_hash = substrate.get_block_hash(772113)
    # block_hash = substrate.get_block_hash(784120)
    # block_hash = substrate.get_block_hash(1068187)
    # block_hash = substrate.get_block_hash(1053563)

    # completed block number = 1059601

    # new block number = 	icp-usdt / 1068157
    # block_hash = substrate.get_block_hash(1068157)

    # completed block number = icp-usdt  / 	1078301
    # block_hash = substrate.get_block_hash(1078301)

    # Fix bug 20221018-1 BEGIN: 1150336
    # block_hash = substrate.get_block_hash(1150336)

    # Fix bug 20221018-1 END: 1150401
    # block_hash = substrate.get_block_hash(1150401)

    # block_hash = substrate.get_block_hash(1237331)
    # block_hash = substrate.get_block_hash(1237338)
    # block_hash = substrate.get_block_hash(1237359)

    block_hash = substrate.get_block_hash(1325845)
    # block_hash = substrate.get_block_hash(1325941)

    substrate.init_runtime(block_hash=block_hash)
    block = harvester.add_block(block_hash=block_hash)
    harvester.sequence_block(block)
    # harvester.debug_task()

    session.commit()
    session.close()
