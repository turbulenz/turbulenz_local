# Copyright (c) 2012-2013 Turbulenz Limited

from decimal import Decimal

CURRENCY = {}


class Currency(object):

    def __init__(self, currency, alphabetic_code, numeric_code, minor_unit_precision):
        self.currency = currency
        self.alphabetic_code = alphabetic_code
        self.numeric_code = numeric_code
        self.minor_unit_precision = minor_unit_precision

        # This is for converting between the major unit denomination and the minor unit.
        # For example, in the GBP system this is 2 (10^2 = 100) because there are 100 pennies (minor) to a pound (major)
        # All arithmatic should be computed using the minor unit to avoid any floating point errors.
        self.to_minor_unit = pow(10, minor_unit_precision)
        self.from_minor_unit = pow(10, -minor_unit_precision)

    def __repr__(self):
        return self.alphabetic_code

    def to_dict(self):
        return {
            'alphabeticCode': self.alphabetic_code,
            'numericCode': self.numeric_code,
            'currencyName': self.currency,
            'minorUnitPrecision': self.minor_unit_precision}


# Loosely based on http://code.google.com/p/python-money/
class Money(object):

    epsilon = 1e-6

    def __init__(self, currency, major_amount=None, minor_amount=None):
        self.currency = currency

        if major_amount is not None:
            minor_amount = self.currency.to_minor_unit * major_amount

        int_value = round(minor_amount, 0)
        # allow for small rounding error (after multiplication)
        if int_value - self.epsilon < minor_amount and int_value + self.epsilon > minor_amount:
            self.minor_amount = Decimal(int_value)
        else:
            raise TypeError('Money minor_amount must be a whole number')

    def __repr__(self):
        return ('%.' + str(self.currency.minor_unit_precision) + 'f') % self.major_amount()

    def get_minor_amount(self):
        return int(self.minor_amount)

    def major_amount(self):
        return round(float(self.minor_amount) * self.currency.from_minor_unit, self.currency.minor_unit_precision)

    def full_string(self):
        return '%s %s' % (self.currency.alphabetic_code, str(self))

    def __pos__(self):
        return Money(currency=self.currency, minor_amount=self.minor_amount)

    def __neg__(self):
        return Money(self.currency, minor_amount=-self.minor_amount)

    def __add__(self, other):
        if isinstance(other, Money):
            if other.currency == self.currency:
                return Money(self.currency, minor_amount=self.minor_amount + other.minor_amount)
            else:
                raise TypeError('Can not add Money quantities of different currencies' % type(other))
        else:
            raise TypeError('Can not add Money quantities to %s' % type(other))

    def __sub__(self, other):
        if isinstance(other, Money):
            if other.currency == self.currency:
                return Money(self.currency, minor_amount=self.minor_amount - other.minor_amount)
            else:
                raise TypeError('Can not subtract Money quantities of different currencies' % type(other))
        else:
            raise TypeError('Can not subtract Money quantities to %s' % type(other))

    def __mul__(self, other):
        if isinstance(other, Money):
            raise TypeError('Can not multiply monetary quantities')
        else:
            return Money(self.currency, minor_amount=self.minor_amount * Decimal(other))

    def __div__(self, other):
        if isinstance(other, Money):
            raise TypeError('Can not divide monetary quantities')
        else:
            return Money(self.currency, minor_amount=self.minor_amount / Decimal(other))

    __radd__ = __add__
    __rsub__ = __sub__
    __rmul__ = __mul__
    __rdiv__ = __div__

    def __eq__(self, other):
        if isinstance(other, Money):
            if other.currency == self.currency:
                return self.minor_amount == other.minor_amount
            else:
                raise TypeError('Can not compare Money quantities of different currencies' % type(other))
        else:
            raise TypeError('Can not compare Money quantities to %s' % type(other))

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

# pylint: disable=C0301
# For more currencies see:
# Definitions of ISO 4217 Currencies
# Source: http://www.iso.org/iso/support/faqs/faqs_widely_used_standards/widely_used_standards_other/currency_codes/currency_codes_list-1.htm
# Source: http://www.currency-iso.org/iso_index/iso_tables/iso_tables_a1.htm
CURRENCY['USD'] = Currency(alphabetic_code='USD', numeric_code=840, currency='US Dollar',      minor_unit_precision=2)
CURRENCY['GBP'] = Currency(alphabetic_code='GBP', numeric_code=826, currency='Pound Sterling', minor_unit_precision=2)
CURRENCY['EUR'] = Currency(alphabetic_code='EUR', numeric_code=978, currency='Euro',           minor_unit_precision=2)
CURRENCY['JPY'] = Currency(alphabetic_code='JPY', numeric_code=392, currency='Yen',            minor_unit_precision=0)
# pylint: enable=C0301


def get_currency(alphabetic_code):
    return CURRENCY[alphabetic_code]


def get_currency_meta():
    return dict((k, v.to_dict()) for k, v in CURRENCY.items())


