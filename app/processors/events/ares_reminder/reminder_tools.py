from app.models.data import DataReminder, DataReminderLifecycle
from app.processors.base import EventProcessor
from app.settings import SEARCH_INDEX_BALANCES_DEPOSIT, SUBSTRATE_ADDRESS_TYPE
from scalecodec.types import ss58_encode


class AresReminderTools:

    def convert_to_price(self, number, fraction_length):
        return number / (10 ** fraction_length)

    def set_released_status_to_lifecycle(self, db_session, reminder_id):
        self.update_point_to_lifecycle(db_session, reminder_id, 0, 1)

    def add_point_to_lifecycle(self, db_session, reminder_id, repeat_count):
        # search old data
        self.update_point_to_lifecycle(db_session, reminder_id, repeat_count)

    def sub_point_to_lifecycle(self, db_session, reminder_id, repeat_count):
        self.update_point_to_lifecycle(db_session, reminder_id, repeat_count * -1)

    def update_point_to_lifecycle(self, db_session, reminder_id, repeat_count, is_released=None):
        # search old data
        lifecycle = DataReminderLifecycle.query(db_session).filter_by(reminder_id=reminder_id).first()
        if lifecycle:
            if is_released:
                lifecycle.is_released = is_released

            lifecycle.points += repeat_count
            lifecycle.save(db_session)

        else:
            new_lifecycle = DataReminderLifecycle(
                reminder_id=reminder_id,
                points=repeat_count,
                is_released=is_released,
            )
            new_lifecycle.save(db_session)
