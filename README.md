# OCM: Object Command Mapping

I often need to call command line software in Python scripts, usually through `subprocess`, for example:

```python
import subprocess


subprocess.run(['ls','-l','/Users/dev'])
```

The following points of using `subprocess` make me feel inconvenient:

1. Need to determine the order of the parameters to determine the order of the list
2. No parameter verification
3. It is not convenient to get parameters, for example: `['ls','-l','/Users/dev']`, I want to get the directory

In response to the above pain points, I implemented OCM. OCM is named after ORM. When we use Python for database query, we often need to do this:

```python
cursor.execute('SELECT xxx FROM xxx WHERE xxx')
print(cursor.fetchone()[1])
```

Very inconvenient, you can use ORM to query like this:


```python
xxx = XXX.objects.filter(xxx=xxx).first()
print(xxx.xxx)
```

So for OCM, what I want to achieve is to run a command like this:


```python
ls = LsCommand(is_long=True, directory='.')
ls()
```

## Installation

```
pip install ocm
```

## Philosophy

Like [click](https://github.com/pallets/click), OCM abstracts command-line parameters into two types:

1. `Option`, can be specified by `-l`, `--long`, `-o foo.txt`, etc.
2. `Argument`, can only pass the value directly, no key
   
For example: in `ls -l /Users/dev`:

1. `-l` is `Option` (here there is no value after `-l`, it is called `flag`)
2. `/Users/dev` is `Argument`

## Usage

```python
from ocm import Command, Option, Argument



class LS(Command):
    is_long = Option('-l', name='is_long', is_flag=True, required=False)
    directory = Argument(name='directory', required=True)

    class Meta:
        exe ='ls'


ls = LS(is_long=True, directory='/Users/dev')
print(ls.is_long)
print(ls.directory)
result = ls()
print(result.stdout)
print(result.stderr)
```

## Parameter Type

OCM built-in parameter types:

1. `StringParamType`
2. `IntegerParamType`
3. `FloatParamType`
4. `ChoicesParamType`

Instructions:

```python
from ocm import Command, Option, Argument, IntegerParamType


class Head(Command):
    number = Option('-n', name='number', param_type=IntegerParamType(), required=False)
    file = Argument(name='file')

    class Meta:
        exe ='head'


head = Head(number=10, file='ocm.py')
result = head()
```


Custom parameter type:

```python
from ocm import ParamType


class MyParamType(ParamType):
    def convert(self, value, param, ctx):
        pass

    def show(self, value):
        pass
```

The `convert method` is responsible for converting the incoming data into the correct data:

1. `value`, the incoming data
2. `param`, the parameter object
3. `ctx`, all other incoming parameters

The `show method` is responsible for converting the data into a string to run on the command line:

1. `value`, the incoming data, generally the result of conversion by the convert method

## Callback

The callback function can perform additional verification and conversion based on the data passed in by the user.

```python
from ocm import Command, Option, Argument, IntegerParamType


def add_one(value, param, ctx):
    if value is None:
        return None
    return value + 1


class Head(Command):
    number = Option(
        '-n', name='number', param_type=IntegerParamType(), required=False, callback=add_one
    )
    file = Argument(name='file')

    class Meta:
        exe ='head'


head = Head(number=10, file='ocm.py')
result = head()
```

## API

### Option

1. `__init__(self, key, is_flag=False, default=None, param_type=None, required=None, callback=None, multiple=False)`

parameter:

1. `key`, the key of the `Option` when splicing into a command line, for example, `-l`
2. `name`, the name of the parameter
3. `is_flag`, whether this parameter is `flag`, see the description in the concept section, the default is `False`
4. `default`, the default value of the parameter
5. `param_type`, the type of the parameter, see the description of the parameter type
6. `required`, is it necessary?
7. `callback`, some parameters need to be converted according to the input value, you can customize the callback function, see the description of the callback function section
8. `multiple`, whether this parameter will be passed in multiple, for example, `ls -l /Users/dev /Users/dev/Downloads/`, `directory` parameter is passed twice

2. `process_value(self, value, ctx)`

Verify `value` according to the rules, and return the verified result:

1. `value`, the value to be verified
2. `ctx`, the value of other parameters passed in at the same time, used for the verification of the parameter

### Argument

1. `__init__(self, is_flag=False, default=None, param_type=None, required=None, callback=None, multiple=False)`

parameter:

1. `name`, the name of the parameter
2. `default`, the default value of the parameter
3. `param_type`, the type of the parameter, see the description of the parameter type
4. `required`, is it necessary?
5. `callback`, some parameters need to be converted according to the input value, you can customize the callback function, see the description of the callback function section
6. `multiple`, whether this parameter will be passed in multiple, for example, `ls -l /Users/dev /Users/dev/Downloads/`, `directory` parameter is passed twice

2. `process_value(self, value, ctx)`

Verify `value` according to the rules, and return the verified result:

1. `value`, the value to be verified
2. `ctx`, the value of other parameters passed in at the same time, used for the verification of the parameter