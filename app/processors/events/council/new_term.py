from app.models.data import Account
from app.processors.base import EventProcessor
from app.settings import SEARCH_INDEX_COUNCIL_MEMBER_ELECTED


class CouncilNewTermEventProcessor(EventProcessor):
    module_id = 'Elections'
    event_id = 'NewTerm'

    def sequencing_hook(self, db_session, parent_block, parent_sequenced_block):
        new_member_ids = [
            member_struct['account'].replace('0x', '') for member_struct in self.event.attributes[0]['value']
        ]

        Account.query(db_session).filter(
            Account.id.in_(new_member_ids), Account.was_council_member == False
        ).update({Account.was_council_member: True}, synchronize_session='fetch')

        Account.query(db_session).filter(
            Account.id.notin_(new_member_ids), Account.is_council_member == True
        ).update({Account.is_council_member: False}, synchronize_session='fetch')

        Account.query(db_session).filter(
            Account.id.in_(new_member_ids), Account.is_council_member == False
        ).update({Account.is_council_member: True}, synchronize_session='fetch')

    def process_search_index(self, db_session):
        for member_struct in self.event.attributes[0]['value']:
            search_index = self.add_search_index(
                index_type_id=SEARCH_INDEX_COUNCIL_MEMBER_ELECTED,
                # account_id=member_struct['account'].replace('0x', ''),
                # sorting_value=member_struct['balance']
                account_id=member_struct[0].replace('0x', ''),
                sorting_value=member_struct[1]
            )

            search_index.save(db_session)
