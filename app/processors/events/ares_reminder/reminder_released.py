from app.models.data import DataReminder, DataReminderMsg
from app.processors.base import EventProcessor
from app.processors.events.ares_reminder.reminder_tools import AresReminderTools
from app.settings import SEARCH_INDEX_BALANCES_DEPOSIT, SUBSTRATE_ADDRESS_TYPE
from scalecodec.types import ss58_encode


class AresReminderReleased(EventProcessor):
    module_id = 'AresReminder'
    event_id = 'ReminderReleased'

    def accumulation_hook(self, db_session):
        event_infos = self.event.attributes
        print('reminder_info = ', event_infos)

        reminder_id = event_infos[0]['value']
        print('reminder_id = ', reminder_id)
        #
        released_bn = event_infos[1]['value']
        print('released_bn = ', released_bn)

        tools = AresReminderTools()
        tools.set_released_status_to_lifecycle(db_session, reminder_id)

    def accumulation_revert(self, db_session):
        pass
