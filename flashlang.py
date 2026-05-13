#!/usr/bin/env python3
"""
FlashLang Language Interpreter - Версия 1.4.2
- ИСПРАВЛЕН ЦИКЛ for (переменная видна в выражениях)
- ДЕКОРАТОРЫ (работающие)
- ИСПРАВЛЕНА АРИФМЕТИКА через eval()
"""

import os
import sys
import re
import json
import logging
import traceback
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('FlashLang')


class FlashLangInterpreter:
    def __init__(self, debug=False):
        self.variables = {}
        self.locals = {}
        self.functions = {}
        self.classes = {}
        self.python_functions = {}
        self.python_classes = {}
        self.modules = {}
        self.flash_modules = {}
        self.return_value = None
        self.break_flag = False
        self.continue_flag = False
        self.debug = debug
        self.flash_home = Path(__file__).parent
        self.packages_dir = self.flash_home / "lib"
        self.skip_else = False

        if debug:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)

        self._setup_builtins()
        self._setup_builtin_decorators()
        logger.debug("FlashLang Interpreter initialized")

    def _setup_builtins(self):
        try:
            import math
            self.modules['math'] = math
            logger.debug("Loaded math module")
        except ImportError:
            pass
        try:
            import random
            self.modules['random'] = random
            logger.debug("Loaded random module")
        except ImportError:
            pass
        self.modules['json'] = json
        logger.debug("Loaded json module")

    def _setup_builtin_decorators(self):
        def log_decorator(func):
            def wrapper(*args, **kwargs):
                logger.info(f"Calling {func.__name__} with args={args}")
                result = func(*args, **kwargs)
                logger.info(f"{func.__name__} returned {result}")
                return result
            return wrapper
        
        def timer_decorator(func):
            def wrapper(*args, **kwargs):
                start = time.time()
                result = func(*args, **kwargs)
                end = time.time()
                logger.info(f"{func.__name__} took {end - start:.4f}s")
                return result
            return wrapper
        
        def deprecated_decorator(func):
            def wrapper(*args, **kwargs):
                logger.warning(f"Function {func.__name__} is deprecated")
                return func(*args, **kwargs)
            return wrapper
        
        self.python_functions['log'] = log_decorator
        self.python_functions['timer'] = timer_decorator
        self.python_functions['deprecated'] = deprecated_decorator
        logger.debug("Built-in decorators registered")

    def _debug_print(self, msg):
        if self.debug:
            logger.debug(msg)

    def _is_comment(self, line: str) -> bool:
        return line.strip().startswith('//')

    def _strip_comments(self, line: str) -> str:
        in_string = False
        quote_char = None
        i = 0
        while i < len(line):
            ch = line[i]
            if ch in ('"', "'") and not in_string:
                in_string = True
                quote_char = ch
            elif ch == quote_char and in_string:
                in_string = False
                quote_char = None
            elif ch == '/' and not in_string:
                if i + 1 < len(line) and line[i + 1] == '/':
                    return line[:i]
            i += 1
        return line

    def _dedent_lines(self, lines: List[str]) -> List[str]:
        if not lines:
            return lines
        min_indent = float('inf')
        for line in lines:
            if line.strip():
                indent = len(line) - len(line.lstrip())
                if indent < min_indent:
                    min_indent = indent
        if min_indent == float('inf'):
            return lines
        return [line[min_indent:] if line.strip() else '' for line in lines]

    def _evaluate_py_expression(self, py_code: str, context: Dict) -> Any:
        try:
            exec_context = {
                **self.modules,
                **self.variables,
                **self.locals,
                **context,
                **self.python_functions,
                **self.python_classes
            }
            return eval(py_code.strip(), exec_context)
        except Exception as e:
            logger.error(f"Python error: {e}")
            return None

    def _get_variable(self, name: str, context: Dict = None) -> Any:
        if context is None:
            context = {}
        if name in context:
            return context[name]
        if name in self.locals:
            return self.locals[name]
        if name in self.variables:
            return self.variables[name]
        if name in self.modules:
            return self.modules[name]
        if name in self.python_functions:
            return self.python_functions[name]
        if name in self.python_classes:
            return self.python_classes[name]
        if name in self.classes:
            return self.classes[name]
        return None

    def _is_string_literal(self, expr: str) -> bool:
        expr = expr.strip()
        return (expr.startswith('"') and expr.endswith('"')) or (
            expr.startswith("'") and expr.endswith("'")
        )

    def _is_arithmetic_expression(self, expr: str) -> bool:
        if '+' in expr or '-' in expr or '*' in expr or '/' in expr:
            return True
        return False

    def _replace_variables_in_expr(self, expr: str, context: Dict) -> str:
        words = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', expr)

        result = expr
        for word in set(words):
            if word in (
                'True', 'False', 'None', 'and', 'or', 'not', 'in', 'is',
                'if', 'else', 'for', 'while', 'break', 'continue',
                'return', 'def', 'class', 'lambda', 'import', 'from'
            ):
                continue

            value = self._get_variable(word, context)
            if value is not None:
                if isinstance(value, str):
                    escaped = value.replace("'", "\\'")
                    result = re.sub(r'\b' + word + r'\b', f"'{escaped}'", result)
                else:
                    result = re.sub(r'\b' + word + r'\b', str(value), result)

        return result

    def evaluate_expression(self, expr: str, context: Dict = None) -> Any:
        if context is None:
            context = {
                **self.variables,
                **self.locals,
                **self.python_functions,
                **self.python_classes,
                **self.classes
            }

        expr = expr.strip()
        if not expr:
            return None

        expr = self._strip_comments(expr)
        self._debug_print(f"Evaluating: '{expr}'")

        # Handle arithmetic expressions
        if self._is_arithmetic_expression(expr):
            if '+' in expr:
                parts = expr.split('+')
                is_string_concat = False
                for part in parts:
                    part = part.strip()
                    if self._is_string_literal(part):
                        is_string_concat = True
                        break
                    val = self._get_variable(part, context)
                    if isinstance(val, str):
                        is_string_concat = True
                        break
                if is_string_concat:
                    return self._evaluate_concatenation(expr, context)
            return self._evaluate_arithmetic(expr, context)

        # Function call
        if '(' in expr and expr.endswith(')'):
            return self._parse_and_call(expr, context)

        # py: expression
        if expr.startswith('py:'):
            return self._evaluate_py_expression(expr[3:], context)

        # new ClassName()
        if expr.startswith('new '):
            match = re.match(r'new\s+([\w.]+)\((.*)\)$', expr)
            if match:
                class_path = match.group(1)
                args_str = match.group(2)
                args = self._parse_arguments(args_str, context)

                if '.' in class_path:
                    parts = class_path.split('.')
                    module_name = parts[0]
                    class_name = parts[1]
                    if module_name in self.flash_modules:
                        if class_name in self.flash_modules[module_name].get('classes', {}):
                            return self._create_flash_instance_from_module(
                                module_name, class_name, args
                            )

                if class_path in self.classes:
                    return self._create_flash_instance(class_path, args)
                if class_path in self.python_classes:
                    try:
                        return self.python_classes[class_path](*args)
                    except Exception as e:
                        logger.error(f"Error creating {class_path}: {e}")
                        return None

        # Array literal
        if expr.startswith('[') and expr.endswith(']'):
            return self._parse_array_literal(expr[1:-1], context)

        # Number
        stripped = expr.lstrip('-')
        if stripped.replace('.', '').isdigit():
            return float(expr) if '.' in expr else int(expr)

        if expr.lower() == 'true':
            return True
        if expr.lower() == 'false':
            return False
        if expr.lower() == 'null':
            return None

        if '>=' in expr:
            parts = expr.split('>=')
            return self.evaluate_expression(parts[0], context) >= self.evaluate_expression(parts[1], context)
        if '<=' in expr:
            parts = expr.split('<=')
            return self.evaluate_expression(parts[0], context) <= self.evaluate_expression(parts[1], context)
        if '==' in expr:
            parts = expr.split('==')
            return self.evaluate_expression(parts[0], context) == self.evaluate_expression(parts[1], context)
        if '>' in expr:
            parts = expr.split('>')
            return self.evaluate_expression(parts[0], context) > self.evaluate_expression(parts[1], context)
        if '<' in expr:
            parts = expr.split('<')
            return self.evaluate_expression(parts[0], context) < self.evaluate_expression(parts[1], context)

        if self._is_string_literal(expr):
            return expr[1:-1]

        if '.' in expr:
            parts = expr.split('.')
            if parts[0] == 'this':
                obj = self.locals.get('this')
                if obj and isinstance(obj, dict) and '_class' in obj:
                    field_name = parts[1]
                    if field_name in obj['_fields']:
                        return obj['_fields'][field_name]
                return None
            obj = self._get_variable(parts[0], context)
            if obj:
                if isinstance(obj, dict) and '_class' in obj:
                    if len(parts) > 1 and parts[1] in obj['_fields']:
                        return obj['_fields'][parts[1]]
                if isinstance(obj, dict):
                    return obj.get(parts[1])
            return None

        result = self._get_variable(expr, context)
        if result is not None:
            return result

        return expr

    def _evaluate_concatenation(self, expr: str, context: Dict) -> Any:
        parts = expr.split('+')
        result_parts = []
        for part in parts:
            val = self.evaluate_expression(part.strip(), context)
            result_parts.append(str(val) if val is not None else '')
        return ''.join(result_parts)

    def _evaluate_arithmetic(self, expr: str, context: Dict) -> Any:
        expr = expr.strip()

        while expr.startswith('(') and expr.endswith(')'):
            expr = expr[1:-1].strip()

        py_expr = self._replace_variables_in_expr(expr, context)

        logger.debug(f"Arithmetic eval: {py_expr}")

        try:
            safe_globals = {
                '__builtins__': {
                    'abs': abs, 'round': round, 'int': int, 'float': float,
                    'str': str, 'len': len
                }
            }
            # БЕРЁМ ВСЕ ПЕРЕМЕННЫЕ из variables И locals
            eval_context = {}
            for key, value in {**self.variables, **self.locals, **context}.items():
                if not callable(value) and not key.startswith('_'):
                    eval_context[key] = value
            
            result = eval(py_expr, safe_globals, eval_context)

            if isinstance(result, float) and result.is_integer():
                return int(result)
            return result
        except Exception as e:
            logger.error(f"Arithmetic error in '{py_expr}': {e}")
            return None

    def _parse_array_literal(self, content: str, context: Dict) -> List[Any]:
        if not content.strip():
            return []
        items = []
        current = ''
        bracket = brace = paren = 0
        in_string = False
        quote = None
        for ch in content:
            if ch in ('"', "'") and not in_string:
                in_string = True
                quote = ch
                current += ch
            elif ch == quote and in_string:
                in_string = False
                quote = None
                current += ch
            elif in_string:
                current += ch
            elif ch == '[':
                bracket += 1
                current += ch
            elif ch == ']':
                bracket -= 1
                current += ch
            elif ch == '{':
                brace += 1
                current += ch
            elif ch == '}':
                brace -= 1
                current += ch
            elif ch == '(':
                paren += 1
                current += ch
            elif ch == ')':
                paren -= 1
                current += ch
            elif ch == ',' and bracket == 0 and brace == 0 and paren == 0:
                if current.strip():
                    items.append(self.evaluate_expression(current.strip(), context))
                current = ''
            else:
                current += ch
        if current.strip():
            items.append(self.evaluate_expression(current.strip(), context))
        return items

    def _create_flash_instance(self, class_name: str, args: List[Any]) -> Any:
        logger.debug(f"Creating instance of {class_name} with args: {args}")
        cls = self.classes[class_name]
        instance = {'_class': class_name, '_fields': {}}

        for field_name, field_info in cls.get('fields', {}).items():
            instance['_fields'][field_name] = field_info.get('default')

        if 'constructor' in cls and cls['constructor'] is not None:
            old_locals = self.locals.copy()
            old_return = self.return_value

            self.locals = {'this': instance}
            params = cls['constructor'].get('params', [])
            for i, param in enumerate(params):
                val = args[i] if i < len(args) else None
                if isinstance(val, str):
                    try:
                        if val.isdigit():
                            val = int(val)
                        else:
                            val = float(val)
                    except ValueError:
                        pass
                self.locals[param] = val

            for line in cls['constructor']['body']:
                self.execute_line(line)

            self.locals = old_locals
            self.return_value = old_return

        return instance

    def _create_flash_instance_from_module(
        self, module_name: str, class_name: str, args: List[Any]
    ) -> Any:
        cls = self.flash_modules[module_name]['classes'][class_name]
        instance = {'_class': f"{module_name}.{class_name}", '_fields': {}}

        for field_name, field_info in cls.get('fields', {}).items():
            instance['_fields'][field_name] = field_info.get('default')

        if 'constructor' in cls and cls['constructor'] is not None:
            old_locals = self.locals.copy()
            old_return = self.return_value

            self.locals = {'this': instance}
            params = cls['constructor'].get('params', [])
            for i, param in enumerate(params):
                val = args[i] if i < len(args) else None
                if isinstance(val, str):
                    try:
                        if val.isdigit():
                            val = int(val)
                        else:
                            val = float(val)
                    except ValueError:
                        pass
                self.locals[param] = val

            for line in cls['constructor']['body']:
                self.execute_line(line)

            self.locals = old_locals
            self.return_value = old_return

        return instance

    def _import_flash_module(self, module_name: str) -> bool:
        module_path = module_name.replace('.', os.sep)

        search_paths = [
            Path.cwd(),
            Path.cwd() / "lib",
            self.packages_dir,
            Path(__file__).parent / "lib",
        ]

        for search_path in search_paths:
            module_file = search_path / f"{module_path}.flang"
            if not module_file.exists():
                module_file = search_path / f"{module_name}.flang"

            if module_file.exists():
                try:
                    logger.info(f"Importing Flash module: {module_name} from {module_file}")
                    with open(module_file, 'r', encoding='utf-8') as f:
                        code = f.read()

                    if not hasattr(self, '_module_context'):
                        self._module_context = {}

                    module_context = {**self.modules, **self.variables}
                    self._module_context[module_name] = module_context

                    python_blocks = self._extract_python_blocks(code)
                    for block in python_blocks:
                        try:
                            exec(block.strip(), module_context)
                        except Exception as e:
                            logger.error(f"Python block error in {module_name}: {e}")

                    for name, obj in module_context.items():
                        if not name.startswith('_') and name not in self.modules:
                            if isinstance(obj, type):
                                self.python_classes[f"{module_name}.{name}"] = obj
                                logger.debug(f"Registered Python class: {module_name}.{name}")
                            elif callable(obj):
                                self.python_functions[f"{module_name}.{name}"] = obj
                                logger.debug(f"Registered Python function: {module_name}.{name}")

                    old_functions = self.functions.copy()
                    old_variables = self.variables.copy()
                    old_classes = self.classes.copy()

                    self.execute(code)

                    new_functions = {}
                    for name, func in self.functions.items():
                        if name not in old_functions:
                            new_functions[name] = func

                    new_variables = {}
                    for name, val in self.variables.items():
                        if name not in old_variables:
                            new_variables[name] = val

                    new_classes = {}
                    for name, cls in self.classes.items():
                        if name not in old_classes:
                            new_classes[name] = cls

                    self.flash_modules[module_name] = {
                        'functions': new_functions,
                        'variables': new_variables,
                        'classes': new_classes,
                        'context': module_context,
                    }

                    logger.info(f"Successfully imported: {module_name}")
                    return True

                except Exception as e:
                    logger.error(f"Error importing '{module_name}': {e}")
                    if self.debug:
                        traceback.print_exc()
                    return False

        logger.warning(f"Module '{module_name}' not found")
        return False

    def _parse_and_call(self, expr: str, context: Dict) -> Any:
        logger.debug(f"Parsing call: {expr}")

        # Method call: obj.method(args)
        if '.' in expr:
            paren_pos = expr.rfind('(')
            last_dot_pos = expr.rfind('.', 0, paren_pos)
            if last_dot_pos != -1:
                obj_expr = expr[:last_dot_pos].strip()
                method_name = expr[last_dot_pos + 1:paren_pos].strip()
                args_str = expr[paren_pos + 1:-1].strip()

                obj = self._get_variable(obj_expr, context)
                logger.debug(f"Method call: obj={obj_expr}, obj_value={obj}, method={method_name}")

                if obj and isinstance(obj, dict) and '_class' in obj:
                    class_name = obj['_class']
                    logger.debug(f"Object is instance of {class_name}")

                    cls = None
                    if '.' in class_name:
                        parts = class_name.split('.')
                        module_name = parts[0]
                        if module_name in self.flash_modules:
                            cls = self.flash_modules[module_name]['classes'].get(parts[1])
                    else:
                        cls = self.classes.get(class_name)

                    if cls:
                        if method_name in cls.get('methods', {}):
                            method = cls['methods'][method_name]
                            args = self._parse_arguments(args_str, context)

                            old_locals = self.locals.copy()
                            old_return = self.return_value

                            self.locals = {'this': obj}
                            for i, param in enumerate(method.get('params', [])):
                                self.locals[param] = args[i] if i < len(args) else None

                            for line in method['body']:
                                self.execute_line(line)
                                if self.return_value is not None:
                                    break

                            result = self.return_value
                            self.locals = old_locals
                            self.return_value = old_return
                            return result

        # Regular function call
        paren_pos = expr.find('(')
        if paren_pos != -1:
            name = expr[:paren_pos].strip()
            args_str = expr[paren_pos + 1:-1].strip()

            # Built-in functions
            if name == 'print':
                val = self.evaluate_expression(args_str, context)
                output = str(val) if val is not None else ''
                print(output)
                return output

            if name == 'input':
                prompt = self.evaluate_expression(args_str, context) if args_str else ''
                if prompt:
                    print(prompt, end='')
                return input()

            if name == 'len':
                val = self.evaluate_expression(args_str, context)
                return len(val) if val else 0

            if name == 'range':
                args = self._parse_arguments(args_str, context)
                if len(args) == 1:
                    return list(range(args[0]))
                if len(args) == 2:
                    return list(range(args[0], args[1]))
                return []

            if name == 'json_parse':
                val = self.evaluate_expression(args_str, context)
                return json.loads(val) if val else {}

            if name == 'json_stringify':
                val = self.evaluate_expression(args_str, context)
                return json.dumps(val) if val else "{}"

            args = self._parse_arguments(args_str, context)

            # Python class
            if name in self.python_classes:
                try:
                    return self.python_classes[name](*args)
                except Exception as e:
                    logger.error(f"Error creating Python class {name}: {e}")
                    return None

            # FlashLang class
            if name in self.classes:
                return self._create_flash_instance(name, args)

            # Python function
            if name in self.python_functions:
                try:
                    result = self.python_functions[name](*args)
                    logger.debug(f"Python function {name} returned: {result}")
                    return result
                except Exception as e:
                    logger.error(f"Error calling Python function {name}: {e}")
                    return None

            # FlashLang function (with decorator support)
            if name in self.functions:
                func_info = self.functions[name]
                
                # Check if function has decorators
                if 'decorators' in func_info and func_info['decorators']:
                    # Apply decorators in reverse order
                    result_func = self._create_callable_function(name, func_info)
                    for decorator_name in reversed(func_info['decorators']):
                        if decorator_name in self.python_functions:
                            decorator = self.python_functions[decorator_name]
                            result_func = decorator(result_func)
                        else:
                            logger.error(f"Decorator '{decorator_name}' not found")
                    return result_func(*args)
                else:
                    # No decorators, execute directly
                    return self._execute_flash_function(name, func_info, args)

        return None

    def _create_callable_function(self, name: str, func_info: Dict) -> Any:
        """Create a Python callable wrapper for FlashLang function"""
        def wrapper(*args):
            return self._execute_flash_function(name, func_info, list(args))
        wrapper.__name__ = name
        return wrapper

    def _execute_flash_function(self, name: str, func_info: Dict, args: List[Any]) -> Any:
        """Execute a FlashLang function in a fresh interpreter"""
        
        # Создаём новый интерпретатор
        temp_interp = FlashLangInterpreter(debug=self.debug)
        
        # Копируем всё необходимое
        temp_interp.functions = self.functions.copy()
        temp_interp.classes = self.classes.copy()
        temp_interp.python_functions = self.python_functions.copy()
        temp_interp.python_classes = self.python_classes.copy()
        temp_interp.modules = self.modules.copy()
        
        # Устанавливаем аргументы
        params = func_info.get('params', [])
        for i, param in enumerate(params):
            temp_interp.variables[param] = args[i] if i < len(args) else None
        
        # Выполняем тело функции как БЛОК, а не построчно
        result = temp_interp.execute_block(func_info['body'])
        
        return result

    def _parse_arguments(self, args_str: str, context: Dict) -> List[Any]:
        if not args_str.strip():
            return []
        args = []
        current = ''
        paren = bracket = brace = 0
        in_string = False
        quote = None
        for ch in args_str:
            if ch in ('"', "'") and not in_string:
                in_string = True
                quote = ch
                current += ch
            elif ch == quote and in_string:
                in_string = False
                quote = None
                current += ch
            elif in_string:
                current += ch
            elif ch == '(':
                paren += 1
                current += ch
            elif ch == ')':
                paren -= 1
                current += ch
            elif ch == '[':
                bracket += 1
                current += ch
            elif ch == ']':
                bracket -= 1
                current += ch
            elif ch == '{':
                brace += 1
                current += ch
            elif ch == '}':
                brace -= 1
                current += ch
            elif ch == ',' and paren == 0 and bracket == 0 and brace == 0:
                if current.strip():
                    args.append(self.evaluate_expression(current.strip(), context))
                current = ''
            else:
                current += ch
        if current.strip():
            args.append(self.evaluate_expression(current.strip(), context))
        return args

    def execute_line(self, line: str) -> Any:
        line = line.strip()
        line = self._strip_comments(line)
        if not line:
            return None

        logger.debug(f"Execute line: {line}")

        if line.startswith('import '):
            module_name = line[7:].rstrip(';').strip()
            
            if self._import_flash_module(module_name):
                if module_name in self.flash_modules:
                    mod = self.flash_modules[module_name]
                    for func_name, func in mod.get('functions', {}).items():
                        self.functions[f"{module_name}.{func_name}"] = func
                    for func_name, func in mod.get('python_functions', {}).items():
                        self.python_functions[f"{module_name}.{func_name}"] = func
                    for var_name, val in mod.get('variables', {}).items():
                        self.variables[f"{module_name}.{var_name}"] = val
                    for class_name, cls in mod.get('classes', {}).items():
                        self.classes[f"{module_name}.{class_name}"] = cls
            elif module_name not in self.modules:
                try:
                    self.modules[module_name] = __import__(module_name)
                    logger.info(f"Imported Python module: {module_name}")
                except ImportError:
                    logger.error(f"Module '{module_name}' not found")
            return None

        if line.startswith('new '):
            line = line.rstrip(';')
            return self.evaluate_expression(line)

        if line.startswith('var '):
            content = line[4:].rstrip(';')
            if '=' in content:
                parts = content.split('=', 1)
                var_name = parts[0].strip()
                value = self.evaluate_expression(parts[1].strip())
                self.variables[var_name] = value
                logger.debug(f"Variable set: {var_name} = {value}")
            return None

        if '(' in line and line.endswith(';') and not line.startswith('var ') and not line.startswith('print(') and not line.startswith('if ') and not line.startswith('for ') and not line.startswith('while ') and not line.startswith('return '):
            line = line.rstrip(';')
            return self.evaluate_expression(line)

        if line.startswith('print(') and line.endswith(');'):
            expr = line[6:-2].strip()
            value = self.evaluate_expression(expr)
            if value is not None:
                print(value)
            return None

        if '=' in line and '[' in line and line.endswith(';'):
            line = line.rstrip(';')
            parts = line.split('=', 1)
            left = parts[0].strip()
            val = self.evaluate_expression(parts[1].strip())
            bracket_pos = left.find('[')
            arr_name = left[:bracket_pos].strip()
            idx_str = left[bracket_pos + 1:-1].strip()
            arr = self._get_variable(arr_name)
            idx = self.evaluate_expression(idx_str)
            if isinstance(arr, list):
                arr[idx] = val
                logger.debug(f"Array set: {arr_name}[{idx}] = {val}")
            return val

        if '=' in line and line.endswith(';'):
            line = line.rstrip(';')
            parts = line.split('=', 1)
            name = parts[0].strip()
            val = self.evaluate_expression(parts[1].strip())

            if '.' in name:
                obj_parts = name.split('.')
                if obj_parts[0] == 'this':
                    obj = self.locals.get('this')
                    if obj and isinstance(obj, dict) and '_class' in obj:
                        obj['_fields'][obj_parts[1]] = val
                        logger.debug(f"Field set: {name} = {val}")
                        return val

            if name in self.locals:
                self.locals[name] = val
            else:
                self.variables[name] = val
            logger.debug(f"Variable set: {name} = {val}")
            return val

        if line.startswith('return '):
            expr = line[7:].rstrip(';').strip()
            self.return_value = self.evaluate_expression(expr) if expr else None
            logger.debug(f"Return: {self.return_value}")
            return self.return_value

        return None

    def _extract_block(self, lines: List[str], start_idx: int) -> Tuple[List[str], int]:
        block = []
        i = start_idx
        depth = 0

        line = lines[i].strip()
        if '{' in line:
            depth = 1
            after = line.split('{', 1)[1].strip()
            if after and after != '}':
                block.append(after)
            if '}' in after:
                depth -= after.count('}')
            i += 1

        while i < len(lines) and depth > 0:
            line = lines[i].strip()

            if line.startswith('} else if ') or line.startswith('} else {'):
                break

            depth += line.count('{') - line.count('}')
            if depth > 0:
                block.append(line)
            else:
                if '}' in line:
                    before = line.split('}', 1)[0].strip()
                    if before:
                        block.append(before)
            i += 1

        return block, i

    def _extract_python_block(self, lines: List[str], start_idx: int) -> Tuple[List[str], int]:
        block = []
        i = start_idx
        depth = 0

        line = lines[i].strip()
        if '{' in line:
            depth = 1
            after = line.split('{', 1)[1].strip()
            if after and after != '}':
                block.append(after)
            i += 1

        while i < len(lines) and depth > 0:
            line = lines[i].rstrip('\n')
            depth += line.count('{') - line.count('}')
            if depth > 0:
                block.append(line)
            i += 1

        return block, i

    def _extract_python_blocks(self, code: str) -> List[str]:
        blocks = []
        i = 0
        while i < len(code):
            if code[i:i + 7] == 'python ':
                j = i + 7
                while j < len(code) and code[j] in ' \t\n':
                    j += 1
                if j < len(code) and code[j] == '{':
                    brace_count = 1
                    k = j + 1
                    while k < len(code) and brace_count > 0:
                        if code[k] == '{':
                            brace_count += 1
                        elif code[k] == '}':
                            brace_count -= 1
                        k += 1
                    if brace_count == 0:
                        block = code[j + 1:k - 1]
                        blocks.append(block)
                    i = k
                    continue
            i += 1
        return blocks

    def execute_block(self, lines: List[str]) -> Any:
        if isinstance(lines, str):
            lines = lines.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i]

            if self._is_comment(line):
                i += 1
                continue

            line = line.strip()
            if not line:
                i += 1
                continue

            # Collect decorators
            decorators = []
            while line.startswith('@'):
                decorator_name = line[1:].strip()
                decorators.append(decorator_name)
                i += 1
                if i >= len(lines):
                    break
                line = lines[i].strip()
                if not line.startswith('@') and not line.startswith('func '):
                    break

            if line.startswith('if '):
                cond_str = line[3:].split('{')[0].strip()
                if cond_str.startswith('(') and cond_str.endswith(')'):
                    cond_str = cond_str[1:-1]
                condition = self.evaluate_expression(cond_str)

                block, next_i = self._extract_block(lines, i)

                if condition:
                    self.execute_block(block)
                    self.skip_else = True
                else:
                    self.skip_else = False

                i = next_i
                continue

            if line.startswith('} else if '):
                if not self.skip_else:
                    cond_str = line[10:].split('{')[0].strip()
                    if cond_str.startswith('(') and cond_str.endswith(')'):
                        cond_str = cond_str[1:-1]
                    condition = self.evaluate_expression(cond_str)

                    block, next_i = self._extract_block(lines, i)
                    if condition:
                        self.execute_block(block)
                        self.skip_else = True
                    i = next_i
                else:
                    _, next_i = self._extract_block(lines, i)
                    i = next_i
                continue

            if line.startswith('} else {'):
                if not self.skip_else:
                    block, next_i = self._extract_block(lines, i)
                    self.execute_block(block)
                    i = next_i
                else:
                    _, next_i = self._extract_block(lines, i)
                    i = next_i
                continue

            if line.startswith('for '):
                match = re.match(r'for\s+(\w+)\s+in\s+(.+?)\s*\{', line)
                if match:
                    var = match.group(1)
                    iterable_expr = match.group(2).strip()
                    iterable = self.evaluate_expression(iterable_expr)
                    block, next_i = self._extract_block(lines, i)
                    
                    for item in iterable:
                        # Сохраняем старое значение если было
                        old_value = self.variables.get(var)
                        self.variables[var] = item
                        # Добавляем в locals для видимости в выражениях
                        self.locals[var] = item
                        self.execute_block(block)
                        # Восстанавливаем
                        if old_value is not None:
                            self.variables[var] = old_value
                            self.locals[var] = old_value
                        else:
                            if var in self.variables:
                                del self.variables[var]
                            if var in self.locals:
                                del self.locals[var]
                    
                    i = next_i
                    continue

            if line.startswith('class '):
                match = re.match(r'class\s+(\w+)\s*\{?', line)
                if match:
                    class_name = match.group(1)
                    class_body, next_i = self._extract_block(lines, i)
                    fields = {}
                    methods = {}
                    constructor = None
                    ci = 0
                    while ci < len(class_body):
                        class_line = class_body[ci].strip()
                        if class_line.startswith('var '):
                            content = class_line[4:].rstrip(';')
                            if '=' in content:
                                parts = content.split('=', 1)
                                field_name = parts[0].strip()
                                default_value = self.evaluate_expression(parts[1].strip())
                                fields[field_name] = {'default': default_value}
                            else:
                                fields[content] = {'default': None}
                            ci += 1
                            continue
                        if class_line.startswith('constructor'):
                            match_con = re.match(r'constructor\s*\(([^)]*)\)', class_line)
                            if match_con:
                                params_str = match_con.group(1)
                                params = [p.strip() for p in params_str.split(',') if p.strip()] if params_str else []
                                con_body, skip = self._extract_block(class_body, ci)
                                constructor = {'params': params, 'body': con_body}
                                ci += len(con_body) + 1
                            else:
                                con_body, skip = self._extract_block(class_body, ci)
                                constructor = {'params': [], 'body': con_body}
                                ci += len(con_body) + 1
                            continue
                        if class_line.startswith('func '):
                            method_decorators = []
                            # Check for decorators on method
                            temp_ci = ci
                            while temp_ci > 0 and class_body[temp_ci - 1].strip().startswith('@'):
                                method_decorators.append(class_body[temp_ci - 1].strip()[1:])
                                temp_ci -= 1
                            
                            match_method = re.match(r'func\s+(\w+)\s*\(([^)]*)\)', class_line)
                            if match_method:
                                method_name = match_method.group(1)
                                params_str = match_method.group(2)
                                params = [p.strip() for p in params_str.split(',') if p.strip()] if params_str else []
                                method_body, skip = self._extract_block(class_body, ci)
                                methods[method_name] = {
                                    'params': params,
                                    'body': method_body,
                                    'decorators': list(reversed(method_decorators))
                                }
                                ci += len(method_body) + 1
                            continue
                        ci += 1
                    self.classes[class_name] = {
                        'fields': fields,
                        'methods': methods,
                        'constructor': constructor
                    }
                    logger.info(f"Class '{class_name}' defined")
                    i = next_i
                    continue

            if line.startswith('func '):
                match = re.match(r'func\s+(\w+)\s*\(([^)]*)\)\s*\{?', line)
                if match:
                    name = match.group(1)
                    params = [p.strip() for p in match.group(2).split(',') if p.strip()]
                    body, next_i = self._extract_block(lines, i)
                    
                    self.functions[name] = {
                        'params': params,
                        'body': body,
                        'decorators': decorators
                    }
                    
                    if decorators:
                        logger.info(f"Function '{name}' defined with decorators {decorators}")
                    else:
                        logger.info(f"Function '{name}' defined")
                    
                    i = next_i
                    continue

            if line.startswith('python '):
                if '{' in line:
                    py_lines, next_i = self._extract_python_block(lines, i)
                else:
                    py_lines = []
                    next_i = i + 1
                    while next_i < len(lines) and lines[next_i].strip():
                        py_lines.append(lines[next_i])
                        next_i += 1

                dedented = self._dedent_lines(py_lines)
                py_code = '\n'.join(dedented)

                try:
                    exec_globals = {}
                    exec(py_code, exec_globals)

                    for name, obj in exec_globals.items():
                        if not name.startswith('_'):
                            if isinstance(obj, type):
                                self.python_classes[name] = obj
                                logger.info(f"Registered Python class: {name}")
                            elif callable(obj):
                                self.python_functions[name] = obj
                                logger.info(f"Registered Python function: {name}")
                except Exception as e:
                    logger.error(f"Python block error: {e}")
                    if self.debug:
                        traceback.print_exc()

                i = next_i
                continue

            if line == '}':
                i += 1
                continue

            self.execute_line(line)
            if self.return_value is not None:
                return self.return_value
            i += 1

        return None

    def execute(self, code: str) -> Any:
        self.skip_else = False
        lines = code.split('\n')
        return self.execute_block(lines)


