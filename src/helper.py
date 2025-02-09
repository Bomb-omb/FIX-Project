import logging
import datetime
import quickfix as fix

def str_to_datetime(date_str):
    try:
        return datetime.datetime.strptime(date_str, '%Y%m%d-%H:%M:%S.%f')
    except:
        return None

def extract_message_field_value(_FIX_API_Object, message, type=''):
    if type == "datetime":
        message.getHeader().getField(_FIX_API_Object)
        return str_to_datetime(_FIX_API_Object.getString())
    if message.isSetField(_FIX_API_Object.getField()):
        message.getField(_FIX_API_Object)
        if type == '':
            return _FIX_API_Object.getValue()
        elif type == 'str':
            return str(_FIX_API_Object.getValue())
        elif type == 'int':
            try:
                return int(_FIX_API_Object.getValue())
            except:
                return None
        elif type == 'float':
            try:
                return float(_FIX_API_Object.getValue())
            except:
                return None
    else:
        return None