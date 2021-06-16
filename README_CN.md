# OCM: 对象命令映射

我经常需要在Python脚本里面调用命令行软件，通常情况下我通过`subprocess`来实现，例如：

```python
import subprocess


subprocess.run(['ls', '-l', '/Users/dev'])
```

使用`subprocess`有以下几点令我觉得不太方便：

1. 需要去确定参数顺序来确定列表的顺序
2. 没有参数校验
3. 获取参数不方便，例如：`['ls', '-l', '/Users/dev']`，我想要获取目录

针对以上痛点，我实现了OCM。OCM得名于ORM，当我们使用Python进行数据库查询时，往往需要这样：

```python
cursor.execute('SELECT xxx FROM xxx WHERE xxx')
print(cursor.fetchone()[1])
```

非常不方便，使用ORM可以像这样进行查询：


```python
xxx = XXX.objects.filter(xxx=xxx).first()
print(xxx.xxx)
```

所以对于OCM来讲，想要实现的是，这样运行一个命令：


```python
ls = LsCommand(is_long=True, directory='.')
ls()
```

## 安装

```
pip install python-ocm
```

## 理念

OCM将命令行参数抽象为两种：

1. `Option`，可以通过`-l`，`--long`，`-o foo.txt`等方式指定
2. `Argument`，只能直接传值，没有键
   
例如：`ls -l /Users/dev`中：

1. `-l`是`Option`（这里`-l`后面没有值，被称为`flag`）
2. `/Users/dev`是`Argument`

## 使用

```python
from ocm import Command, Option, Argument



class LS(Command):
    is_long = Option('-l', name='is_long', is_flag=True, required=False)
    directory = Argument(name='directory', required=True)

    class Meta:
        exe = 'ls'


ls = LS(is_long=True, directory='/Users/dev')
print(ls.is_long)
print(ls.directory)
result = ls()
print(result.stdout)
print(result.stderr)
```

## 参数类型

OCM内置参数类型：

1. `StringParamType`
2. `IntegerParamType`
3. `FloatParamType`
4. `ChoicesParamType`

使用方法：

```python
from ocm import Command, Option, Argument, IntegerParamType


class Head(Command):
    number = Option('-n', name='number', param_type=IntegerParamType(), required=False)
    file = Argument(name='file')

    class Meta:
        exe = 'head'


head = Head(number=10, file='ocm.py')
result = head()
```


自定义参数类型：

```python
from ocm import ParamType


class MyParamType(ParamType):
    def convert(self, value, param, ctx):
        pass

    def show(self, value):
        pass
```

`convert方法`负责将传入的数据转换为正确的数据：

1. `value`，传入的数据
2. `param`，参数对象
3. `ctx`，其他所有传入的参数

`show方法`负责将数据转换为字符串，以在命令行运行：

1. `value`，传入的数据，一般为convert方法转换的结果

## 回调函数

回调函数可以在用户传入的数据的基础上进行额外的验证、转换。

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
        exe = 'head'


head = Head(number=10, file='ocm.py')
result = head()
```

## API

### Option

1. `__init__(self, key, is_flag=False, default=None, param_type=None, required=None, callback=None, multiple=False)`

参数：

1. `key`，该`Option`在拼接为命令行时的键，例如，`-l`
2. `name`，该参数的名称
3. `is_flag`，该参数是否为`flag`，见理念部分说明，默认为`False`
4. `default`，该参数的默认值
5. `param_type`，该参数的类型，见参数类型部分说明
6. `required`，是否必须
7. `callback`，有些参数需要根据输入值进行转换可以自定义回调函数，见回调函数部分说明
8. `multiple`，该参数是否会传入多个，例如，`ls -l /Users/dev /Users/dev/Downloads/`，`directory`参数传了两次

2. `process_value(self, value, ctx)`

根据规则对`value`进行验证，返回验证过后的结果：

1. `value`，需要验证的值
2. `ctx`，同时传入的其他参数的值，用于该参数的验证

### Argument

1. `__init__(self, is_flag=False, default=None, param_type=None, required=None, callback=None, multiple=False)`

参数：

1. `name`，该参数的名称
2. `default`，该参数的默认值
3. `param_type`，该参数的类型，见参数类型部分说明
4. `required`，是否必须
5. `callback`，有些参数需要根据输入值进行转换可以自定义回调函数，见回调函数部分说明
6. `multiple`，该参数是否会传入多个，例如，`ls -l /Users/dev /Users/dev/Downloads/`，`directory`参数传了两次

2. `process_value(self, value, ctx)`

根据规则对`value`进行验证，返回验证过后的结果：

1. `value`，需要验证的值
2. `ctx`，同时传入的其他参数的值，用于该参数的验证
