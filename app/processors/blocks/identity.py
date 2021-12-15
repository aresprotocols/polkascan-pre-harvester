from app.models.data import IdentityAudit, Account
from app.processors import BlockProcessor
from app.settings import IDENTITY_TYPE_SET, IDENTITY_TYPE_CLEARED, IDENTITY_TYPE_KILLED, IDENTITY_TYPE_SET_SUBS


class IdentityBlockProcessor(BlockProcessor):

    def sequencing_hook(self, db_session, parent_block_data, parent_sequenced_block_data):

        for identity_audit in IdentityAudit.query(db_session).filter_by(block_id=self.block.id).order_by('event_idx'):

            account = Account.query(db_session).get(identity_audit.account_id)

            if account:

                if identity_audit.type_id == IDENTITY_TYPE_SET:

                    account.has_identity = True

                    account.identity_display = identity_audit.data.get('display')
                    account.identity_email = identity_audit.data.get('email')
                    account.identity_legal = identity_audit.data.get('legal')
                    account.identity_riot = identity_audit.data.get('riot')
                    account.identity_web = identity_audit.data.get('web')
                    account.identity_twitter = identity_audit.data.get('twitter')

                    if account.has_subidentity:
                        # Update sub accounts
                        sub_accounts = Account.query(db_session).filter_by(parent_identity=account.id)
                        for sub_account in sub_accounts:
                            sub_account.identity_display = account.identity_display
                            sub_account.identity_email = account.identity_email
                            sub_account.identity_legal = account.identity_legal
                            sub_account.identity_riot = account.identity_riot
                            sub_account.identity_web = account.identity_web
                            sub_account.identity_twitter = account.identity_twitter

                            sub_account.save(db_session)

                    account.save(db_session)
                elif identity_audit.type_id in [IDENTITY_TYPE_CLEARED, IDENTITY_TYPE_KILLED]:

                    if account.has_subidentity:
                        # Clear sub accounts
                        sub_accounts = Account.query(db_session).filter_by(parent_identity=account.id)
                        for sub_account in sub_accounts:
                            sub_account.identity_display = None
                            sub_account.identity_email = None
                            sub_account.identity_legal = None
                            sub_account.identity_riot = None
                            sub_account.identity_web = None
                            sub_account.identity_twitter = None
                            sub_account.parent_identity = None
                            sub_account.has_identity = False

                            sub_account.identity_judgement_good = 0
                            sub_account.identity_judgement_bad = 0

                            sub_account.save(db_session)

                    account.has_identity = False
                    account.has_subidentity = False

                    account.identity_display = None
                    account.identity_email = None
                    account.identity_legal = None
                    account.identity_riot = None
                    account.identity_web = None
                    account.identity_twitter = None

                    account.identity_judgement_good = 0
                    account.identity_judgement_bad = 0

                    account.save(db_session)

                elif identity_audit.type_id == IDENTITY_TYPE_SET_SUBS:

                    # Clear current subs
                    sub_accounts = Account.query(db_session).filter_by(parent_identity=account.id)
                    for sub_account in sub_accounts:
                        sub_account.identity_display = None
                        sub_account.identity_email = None
                        sub_account.identity_legal = None
                        sub_account.identity_riot = None
                        sub_account.identity_web = None
                        sub_account.identity_twitter = None
                        sub_account.parent_identity = None
                        sub_account.identity_judgement_good = 0
                        sub_account.identity_judgement_bad = 0
                        sub_account.has_identity = False

                        sub_account.save(db_session)

                    account.has_subidentity = False

                    # Process sub indenties
                    if len(identity_audit.data.get('subs', [])) > 0:

                        account.has_subidentity = True

                        for sub_identity in identity_audit.data.get('subs'):
                            sub_account = Account.query(db_session).get(sub_identity['account'].replace('0x', ''))
                            if sub_account:
                                sub_account.parent_identity = account.id
                                sub_account.subidentity_display = sub_identity['name']

                                sub_account.identity_display = account.identity_display
                                sub_account.identity_email = account.identity_email
                                sub_account.identity_legal = account.identity_legal
                                sub_account.identity_riot = account.identity_riot
                                sub_account.identity_web = account.identity_web
                                sub_account.identity_twitter = account.identity_twitter

                                sub_account.identity_judgement_good = account.identity_judgement_good
                                sub_account.identity_judgement_bad = account.identity_judgement_bad

                                sub_account.has_identity = True

                                sub_account.save(db_session)

                    account.save(db_session)
