from typing import Optional

from scalecodec.base import RuntimeConfigurationObject, Singleton
from substrateinterface import SubstrateInterface
from scalecodec.types import Enum, H256, GenericRegistryType


class AresSubstrateInterface(SubstrateInterface):
    def implements_scaleinfo(self) -> Optional[bool]:
        if self.metadata_decoder:
            return self.metadata_decoder.portable_registry is not None
        return False

    def init_runtime(self, block_hash=None, block_id=None):
        super().init_runtime(block_hash=block_hash, block_id=block_id)
        self.ss58_format = None


class CompatibleRuntimeConfigurationObject(RuntimeConfigurationObject):
    def get_decoder_class_for_scale_info_definition(
            self, type_string: str, scale_info_type: 'GenericRegistryType', prefix: str
    ):
        decoder_class = None
        base_decoder_class = None

        # Check if base decoder class is defined for path
        if 'path' in scale_info_type.value and len(scale_info_type.value['path']) > 0:
            path_string = '::'.join(scale_info_type.value["path"])
            base_decoder_class = self.get_decoder_class(path_string)
            # print("base_decoder_class: {} path_string--> {}".format(base_decoder_class,path_string))

            if base_decoder_class is None:
                # Try generic type
                catch_all_path = '*::' * (len(scale_info_type.value['path']) - 1) + scale_info_type.value["path"][-1]
                base_decoder_class = self.get_decoder_class(catch_all_path)

            if base_decoder_class and hasattr(base_decoder_class, 'process_scale_info_definition'):
                # if process_scale_info_definition is implemented result is final
                decoder_class = type(type_string, (base_decoder_class,), {})
                decoder_class.process_scale_info_definition(scale_info_type, prefix)

                # Link ScaleInfo RegistryType to decoder class
                decoder_class.scale_info_type = scale_info_type

                return decoder_class

        if 'variant' in scale_info_type.value['def']:
            # Enum
            type_mapping = []
            type_name = []
            variants = scale_info_type.value['def']['variant']['variants']

            if len(variants) > 0:
                # Create placeholder list
                variant_length = max([v['index'] for v in variants]) + 1
                type_mapping = [(None, 'Null')] * variant_length
                type_name = [(None, 'Null')] * variant_length

                for variant in variants:

                    if 'fields' in variant:
                        if len(variant['fields']) == 0:
                            enum_value = 'Null'
                            field_types = 'Null'
                        elif len(variant['fields']) == 1:
                            enum_value = f"{prefix}::{variant['fields'][0]['type']}"
                            field_types = variant['fields'][0]['typeName']
                        else:
                            field_types = []
                            field_str = ', '.join([f"{prefix}::{f['type']}" for f in variant['fields']])
                            for f in variant['fields']:
                                field_types.append(f['typeName'])
                            enum_value = f"({field_str})"

                    else:
                        enum_value = 'Null'
                    print("path: {}, type_string:{},  variant: {}, value: {}, field_type: {}".format(path_string,
                                                                                                     type_string,
                                                                                                     variant['index'],
                                                                                                     (variant['name'],
                                                                                                      enum_value),
                                                                                                     field_types,
                                                                                                     ))
                    # Put mapping in right order in list
                    type_mapping[variant['index']] = (variant['name'], enum_value)
                    type_name[variant['index']] = field_types
            if base_decoder_class is None:
                base_decoder_class = self.get_decoder_class("Enum")

            decoder_class = type(type_string, (base_decoder_class,), {
                'type_mapping': type_mapping,
                'type_name': type_name,
            })
            decoder_class.scale_info_type = scale_info_type
        else:
            return super().get_decoder_class_for_scale_info_definition(type_string, scale_info_type, prefix)
        return decoder_class


class CompatibleRuntimeConfiguration(CompatibleRuntimeConfigurationObject, metaclass=Singleton):
    pass


# Copy from GenericScaleInfoEvent
class CompatibleGenericScaleInfoEvent(Enum):
    def __init__(self, *args, **kwargs):

        self.event_index = None
        self.event = None
        self.event_module = None

        super().__init__(*args, **kwargs)

    def process(self):

        super().process()
        enum_index = self.value_object[1].index
        self.event_index = bytes([self.index, enum_index]).hex()

        if type(self.value_object[1][1].value) == tuple and hasattr(self.value_object[1], 'type_name'):
            attributes = [{}] * len(self.value_object[1][1].value)
            i = 0
            types = self.value_object[1].type_name[enum_index]
            for value in self.value_object[1][1].value:
                attributes[i] = {
                    'type': types[i],
                    'value': value,
                }
                i += 1
        else:
            attributes = self.value_object[1][1].value if self.value_object[1][1] else None

        return {
            'event_index': self.event_index,
            'module_id': self.value_object[0],
            'event_id': self.value_object[1][0],
            'attributes': attributes,
        }


# Copy GenericAccountId
class AresGenericAccountId(H256):
    """
        unuseful

        "AccountId": "AresGenericAccountId",
        "ValidatorId": "AccountId",
        "sp_core::crypto::AccountId32": "AresGenericAccountId",
    """

    def __init__(self, data=None, **kwargs):
        self.public_key = None
        super().__init__(data, **kwargs)

    def process_encode(self, value):
        if value[0:2] != '0x':
            # from scalecodec.utils.ss58 import ss58_decode
            # self.ss58_address = value
            value = '0x{}'.format(value)
        return super().process_encode(value)

    def serialize(self):
        return self.value

    def process(self):
        value = self.public_key = super().process()
        return value

    @classmethod
    def process_scale_info_definition(cls, scale_info_definition: 'GenericRegistryType', prefix: str):
        return
