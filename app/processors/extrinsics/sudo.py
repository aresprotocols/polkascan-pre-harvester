from app.models.data import Account
from app.processors import ExtrinsicProcessor


class SudoSetKey(ExtrinsicProcessor):
    module_id = 'Sudo'
    call_id = 'set_key'

    def sequencing_hook(self, db_session, parent_block, parent_sequenced_block):
        if self.extrinsic.success:
            sudo_key = self.extrinsic.params[0]['value'].replace('0x', '')

            Account.query(db_session).filter(
                Account.id == sudo_key, Account.was_sudo == False
            ).update({Account.was_sudo: True}, synchronize_session='fetch')

            Account.query(db_session).filter(
                Account.id != sudo_key, Account.is_sudo == True
            ).update({Account.is_sudo: False}, synchronize_session='fetch')

            Account.query(db_session).filter(
                Account.id == sudo_key, Account.is_sudo == False
            ).update({Account.is_sudo: True}, synchronize_session='fetch')
