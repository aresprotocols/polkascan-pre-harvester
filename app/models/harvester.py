#  Polkascan PRE Explorer GUI
#
#  Copyright 2018-2020 openAware BV (NL).
#  This file is part of Polkascan.
#
#  Polkascan is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Polkascan is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Polkascan. If not, see <http://www.gnu.org/licenses/>.
#
#  harvester.py
#
from app.models.base import BaseModel, BaseModelObj
from datetime import datetime
import sqlalchemy as sa


class Status(BaseModel):
    __tablename__ = 'harvester_status'
    key = sa.Column(sa.String(64), primary_key=True)
    value = sa.Column(sa.String(255))
    last_modified = sa.Column(sa.DateTime(timezone=True))
    notes = sa.Column(sa.String(255))

    @classmethod
    def get_status(cls, session, key):
        model = session.query(cls).filter_by(key=key).first()

        if not model:
            return Status(
                key=key,
                last_modified=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )

        return model

    @classmethod
    def diff_second(cls, old_time_str):
        old_time = datetime.strptime(old_time_str, "%Y-%m-%d %H:%M:%S")
        current_time = datetime.now()
        return (current_time - old_time).seconds

    # def save(self, session):
    #     self.last_modified = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    #     # session.add(self)
    #     # session.flush()
    #     # BaseModel.save(self, session)
    #     # super().save(session)
    #     # session.add(self)
    #     # BaseModelObj.save()
    #     BaseModelObj.save(self, session)
    #     # session.flush()



class Setting(BaseModel):
    __tablename__ = 'harvester_setting'
    key = sa.Column(sa.String(64), primary_key=True)
    value = sa.Column(sa.String(255))
    notes = sa.Column(sa.String(255))