def run_example(debug=False):
    code = '''
python {
def greet_py(name):
    return f"Hello from Python, {name}!"
}

@log
func say_hello(name) {
    return "Hello, " + name;
}

@log
@timer
func slow_function(n) {
    var result = 0;
    for i in range(n) {
        result = result + i;
    }
    return result;
}

@deprecated
func old_function() {
    return "This is old";
}

class Person {
    var name = "";
    var age = 0;
    
    constructor(name, age) {
        this.name = name;
        this.age = age;
    }
    
    @log
    func introduce() {
        print("I'm " + this.name + ", " + this.age + " years old");
    }
}

var person = new Person("Alice", 25);
person.introduce();

var message = say_hello("FlashLang");
print(message);

var sum = slow_function(1000);
print("Sum: " + sum);

var old_msg = old_function();
print(old_msg);

var a = 10;
var b = 3;
var quotient = a / b;
print("Quotient: " + quotient);

var py_msg = greet_py("FlashLang");
print(py_msg);
'''
    print("\n" + "=" * 50)
    print("RUNNING EXAMPLE WITH DECORATORS")
    print("=" * 50 + "\n")

    interpreter = FlashLangInterpreter(debug=debug)
    interpreter.execute(code)


if __name__ == "__main__":
    debug = "--debug" in sys.argv
    args = [arg for arg in sys.argv[1:] if arg != "--debug"]

    if debug:
        logger.setLevel(logging.DEBUG)

    if len(args) > 0:
        print(f"\n{'=' * 50}")
        print(f"RUNNING {args[0]}")
        print(f"{'=' * 50}\n")

        with open(args[0], 'r', encoding='utf-8') as f:
            code = f.read()

        interpreter = FlashLangInterpreter(debug=debug)
        interpreter.execute(code)
    else:
        run_example(debug)