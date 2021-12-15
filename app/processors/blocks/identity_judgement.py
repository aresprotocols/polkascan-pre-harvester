from app.models.data import IdentityJudgementAudit, IdentityJudgement, Account
from app.processors import BlockProcessor
from app.settings import IDENTITY_JUDGEMENT_TYPE_GIVEN


class IdentityJudgementBlockProcessor(BlockProcessor):

    def sequencing_hook(self, db_session, parent_block_data, parent_sequenced_block_data):
        audits = IdentityJudgementAudit.query(db_session).filter_by(block_id=self.block.id).order_by('event_idx')
        for identity_audit in audits:

            if identity_audit.type_id == IDENTITY_JUDGEMENT_TYPE_GIVEN:

                judgement = IdentityJudgement.query(db_session).filter_by(
                    account_id=identity_audit.account_id,
                    registrar_index=identity_audit.registrar_index
                ).first()

                if not judgement:
                    judgement = IdentityJudgement(
                        account_id=identity_audit.account_id,
                        registrar_index=identity_audit.registrar_index,
                        created_at_block=self.block.id
                    )

                if identity_audit.data:
                    judgement.judgement = identity_audit.data.get('judgement')
                    judgement.updated_at_block = self.block.id

                    judgement.save(db_session)

                    account = Account.query(db_session).get(identity_audit.account_id)

                    if account:

                        if judgement.judgement in ['Reasonable', 'KnownGood']:
                            account.identity_judgement_good += 1

                        if judgement.judgement in ['LowQuality', 'Erroneous']:
                            account.identity_judgement_bad += 1

                        account.save(db_session)

                        if account.has_subidentity:
                            # Update sub identities
                            sub_accounts = Account.query(db_session).filter_by(parent_identity=account.id)
                            for sub_account in sub_accounts:
                                sub_account.identity_judgement_good = account.identity_judgement_good
                                sub_account.identity_judgement_bad = account.identity_judgement_bad
                                sub_account.save(db_session)
