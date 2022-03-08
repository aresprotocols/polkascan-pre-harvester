#  Polkascan PRE Harvester
#
#  Copyright 2018-2020 openAware BV (NL).
#  This file is part of Polkascan.
#
#  Polkascan is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Polkascan is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Polkascan. If not, see <http://www.gnu.org/licenses/>.
#
#  tasks.py

import os
import traceback

import celery
from celery.result import AsyncResult
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker, scoped_session

from app import settings
from app.models.data import Block, Account, AccountInfoSnapshot, SearchIndex, SymbolSnapshot, Extrinsic, \
    BlockTotal, Event
from app.models.harvester import Status
from app.processors.converters import PolkascanHarvesterService, HarvesterCouldNotAddBlock, BlockAlreadyAdded
from app.processors.events.treasury.burnt import TreasuryBurnt
from app.settings import DB_CONNECTION, DEBUG, TYPE_REGISTRY, FINALIZATION_ONLY, TYPE_REGISTRY_FILE, \
    MAXIMUM_THREAD

CELERY_BROKER = os.environ.get('CELERY_BROKER')
CELERY_BACKEND = os.environ.get('CELERY_BACKEND')

app = celery.Celery('tasks', broker=CELERY_BROKER, backend=CELERY_BACKEND)
BLOCKS_LIMIT = 100

app.conf.beat_schedule = {
    'check-head-10-seconds': {
        'task': 'app.tasks.start_harvester',
        'schedule': 10.0,
        'args': ()
    },
}

app.conf.timezone = 'UTC'


class BaseTask(celery.Task):

    def __init__(self):
        self.metadata_store = {}

    def __call__(self, *args, **kwargs):
        self.engine = create_engine(DB_CONNECTION, echo=DEBUG, isolation_level="READ_UNCOMMITTED", pool_pre_ping=True)
        session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.scoped_session = scoped_session(session_factory)
        self.session = self.scoped_session()
        self.harvester = PolkascanHarvesterService(
            db_session=self.session,
            type_registry=settings.TYPE_REGISTRY,
            type_registry_file=settings.TYPE_REGISTRY_FILE
        )

        return super().__call__(*args, **kwargs)

    def after_return(self, status, retval, task_id, args, kwargs, einfo):

        if hasattr(self, 'scoped_session'):
            self.scoped_session.remove()
            self.session.close()
        if hasattr(self, 'engine'):
            self.engine.engine.dispose()
        if hasattr(self, 'harvester'):
            self.harvester.substrate.close()


@app.task(base=BaseTask, bind=True)
def accumulate_block_recursive(self, block_hash, end_block_hash=None):
    harvester = self.harvester

    harvester.metadata_store = self.metadata_store
    harvester.substrate.metadata_cache = self.metadata_store

    # If metadata store isn't initialized yet, perform some tests
    # if not harvester.metadata_store:
    #     print('Init: create entrypoints')
    #     # Check if blocks exists
    #     max_block_id = self.session.query(func.max(Block.id)).one()[0]
    #
    #     if not max_block_id:
    #         # Speed up accumulating by creating several entry points
    #         substrate = SubstrateInterface(
    #             url=SUBSTRATE_RPC_URL,
    #             type_registry_preset=settings.TYPE_REGISTRY,
    #             runtime_config=RuntimeConfiguration()
    #         )
    #         block_nr = substrate.get_block_number(block_hash)
    #         if block_nr > 100:
    #             for entry_point in range(0, block_nr, block_nr // 4)[1:-1]:
    #                 entry_point_hash = substrate.get_block_hash(entry_point)
    #                 accumulate_block_recursive.delay(entry_point_hash)

    block = None
    max_sequenced_block_id = False

    add_count = 0

    for nr in range(0, BLOCKS_LIMIT):
        if not block or block.id > 0:
            try:
                # Process block
                block = harvester.add_block(block_hash)

                print('+ Block Added {} number {}'.format(block_hash, block.id))

                add_count += 1

                self.session.commit()

                # Break loop if targeted end block hash is reached
                if block_hash == end_block_hash or block.id == 0:
                    break

                # Continue with parent block hash
                block_hash = block.parent_hash
            except BlockAlreadyAdded as e:
                block = Block.query(self.session).filter_by(hash=block_hash).first()
                print('. Skipped {} '.format(block_hash))
                block_hash = block.parent_hash
            except IntegrityError as e:
                print('. Skipped duplicate {} '.format(block_hash))
            except Exception as exc:
                print('! ERROR adding {}'.format(block_hash))
                raise HarvesterCouldNotAddBlock(block_hash) from exc

    # Update persistent metadata store in Celery task
    self.metadata_store = harvester.metadata_store

    if block_hash != end_block_hash and block and block.id > 0:
        accumulate_block_recursive.delay(block.parent_hash, end_block_hash)

    return {
        'result': '{} blocks added'.format(add_count),
        'lastAddedBlockHash': block_hash,
        'sequencerStartedFrom': max_sequenced_block_id
    }


