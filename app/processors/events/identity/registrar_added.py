from app.models.data import Account
from app.processors.base import EventProcessor


class RegistrarAddedEventProcessor(EventProcessor):
    module_id = 'Identity'
    event_id = 'RegistrarAdded'

    def sequencing_hook(self, db_session, parent_block, parent_sequenced_block):
        registrars = self.substrate.get_runtime_state(
            module="Identity",
            storage_function="Registrars",
            params=[]
        ).get('result')

        if not registrars:
            registrars = []

        registrar_ids = [registrar['account'].replace('0x', '') for registrar in registrars]

        Account.query(db_session).filter(
            Account.id.in_(registrar_ids), Account.was_registrar == False
        ).update({Account.was_registrar: True}, synchronize_session='fetch')

        Account.query(db_session).filter(
            Account.id.notin_(registrar_ids), Account.is_registrar == True
        ).update({Account.is_registrar: False}, synchronize_session='fetch')

        Account.query(db_session).filter(
            Account.id.in_(registrar_ids), Account.is_registrar == False
        ).update({Account.is_registrar: True}, synchronize_session='fetch')
