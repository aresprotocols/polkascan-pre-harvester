from app.models.data import IdentityAudit
from app.processors.base import EventProcessor
from app.settings import IDENTITY_TYPE_SET, SEARCH_INDEX_IDENTITY_SET


class IdentitySetEventProcessor(EventProcessor):
    module_id = 'Identity'
    event_id = 'IdentitySet'

    def accumulation_hook(self, db_session):

        # Check event requirements
        if len(self.event.attributes) == 1 and \
                self.event.attributes[0]['type'] == 'T::AccountId':

            identity_audit = IdentityAudit(
                account_id=self.event.attributes[0]['value'].replace('0x', ''),
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=IDENTITY_TYPE_SET
            )

            identity_audit.data = {
                'display': None,
                'email': None,
                'legal': None,
                'riot': None,
                'web': None,
                'twitter': None
            }

            for param in self.extrinsic.params:
                if param.get('name') == 'info':
                    identity_audit.data['display'] = param.get('value', {}).get('display', {}).get('Raw')
                    identity_audit.data['email'] = param.get('value', {}).get('email', {}).get('Raw')
                    identity_audit.data['legal'] = param.get('value', {}).get('legal', {}).get('Raw')
                    identity_audit.data['web'] = param.get('value', {}).get('web', {}).get('Raw')
                    identity_audit.data['riot'] = param.get('value', {}).get('riot', {}).get('Raw')
                    identity_audit.data['twitter'] = param.get('value', {}).get('twitter', {}).get('Raw')

            identity_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in IdentityAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=SEARCH_INDEX_IDENTITY_SET,
            account_id=self.event.attributes[0]['value'].replace('0x', '')
        )

        search_index.save(db_session)