@app.task(base=BaseTask, bind=True)
def start_sequencer(self):
    sequencer_task = Status.get_status(self.session, 'SEQUENCER_TASK_ID')

    if sequencer_task.value:
        task_result = AsyncResult(sequencer_task.value)
        if not task_result or task_result.ready():
            sequencer_task.value = None
            sequencer_task.save(self.session)

    if sequencer_task.value is None:
        sequencer_task.value = self.request.id
        sequencer_task.save(self.session)
        self.session.commit()

        harvester = self.harvester
        try:
            result = harvester.start_sequencer()
        except Exception as e:
            traceback.print_exception(type(e), e, e.__traceback__)
            self.session.rollback()
            result = {'result': str(e)}

        sequencer_task.value = None
        sequencer_task.save(self.session)

        self.session.commit()

        # Check if analytics data need to be generated
        # start_generate_analytics.delay()

        return result
    else:
        return {'result': 'Sequencer already running'}


@app.task(base=BaseTask, bind=True)
def rebuilding_search_index(self, search_index_id=None, truncate=False):
    if truncate:
        # Clear search index table
        self.session.execute('delete from analytics_search_index where index_type_id={}'.format(search_index_id))
        self.session.commit()

    harvester = self.harvester
    harvester.rebuild_search_index()

    return {'result': 'index rebuilt'}


@app.task(base=BaseTask, bind=True)
def start_harvester(self, check_gaps=True):
    substrate = self.harvester.substrate

    block_sets = []
    if check_gaps:
        # Check for gaps between already harvested blocks and try to fill them first
        remaining_sets_result = Block.get_missing_block_ids(self.session)
        remaining_sets_result = remaining_sets_result.mappings().all()
        print("query remaining sets:{}".format(remaining_sets_result))
        for block_set in remaining_sets_result:
            end = int(block_set['block_from'])
            start = int(block_set['block_to'])
            parallel = 1
            if len(remaining_sets_result) == 1 and start - end > BLOCKS_LIMIT * 10:
                parallel = MAXIMUM_THREAD
            for i in range(parallel):
                end = start - BLOCKS_LIMIT
                end = 0 if end < 0 else end
                # Get start and end block hash
                end_block_hash = substrate.get_block_hash(end)
                start_block_hash = substrate.get_block_hash(start)
                # Start processing task
                accumulate_block_recursive.delay(start_block_hash, end_block_hash)
                block_sets.append({
                    'start': start,
                    'end': end,
                    'start_block_hash': start_block_hash,
                    'end_block_hash': end_block_hash
                })
                start = end + 1

    # Start sequencer
    sequencer_task = start_sequencer.delay()

    # Continue from current (finalised) head
    if FINALIZATION_ONLY == 1:
        start_block_hash = substrate.get_chain_finalised_head()
    else:
        start_block_hash = substrate.get_chain_head()

    end_block_hash = None

    accumulate_block_recursive.delay(start_block_hash, end_block_hash)

    block_sets.append({
        'start_block_hash': start_block_hash,
        'end_block_hash': end_block_hash
    })

    return {
        'result': 'Harvester job started',
        'block_sets': block_sets,
        'sequencer_task_id': sequencer_task.task_id
    }


@app.task(base=BaseTask, bind=True)
def start_generate_analytics(self):
    self.session.execute('CALL generate_analytics_data()')
    self.session.commit()
    return {'status': 'OK'}


@app.task(base=BaseTask, bind=True)
def rebuild_search_index(self):
    harvester = PolkascanHarvesterService(
        db_session=self.session,
        type_registry=TYPE_REGISTRY,
        type_registry_file=TYPE_REGISTRY_FILE
    )
    harvester.rebuild_search_index()

    return {'result': 'search index rebuilt'}


@app.task(base=BaseTask, bind=True)
def rebuild_account_info_snapshot(self):
    harvester = self.harvester

    last_full_snapshot_block_nr = 0

    self.session.execute('truncate table {}'.format(AccountInfoSnapshot.__tablename__))

    for account_id, block_id in self.session.query(SearchIndex.account_id, SearchIndex.block_id).filter(
            SearchIndex.block_id >= settings.BALANCE_SYSTEM_ACCOUNT_MIN_BLOCK
    ).order_by('block_id').group_by(SearchIndex.account_id, SearchIndex.block_id).yield_per(1000):

        if block_id > last_full_snapshot_block_nr + settings.BALANCE_FULL_SNAPSHOT_INTERVAL:

            last_full_snapshot_block_nr = block_id - block_id % settings.BALANCE_FULL_SNAPSHOT_INTERVAL
            harvester.create_full_balance_snaphot(last_full_snapshot_block_nr)
            self.session.commit()
        else:
            harvester.create_balance_snapshot(block_id, account_id)
            self.session.commit()

    # set balances according to most recent snapshot
    account_info = self.session.execute("""
            select
               a.account_id, 
               a.balance_total,
               a.balance_free,
               a.balance_reserved,
               a.nonce
        from
             data_account_info_snapshot as a
        inner join (
            select 
                account_id, max(block_id) as max_block_id 
            from data_account_info_snapshot 
            group by account_id
        ) as b
        on a.account_id = b.account_id and a.block_id = b.max_block_id
        """)

    for account_id, balance_total, balance_free, balance_reserved, nonce in account_info:
        Account.query(self.session).filter_by(id=account_id).update(
            {
                Account.balance_total: balance_total,
                Account.balance_free: balance_free,
                Account.balance_reserved: balance_reserved,
                Account.nonce: nonce,
            }, synchronize_session='fetch'
        )
    self.session.commit()

    return {'result': 'account info snapshots rebuilt'}


