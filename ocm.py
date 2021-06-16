# -*- coding: utf-8 -*-
"""
OCM: object Command Mapping
"""
import sys
import json
import logging
import subprocess as sp
from shutil import which
from collections import OrderedDict


logger = logging.getLogger('OCM')
RUNNING = 0
SUCCESS = 1
FAILED = -1


class OCMError(Exception):
    """ocm error"""


class BadParameter(OCMError):
    """bad parameter error"""


class CommandError(OCMError):
    """raises when command encounter errors"""


class ParamType:
    def convert(self, value, param, ctx):
        return value

    def show(self, value):
        return value


class StringParamType(ParamType):
    def convert(self, value, param, ctx):
        if isinstance(value, bytes):
            enc = get_enc()
            try:
                value = value.decode(enc)
            except UnicodeError:
                value = value.decode("utf-8", "replace")
        if not isinstance(value, str):
            value = str(value)
        return value


class IntegerParamType(ParamType):
    def convert(self, value, param, ctx):
        try:
            return int(value)
        except ValueError:
            raise BadParameter(
                f'{param.name}: invalid integer parameter value {value}'
            )

    def show(self, value):
        return str(value)


class FloatParamType(ParamType):
    def __init__(self, precision=2):
        self.precision = precision

    def convert(self, value, param, ctx):
        try:
            return float(value)
        except ValueError:
            raise BadParameter(
                f'{param.name}: invalid float parameter value {value}'
            )

    def show(self, value):
        temp = f'%0.{self.precision}f'
        return temp % round(value, self.precision)


class ChoicesParamType(ParamType):
    def __init__(self, choices):
        self.choices = choices

    def convert(self, value, param, ctx):
        if value not in self.choices:
            raise BadParameter(
                f'{param.name}: invalid value {value}, '
                f'should be one of {", ".join(self.choices)}'
            )
        return value

    def show(self, value):
        return str(value)


def get_enc():
    return sys.getfilesystemencoding() or sys.getdefaultencoding()


def convert_param_type(param_type, default):
    """convert ParamType according to default"""
    if isinstance(param_type, ParamType):
        return param_type

    if not default:
        return StringParamType()

    if isinstance(default, int):
        return IntegerParamType()

    if isinstance(default, str):
        return StringParamType()

    if isinstance(default, float):
        return FloatParamType()

    if isinstance(default, (list, tuple)):
        return convert_param_type(param_type, default[0])

    if default.__class__.__name__ == 'function':
        return convert_param_type(param_type, default())

    return StringParamType()


class Parameter:
    create_order = 0

    def __init__(
        self,
        name,
        default=None,
        param_type=None,
        required=None,
        callback=None,
        multiple=False,
    ):
        self.create_order = Parameter.create_order
        Parameter.create_order += 1

        if required is None:
            required = default is None

        self.name = name
        self.default = default
        self.param_type = convert_param_type(
            param_type, default
        )
        self.required = required
        self.callback = callback
        self.multiple = multiple

    def get_default(self):
        if self.default.__class__.__name__ == 'function':
            return self.default()
        return self.default

    def type_cast_value(self, value, ctx):
        if value is None:
            return () if self.multiple else None
        if self.multiple:
            if not isinstance(value, (list, tuple)):
                value = (value,)
            return tuple(self.param_type.convert(x, self, ctx) for x in value)
        return self.param_type.convert(value, self, ctx)

    def value_is_missing(self, value):
        if value is None:
            return True

        if self.multiple and value == ():
            return True

        return False

    def convert(self, value, ctx):
        value = self.type_cast_value(value, ctx)
        if self.value_is_missing(value):
            value = self.get_default()

        if self.required and self.value_is_missing(value):
            raise BadParameter(f'{self.name} is required.')

        if self.callback is not None:
            value = self.callback(value, self, ctx)

        return value

    def show(self, value):
        raise NotImplemented(f'{self.__class__.__name__}.show not implemented.')


class Option(Parameter):
    def __init__(self, key, is_flag=False, **kwargs):
        if not isinstance(key, str):
            raise BadParameter(f'invalid key {key}')
        self.key = key
        self.is_flag = is_flag
        super().__init__(**kwargs)

    def show(self, value):
        lst = []
        if (not self.required) and self.value_is_missing(value):
            return lst
        if self.multiple:
            if not isinstance(value, (list, tuple)):
                value = (value,)
            if self.is_flag:
                for x in value:
                    if x:
                        lst.append(self.key)
            else:
                for x in value:
                    lst.append(self.key)
                    lst.append(self.param_type.show(x))
        else:
            if self.is_flag:
                if value:
                    lst.append(self.key)
            else:
                lst.append(self.key)
                lst.append(self.param_type.show(value))
        return lst

    def convert(self, value, ctx):
        if self.is_flag:
            return True if value else False
        return super().convert(value, ctx)


