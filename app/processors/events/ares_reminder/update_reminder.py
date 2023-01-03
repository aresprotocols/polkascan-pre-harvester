from app.models.data import DataReminder, DataReminderLifecycle
from app.processors import EventProcessor
from app.processors.events.ares_reminder.reminder_tools import AresReminderTools
from app.settings import SEARCH_INDEX_BALANCES_DEPOSIT, SUBSTRATE_ADDRESS_TYPE
from scalecodec.types import ss58_encode


class AresCreateReminder(EventProcessor):
    module_id = 'AresReminder'
    event_id = 'UpdateReminder'

    def accumulation_hook(self, db_session):
        reminder_infos = self.event.attributes

        tools = AresReminderTools()

        print('reminder_info', reminder_infos)

        reminder_id = reminder_infos[0]['value']
        print('-- reminder_id', reminder_id)
        reminder_body = reminder_infos[2]['value']
        print('##### reminder_body = ', reminder_body)
        owner = reminder_body['owner'].replace('0x', '')
        print('-- owner', owner)
        interval_bn = reminder_body['interval_bn']
        print('-- interval_bn', interval_bn)
        repeat_count = reminder_body['repeat_count']
        print('-- repeat_count', repeat_count)
        create_bn = reminder_body['create_bn']
        print('-- create_bn', create_bn)
        price_snapshot_raw = reminder_body['price_snapshot']
        price_snapshot = tools.convert_to_price(price_snapshot_raw['number'], price_snapshot_raw['fraction_length'])
        print('-- price_snapshot', price_snapshot)
        trigger_condition_type = 'TargetPriceModel' if 'TargetPriceModel' in reminder_body['trigger_condition'] else None
        print('-- trigger_condition_type', trigger_condition_type)

        trigger_condition_price_key = None
        anchor_price = None
        if 'TargetPriceModel' == trigger_condition_type:
            trigger_condition_price_key = reminder_body['trigger_condition'][trigger_condition_type][0]
            print('-- trigger_condition_price_key', trigger_condition_price_key)
            anchor_price_raw = reminder_body['trigger_condition'][trigger_condition_type][1]
            anchor_price = tools.convert_to_price(anchor_price_raw['number'], anchor_price_raw['fraction_length'])
            print('-- anchor_price', anchor_price)

        trigger_receiver_type = 'HttpCallBack' if 'HttpCallBack' in reminder_body['trigger_receiver'] else None
        print('-- trigger_receiver_type', trigger_receiver_type)
        trigger_receiver_url = None
        trigger_receiver_sign = None
        if 'HttpCallBack' == trigger_receiver_type:
            trigger_receiver_url = reminder_body['trigger_receiver'][trigger_receiver_type][0]
            print('-- trigger_receiver_url', trigger_receiver_url)
            trigger_receiver_sign = reminder_body['trigger_receiver'][trigger_receiver_type][1]
            print('-- trigger_receiver_sign', trigger_receiver_sign)

        update_bn = reminder_body['update_bn']
        print('-- update_bn', update_bn)
        tip = reminder_body['tip']
        print('-- tip', tip)
        repeat_increase = reminder_infos[3]['value']
        print('-- repeat_increase', repeat_increase)
        repeat_reduce = reminder_infos[4]['value']
        print('-- repeat_reduce', repeat_reduce)

        # search old data reminder
        db_data = DataReminder.query(db_session).filter_by(reminder_id=reminder_id).first()
        if db_data:
            if db_data.block_id > self.block.id :
                db_data.block_id = self.block.id
                db_data.reminder_id = reminder_id
                db_data.owner = owner
                db_data.owner_ss58 = ss58_encode(owner, SUBSTRATE_ADDRESS_TYPE)
                db_data.interval_bn = interval_bn
                db_data.repeat_count = repeat_count
                db_data.create_bn = create_bn
                db_data.price_snapshot = price_snapshot
                db_data.trigger_condition_type = trigger_condition_type
                db_data.trigger_condition_price_key = trigger_condition_price_key
                db_data.anchor_price = anchor_price
                db_data.trigger_receiver_type = trigger_receiver_type
                db_data.trigger_receiver_url = trigger_receiver_url
                db_data.trigger_receiver_sign = trigger_receiver_sign
                db_data.update_bn = update_bn
                db_data.tip = tip
                db_data.datetime = self.block.datetime
                db_data.save(db_session)

        else:
            db_data = DataReminder(
                block_id=self.block.id,
                reminder_id=reminder_id,
                owner=owner,
                owner_ss58=ss58_encode(owner, SUBSTRATE_ADDRESS_TYPE),
                interval_bn=interval_bn,
                repeat_count=repeat_count,
                create_bn=create_bn,
                price_snapshot=price_snapshot,
                trigger_condition_type=trigger_condition_type,
                trigger_condition_price_key=trigger_condition_price_key,
                anchor_price=anchor_price,
                trigger_receiver_type=trigger_receiver_type,
                trigger_receiver_url=trigger_receiver_url,
                trigger_receiver_sign=trigger_receiver_sign,
                update_bn=update_bn,
                tip=tip,
                datetime=self.block.datetime,
            )
            db_data.save(db_session)

        if repeat_increase > 0:
            tools.add_point_to_lifecycle(db_session, reminder_id, repeat_increase)
        if repeat_reduce > 0:
            tools.sub_point_to_lifecycle(db_session, reminder_id, repeat_reduce)

    def accumulation_revert(self, db_session):
        print("RUN KAMI-DEBUG:: accumulation_revert ", self.block.id)
        for item in DataReminder.query(db_session).filter_by(block_id=self.block.id):
            reminder_id = item.reminder_id
            repeat_count = item.repeat_count
            tools = AresReminderTools()
            tools.sub_point_to_lifecycle(db_session, reminder_id, repeat_count)
            db_session.delete(item)