@app.task(base=BaseTask, bind=True)
def balance_snapshot(self, account_id=None, block_start=1, block_end=None, block_ids=None):
    if account_id:
        accounts = [account_id]
    else:
        accounts = [account.id for account in Account.query(self.session)]

    harvester = self.harvester

    if block_ids:
        block_range = block_ids
    else:

        if block_end is None:
            # Set block end to chaintip
            substrate = self.harvester.substrate
            block_end = substrate.get_block_number(substrate.get_chain_finalised_head())

        block_range = range(block_start, block_end + 1)

    for block_id in block_range:
        for account in accounts:
            harvester.create_balance_snapshot(block_id, account)
            self.session.commit()

    return {
        'message': 'Snapshop created',
        'account_id': account_id,
        'block_start': block_start,
        'block_end': block_end,
        'block_ids': block_ids
    }


@app.task(base=BaseTask, bind=True)
def update_balances_in_block(self, block_id):
    harvester = self.harvester

    harvester.create_full_balance_snaphot(block_id)
    self.session.commit()

    harvester.update_account_balances()
    self.session.commit()

    return 'Snapshot created for block {}'.format(block_id)


@app.task(base=BaseTask, bind=True)
def rebuild_oracle_price_snapshot(self, block_start=1, block_end=None, block_ids=None):
    print("1")
    # self.session.execute('truncate table {}'.format(SymbolSnapshot.__tablename__))
    #
    # substrate = self.harvester.substrate
    # if block_ids:
    #     block_range = block_ids
    # else:
    #     if block_end is None:
    #         # Set block end to chaintip
    #         substrate = self.harvester.substrate
    #         block_end = substrate.get_block_number(substrate.get_chain_finalised_head())
    #
    #     block_range = range(block_start, block_end + 1)
    #
    # for block_id in block_range:
    #     extrinsic = Extrinsic.query(self.session).filter_by(block_id=block_id, module_id='AresOracle',
    #                                                         call_id='submit_price_unsigned_with_signed_payload').first()
    #     if extrinsic:
    #         try:
    #             block = Block.query(self.session).filter_by(id=block_id).first()
    #             processor = AresOracleSubmitPrice(block, extrinsic, substrate=substrate)
    #             processor.accumulation_hook(self.session)
    #             self.session.commit()
    #         except Exception as e:
    #             print('! error {}'.format(e))


@app.task(base=BaseTask, bind=True)
def rebuild_total_treasury_burn(self, block_start=1, block_end=None, block_ids=None):
    substrate = self.harvester.substrate
    if block_ids:
        block_range = block_ids
    else:
        if block_end is None:
            # Set block end to chaintip
            substrate = self.harvester.substrate
            block_end = substrate.get_block_number(substrate.get_chain_finalised_head())

        block_range = range(block_start, block_end + 1)
    for block_id in block_range:
        if block_id > 1:
            sequencer_parent_block = BlockTotal.query(self.session).filter_by(id=block_id - 1).first()
            sequencer_parent_block = sequencer_parent_block.asdict()
        else:
            sequencer_parent_block = {}

        events = Event.query(self.session).filter_by(block_id=block_id).order_by('event_idx')
        if events:
            try:
                block = Block.query(self.session).filter_by(id=block_id).first()
                sequenced_block: BlockTotal = BlockTotal.query(self.session).filter_by(id=block_id).first()
                exist = False
                for event in events:
                    if event.module_id == 'treasury' and event.event_id == 'Burnt':
                        processor = TreasuryBurnt(block, event, substrate=substrate, sequenced_block=sequenced_block)
                        processor.sequencing_hook(self.session, {}, sequencer_parent_block)
                        sequenced_block.save(self.session)
                        self.session.commit()
                        exist = True
                        break
                if exist is False:
                    sequenced_block.total_treasury_burn = int(sequencer_parent_block.get('total_treasury_burn', 0))
                    self.session.commit()
            except Exception as e:
                print('! error {}'.format(e))