class Argument(Parameter):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def show(self, value):
        lst = []
        if (not self.required) and self.value_is_missing(value):
            return lst
        if self.multiple:
            if not isinstance(value, (list, tuple)):
                value = (value,)
            for x in value:
                lst.append(self.param_type.show(x))
        else:
            lst.append(self.param_type.show(value))
        return lst


class CommandBase(type):
    def __new__(cls, clsname, bases, attrs):
        # exclude Command itself
        parents = [base for base in bases if isinstance(base, CommandBase)]
        if not parents:
            return type.__new__(cls, clsname, bases, attrs)

        # parameters
        parameters = []
        need_pop_names = []
        for name, parameter in attrs.items():
            if isinstance(parameter, Parameter):
                need_pop_names.append(name)
                parameters.append((name, parameter))
        for name in need_pop_names:
            attrs.pop(name)
        parameters = OrderedDict(sorted(parameters, key=lambda x: x[1].create_order))
        attrs['_parameters'] = parameters

        # meta
        meta_cls = attrs.pop('Meta', None)
        meta = OrderedDict()
        exe = getattr(meta_cls, 'exe', None)
        if not exe:
            raise OCMError('exe attribute of Meta class must be set.')
        meta['exe'] = exe
        sub_commands = getattr(meta_cls, 'sub_commands', [])
        if sub_commands is None:
            sub_commands = []
        if not isinstance(sub_commands, (list, tuple)):
            raise OCMError('sub_commands of Meta class must be a list')
        meta['sub_commands'] = sub_commands
        attrs['_meta'] = meta
        return type.__new__(cls, clsname, bases, attrs)


class Result:
    def __init__(self, stdout, stderr):
        self.stdout = stdout
        self.stderr = stderr
        self._irs = None

    def __iter__(self):
        return iter((('stdout', self.stdout), ('stderr', self.stderr)))

    def __repr__(self):
        return f'<Result: {self.stdout[: 10]}>'

    def _populate_irs(self):
        self._irs = OrderedDict()
        for line in self.stdout.split('\n'):
            temp = line.split(':', 2)
            if (len(temp) == 3) and (temp[0] == 'OCMIR'):
                self._irs[temp[1]] = temp[2]

    def __getitem__(self, item):
        if self._irs is None:
            self._populate_irs()
        if item not in self._irs:
            raise CommandError(f'Intermediate result {item} not found.')
        value = self._irs[item]
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass
        return value


class Command(metaclass=CommandBase):

    def __init__(self, **kwargs):
        for name, parameter in self._parameters.items():
            value = kwargs.get(name, None)
            value = parameter.convert(value, kwargs)
            setattr(self, name, value)
        for name in self._parameters:
            kwargs.pop(name, None)
        if len(kwargs) > 0:
            raise CommandError(f'Undefined parameters {", ".join(kwargs.keys())}.')
        super().__init__()

    def _to_list(self):
        lst = [self._meta['exe']]
        lst += self._meta['sub_commands']
        for name, parameter in self._parameters.items():
            lst += parameter.show(getattr(self, name))
        return lst

    def __iter__(self):
        return iter(self._to_list())

    def __repr__(self):
        return ' '.join(self._to_list())

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            raise NotImplemented(
                f'Compare {self.__class__.__name__} to '
                f'{other.__class__.__name__} not implemented.'
            )
        return str(self) == str(other)

    def __hash__(self):
        return hash(str(self))

    def check(self):
        return which(self._meta['exe']) is not None

    def __call__(self, **kwargs):
        if ('stdout' in kwargs) or ("stdin" in kwargs):
            raise CommandError(
                'OCM forced to pass in the stdin, stdout parameters, '
                'these two parameters do not need to be passed'
            )
        if not self.check():
            raise OCMError(f'{self._meta["exe"]} not installed')
        p = sp.Popen(
            self._to_list(),
            stdout=sp.PIPE,
            stderr=sp.PIPE,
            **kwargs
        )
        logger.info(f'Running command {self}')
        logger.info('Output:')
        stdout = []
        enc = get_enc()
        for raw_line in iter(p.stdout.readline, b''):
            line = raw_line.decode(enc)
            stdout.append(line)
            logger.info(line.rstrip())
        stdout = ''.join(stdout)
        p.wait()
        if p.returncode:
            raise CommandError(f'{self} failed.')
        stderr = p.stderr.read().decode(enc)
        return Result(
            stdout=stdout,
            stderr=stderr
        )


if __name__ == '__main__':
    class Ls(Command):
        is_long = Option('-l', name='is_long', is_flag=True)
        directory = Argument(name='directory')

        class Meta:
            exe = 'ls'

    ls = Ls(
        is_long=True,
        directory='/'
    )
    result = ls()
    print(result.stdout)
