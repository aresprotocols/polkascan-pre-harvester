import datetime

from app.processors import ExtrinsicProcessor


class TimestampExtrinsicProcessor(ExtrinsicProcessor):
    module_id = 'Timestamp'
    call_id = 'set'

    def accumulation_hook(self, db_session):

        if self.extrinsic.success:
            # Store block date time related fields
            for param in self.extrinsic.params:
                if param.get('name') == 'now':
                    t = datetime.datetime.fromtimestamp(param.get('value') / 1000.0)
                    self.block.set_datetime(t)
                    # self.block.set_datetime(dateutil.parser.parse(param.get('value')).replace(tzinfo=pytz.UTC))
