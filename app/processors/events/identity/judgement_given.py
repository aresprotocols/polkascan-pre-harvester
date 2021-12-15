from app.models.data import IdentityJudgementAudit
from app.processors.base import EventProcessor
from app.settings import IDENTITY_JUDGEMENT_TYPE_GIVEN, SEARCH_INDEX_IDENTITY_JUDGEMENT_GIVEN


class IdentityJudgementGivenEventProcessor(EventProcessor):
    module_id = 'Identity'
    event_id = 'JudgementGiven'

    def accumulation_hook(self, db_session):

        # Check event requirements
        if len(self.event.attributes) == 2 and \
                self.event.attributes[0]['type'] == 'AccountId' and \
                self.event.attributes[1]['type'] == 'RegistrarIndex':

            identity_audit = IdentityJudgementAudit(
                account_id=self.event.attributes[0]['value'].replace('0x', ''),
                registrar_index=self.event.attributes[1]['value'],
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=IDENTITY_JUDGEMENT_TYPE_GIVEN
            )

            for param in self.extrinsic.params:
                if param.get('name') == 'judgement':
                    identity_audit.data = {'judgement': list(param.get('value').keys())[0]}

            identity_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in IdentityJudgementAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=SEARCH_INDEX_IDENTITY_JUDGEMENT_GIVEN,
            account_id=self.event.attributes[0]['value'].replace('0x', '')
        )

        search_index.save(db_session)