# pylint: disable=R0915
def tests():
    from random import randint

    usd = get_currency('USD')
    yen = get_currency('JPY')

    try:
        _ = Money(usd, minor_amount=0.1)
        assert False, 'Init Test 1'
    except TypeError:
        pass

    try:
        _ = Money(usd, 0.001)
        assert False, 'Init Test 2'
    except TypeError:
        pass

    try:
        Money(yen, 0.1)
        assert False, 'Init Test 3'
    except TypeError:
        pass

    try:
        _ = Money(usd, 123456789.001)
        assert False, 'Large Init Test'
    except TypeError:
        pass

    assert Money(usd, 1) == Money(usd, 1), 'Equality Test 1'
    assert Money(usd, 1) == Money(usd, minor_amount=100), 'Equality Test 2'
    assert Money(usd, 0.1) == Money(usd, minor_amount=10), 'Equality Test 3'
    assert Money(yen, minor_amount=1) == Money(yen, 1), 'Equality Test 4'

    assert not (Money(usd, 2) == Money(usd, 1)), 'Equality Test 5'
    assert not (Money(usd, 1) == Money(usd, minor_amount=101)), 'Equality Test 6'
    assert not (Money(yen, minor_amount=100) == Money(yen, 1)), 'Equality Test 7'

    try:
        _ = (Money(yen, 1) == 1)
        assert False, 'Equality Test 8'
    except TypeError:
        pass

    try:
        _ = (Money(yen, 1) == Money(usd, 1))
        assert False, 'Equality Test 9'
    except TypeError:
        pass

    offsets = [0, 10, 40, 50, 90, 100, 150, 1500, 15000, randint(0, 9999999)]
    for offset in offsets:
        for v in xrange(1000):
            v = v * 0.01 + offset
            try:
                assert Money(usd, v) == Money(usd, minor_amount=round(v * 100, 0)), 'Large Equality Test All %f' % v
            except TypeError:
                print 'Large Equality Test All USD %5.10f' % v
                raise

    assert Money(usd, 2) != Money(usd, 1), 'Inequality Test 1'
    assert Money(usd, 1) != Money(usd, minor_amount=101), 'Inequality Test 2'
    assert Money(yen, minor_amount=100) != Money(yen, 1), 'Inequality Test 3'

    assert not (Money(usd, 1) != Money(usd, 1)), 'Inequality Test 4'
    assert not (Money(usd, 1) != Money(usd, minor_amount=100)), 'Inequality Test 5'
    assert not (Money(usd, 0.1) != Money(usd, minor_amount=10)), 'Inequality Test 6'
    assert not (Money(yen, minor_amount=1) != Money(yen, 1)), 'Inequality Test 7'

    try:
        _ = (Money(yen, 1) != 1)
        assert False, 'Inequality Test 8'
    except TypeError:
        pass

    try:
        _ = (Money(yen, 1) != Money(usd, 1))
        assert False, 'Inequality Test 9'
    except TypeError:
        pass

    assert Money(usd, 1).major_amount() == 1, 'Value Test 1'
    assert Money(usd, minor_amount=100).major_amount() == 1, 'Value Test 2'
    assert Money(usd, minor_amount=25).major_amount() == 0.25, 'Value Test 3'
    assert Money(usd, 0.1).major_amount() == 0.1, 'Value Test 4'

    assert Money(usd, 1.59).major_amount() == 1.59, 'Value Test 5'
    assert Money(usd, 1.99).major_amount() == 1.99, 'Value Test 6'
    assert Money(usd, 0.99).major_amount() == 0.99, 'Value Test 7'
    assert Money(usd, 1.29).major_amount() == 1.29, 'Value Test 8'

    assert '%s' % Money(usd, 1) == '1.00', 'Repr Test 1'
    assert '%s' % Money(usd, minor_amount=100) == '1.00', 'Repr Test 2'
    assert '%s' % Money(usd, minor_amount=25) == '0.25', 'Repr Test 3'
    assert '%s' % Money(usd, 0.1) == '0.10', 'Repr Test 4'

    assert +Money(usd, minor_amount=25) == Money(usd, minor_amount=25), 'Pos Test 1'

    assert -Money(usd, 1) == Money(usd, -1), 'Negate Test 1'
    assert -Money(usd, minor_amount=25) == Money(usd, minor_amount=-25), 'Negate Test 2'

    assert Money(usd, 1) + Money(usd, 0.5) == Money(usd, 1.5), 'Add Test 1'
    assert Money(usd, 1) + Money(usd, minor_amount=25) == Money(usd, 1.25), 'Add Test 2'
    assert Money(usd, 1) + Money(usd, minor_amount=25) == Money(usd, minor_amount=125), 'Add Test 3'
    try:
        _ = Money(usd, 1) + Money(yen, 10)
        assert False, 'Add Test 4'
    except TypeError:
        pass

    try:
        _ = Money(usd, 1) + 1
        assert False, 'Add Test 5'
    except TypeError:
        pass

    assert Money(usd, 1) - Money(usd, 0.5) == Money(usd, 0.5), 'Subtract Test 1'
    assert Money(usd, 1) - Money(usd, minor_amount=25) == Money(usd, 0.75), 'Subtract Test 2'
    assert Money(usd, 1) - Money(usd, minor_amount=25) == Money(usd, minor_amount=75), 'Subtract Test 3'
    try:
        _ = Money(usd, 1) - Money(yen, 10)
        assert False, 'Subtract Test 4'
    except TypeError:
        pass

    try:
        _ = Money(usd, 1) - 1
        assert False, 'Subtract Test 5'
    except TypeError:
        pass

    assert Money(usd, 1) * 2 == Money(usd, 2), 'Multiply Test 1'
    assert Money(usd, 2.5) * 3 == Money(usd, 7.5), 'Multiply Test 2'
    assert Money(usd, minor_amount=25) * 4 == Money(usd, 1), 'Multiply Test 3'
    try:
        _ = Money(usd, 1) * Money(usd, 10)
        assert False, 'Multiply Test 4'
    except TypeError:
        pass

    assert Money(usd, 2) / 2 == Money(usd, 1), 'Divide Test 1'
    assert Money(usd, 7.5) / 3 == Money(usd, 2.5), 'Divide Test 2'
    assert Money(usd, minor_amount=100) / 4 == Money(usd, 0.25), 'Divide Test 3'
    try:
        _ = Money(usd, 1) / Money(usd, 10)
        assert False, 'Divide Test 4'
    except TypeError:
        pass

    print 'All tests passed'
# pylint: enable=R0915

if __name__ == '__main__':
    tests()
