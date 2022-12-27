from app.models.data import DataReminder, DataReminderMsg
from app.processors.base import EventProcessor
from app.processors.events.ares_reminder.reminder_tools import AresReminderTools
from app.settings import SEARCH_INDEX_BALANCES_DEPOSIT, SUBSTRATE_ADDRESS_TYPE
from scalecodec.types import ss58_encode


class AresReminderMsg(EventProcessor):
    module_id = 'AresReminder'
    event_id = 'ReminderMsg'

    def accumulation_hook(self, db_session):
        event_infos = self.event.attributes
        print('reminder_info = ', event_infos)

        reminder_id = event_infos[0]['value']
        print('reminder_id = ', reminder_id)

        remaining_count = event_infos[1]['value']
        print('remaining_count = ', remaining_count)

        send_bn = event_infos[2]['value']
        print('send_bn = ', send_bn)

        submitter = event_infos[3]['value'].replace('0x', '')
        print('submitter = ', submitter)

        response_mark = event_infos[4]['value']
        print('response_mark = ', response_mark)

        status = event_infos[5]['value']
        print('status = ', status)

        db_data = DataReminderMsg(
            block_id=self.block.id,
            reminder_id=reminder_id,
            remaining_count=remaining_count,
            send_bn=send_bn,
            submitter=submitter,
            response_mark=response_mark,
            status=status,
        )
        db_data.save(db_session)

        tools = AresReminderTools()
        tools.sub_point_to_lifecycle(db_session, reminder_id, 1)

    def accumulation_revert(self, db_session):
        print("RUN KAMI-DEBUG:: accumulation_revert ", self.block.id)
        for item in DataReminderMsg.query(db_session).filter_by(block_id=self.block.id):
            reminder_id = item.reminder_id
            tools = AresReminderTools()
            tools.sub_point_to_lifecycle(db_session, reminder_id, 1)
            db_session.delete(item)
