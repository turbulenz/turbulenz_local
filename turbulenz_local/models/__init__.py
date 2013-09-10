# Copyright (c) 2010-2011,2013 Turbulenz Limited

class Field(object):
    pass


class ModelMeta(type):

    def __new__(mcs, name, bases, attrs):
        fields = {}
        new_attrs = {}
        for name, value in attrs.iteritems():
            if isinstance(value, Field):
                fields.update({name: value})
            else:
                new_attrs.update({name: value})
        new_attrs['_fields'] = fields
        return super(ModelMeta, mcs).__new__(mcs, name, bases, new_attrs)


class Model(object):

    __metaclass__ = ModelMeta

    def __init__(self, **kwargs):
        for k, v in self._fields.items():
            if kwargs.get(k, None):
                self._fields[k].value = v

    def __setattr__(self, name, value):
        if name in self._fields:
            self._fields[name].value = value
        else:
            raise AttributeError(name)

    def __getattr__(self, name):
        if name in self._fields:
            return self._fields[name].value
        raise AttributeError(name)


class String(Field):

    def __init__(self, not_empty=False, max_length=None, **kwargs):
        Field.__init__(self)
        self.not_empty = not_empty
        self.max_length = max_length
        self.value = None


class ModelException(Exception):
    pass
