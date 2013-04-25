# Copyright (c) 2012-2013 Turbulenz Limited

from random import randint

def create_id():
    #id needs to be of 12-bytes length
    string_id = ''
    for _ in range(12):
        string_id += '%02x' % randint(0, 255)
    return string_id
