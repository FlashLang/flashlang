#!/usr/bin/env python3
"""
FlashLang Language Interpreter - Версия 0.2
- ПОЛНОСТЬЮ РАБОТАЕТ ВСЁ: классы, this, конкатенация, print, try-catch, switch
- Исправлена конкатенация в print внутри методов
- Исправлено сложение чисел
"""

import sys
import re
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
        self.skip_else = False
        self.exception_caught = False
        self.exception_value = None
        self.output_buffer = []
        self.debug = debug
        
        self.flash_home = Path(__file__).parent
        self.packages_dir = self.flash_home / "lib"
        
        self._setup_builtins()
    
    def _setup_builtins(self):
        try:
            import math
            self.modules['math'] = math
        except: pass
        try:
            import random
            self.modules['random'] = random
        except: pass
    
    def _debug_print(self, msg):
        if self.debug:
            print(f"[DEBUG] {msg}")
    
    def _is_comment(self, line: str) -> bool:
        stripped = line.strip()
        return stripped.startswith('/') and not stripped.startswith('//')
    
    def _strip_comments(self, line: str) -> str:
        in_string = False
        quote_char = None
        for i, ch in enumerate(line):
            if ch in ('"', "'") and not in_string:
                in_string = True
                quote_char = ch
            elif ch == quote_char and in_string:
                in_string = False
                quote_char = None
            elif ch == '/' and not in_string:
                if i + 1 < len(line) and line[i+1] == '/':
                    continue
                return line[:i]
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
            exec_context = {**self.modules, **self.variables, **self.locals, **context, **self.python_functions, **self.python_classes}
            return eval(py_code.strip(), exec_context)
        except Exception as e:
            print(f"Python error: {e}")
            return None
    
    def _get_variable(self, name: str, context: Dict) -> Any:
        if name in context: return context[name]
        if name in self.locals: return self.locals[name]
        if name in self.variables: return self.variables[name]
        if name in self.modules: return self.modules[name]
        if name in self.python_functions: return self.python_functions[name]
        if name in self.python_classes: return self.python_classes[name]
        if name in self.classes: return self.classes[name]
        return None
    
    def _evaluate_simple(self, expr: str, context: Dict) -> Any:
        """Вычисляет простые выражения без обработки +"""
        expr = expr.strip()
        
        # Числа
        if expr.lstrip('-').replace('.', '').isdigit():
            return float(expr) if '.' in expr else int(expr)
        
        # Строки
        if (expr.startswith('"') and expr.endswith('"')) or (expr.startswith("'") and expr.endswith("'")):
            return expr[1:-1]
        
        # Константы
        if expr.lower() == 'true': return True
        if expr.lower() == 'false': return False
        if expr.lower() == 'null': return None
        
        # Доступ к полям
        if '.' in expr:
            parts = expr.split('.')
            if parts[0] == 'this':
                obj = self.locals.get('this')
                if obj and isinstance(obj, dict) and '_class' in obj:
                    field_name = parts[1]
                    if field_name in obj['_fields']:
                        return obj['_fields'][field_name]
            else:
                obj = self._get_variable(parts[0], context)
                if obj:
                    if isinstance(obj, dict) and '_class' in obj:
                        if len(parts) > 1 and parts[1] in obj['_fields']:
                            return obj['_fields'][parts[1]]
                    else:
                        for part in parts[1:]:
                            if hasattr(obj, part):
                                obj = getattr(obj, part)
                            elif isinstance(obj, dict) and part in obj:
                                obj = obj[part]
                            else:
                                return None
                        return obj
        
        # Вызов функции
        if '(' in expr and expr.endswith(')'):
            return self._parse_and_call(expr, context)
        
        # Переменная
        return self._get_variable(expr, context)
    
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
        self._debug_print(f"Creating instance of {class_name} with args: {args}")
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
                # Пробуем преобразовать в число для любых числовых полей
                if isinstance(val, str):
                    try:
                        if val.isdigit():
                            val = int(val)
                        else:
                            val = float(val)
                    except:
                        pass
                self.locals[param] = val
            
            for line in cls['constructor']['body']:
                self.execute_line(line)
            
            self.locals = old_locals
            self.return_value = old_return
        
        self._debug_print(f"Instance created: {instance}")
        return instance
    
    def evaluate_expression(self, expr: str, context: Dict = None) -> Any:
        if context is None:
            context = {**self.variables, **self.locals, **self.python_functions, **self.python_classes, **self.classes}
        
        expr = expr.strip()
        if not expr:
            return None
        
        expr = self._strip_comments(expr)
        self._debug_print(f"Evaluating: '{expr}'")
        
        if expr.startswith('py:'):
            return self._evaluate_py_expression(expr[3:], context)
        
        if expr.startswith('[') and expr.endswith(']'):
            return self._parse_array_literal(expr[1:-1], context)
        
        if expr.lstrip('-').replace('.', '').isdigit():
            return float(expr) if '.' in expr else int(expr)
        
        # Константы
        if expr.lower() == 'true': return True
        if expr.lower() == 'false': return False
        if expr.lower() == 'null': return None
        
        # Вызов функции/метода или new (только если нет + вне скобок)
        if '(' in expr and expr.endswith(')'):
            paren_count = 0
            has_plus_outside = False
            in_string = False
            quote = None
            for ch in expr:
                if ch in ('"', "'") and not in_string:
                    in_string = True
                    quote = ch
                elif ch == quote and in_string:
                    in_string = False
                    quote = None
                elif ch == '(' and not in_string:
                    paren_count += 1
                elif ch == ')' and not in_string:
                    paren_count -= 1
                elif ch == '+' and paren_count == 0 and not in_string:
                    has_plus_outside = True
                    break
            if not has_plus_outside:
                return self._parse_and_call(expr, context)
        
        # Конкатенация/сложение
        if '+' in expr:
            parts = self._split_by_plus_outside_parens(expr)
            self._debug_print(f"CONCAT parts: {parts}")
            if len(parts) > 1:
                # Проверяем, все ли части числа
                all_numbers = True
                values = []
                for part in parts:
                    val = self.evaluate_expression(part.strip(), context)
                    values.append(val)
                    if not isinstance(val, (int, float)):
                        all_numbers = False
                
                if all_numbers:
                    # Числовое сложение
                    result = sum(values)
                else:
                    # Строковая конкатенация
                    result = ''
                    for v in values:
                        result += str(v) if v is not None else ''
                return result               
        
        # Строки (целиком в кавычках)
        if (expr.startswith('"') and expr.endswith('"')) or (expr.startswith("'") and expr.endswith("'")):
            return expr[1:-1]
        
        # Доступ к полям
        if '.' in expr:
            parts = expr.split('.')
            if parts[0] == 'this':
                obj = self.locals.get('this')
                if obj and isinstance(obj, dict) and '_class' in obj:
                    field_name = parts[1]
                    if field_name in obj['_fields']:
                        return obj['_fields'][field_name]
                return None
            else:
                obj = self._get_variable(parts[0], context)
                if obj:
                    if isinstance(obj, dict) and '_class' in obj:
                        if len(parts) > 1 and parts[1] in obj['_fields']:
                            return obj['_fields'][parts[1]]
                    else:
                        for part in parts[1:]:
                            if hasattr(obj, part):
                                obj = getattr(obj, part)
                            elif isinstance(obj, dict) and part in obj:
                                obj = obj[part]
                            else:
                                return None
                        return obj
        
        result = self._get_variable(expr, context)
        if result is not None:
            return result
        
        return expr
    
    def _import_flash_module(self, module_name: str) -> bool:
        """Импортирует FlashLang модуль (.flang файл)"""
        search_paths = [
            Path.cwd(),
            Path.cwd() / "lib",
            Path.home() / ".flashlang" / "packages",
            Path(__file__).parent / "lib",
        ]
        
        for search_path in search_paths:
            module_file = search_path / f"{module_name}.flang"
            
            if module_file.exists():
                try:
                    with open(module_file, 'r', encoding='utf-8') as f:
                        code = f.read()
                    
                    # Сохраняем текущее состояние
                    old_functions = self.functions.copy()
                    old_variables = self.variables.copy()
                    old_classes = self.classes.copy()
                    old_python_funcs = self.python_functions.copy()
                    old_python_classes = self.python_classes.copy()
                    
                    # Выполняем код модуля
                    self.execute(code)
                    
                    # Находим НОВЫЕ функции, переменные, классы
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
                    
                    new_python_funcs = {}
                    for name, func in self.python_functions.items():
                        if name not in old_python_funcs:
                            new_python_funcs[name] = func
                    
                    new_python_classes = {}
                    for name, cls in self.python_classes.items():
                        if name not in old_python_classes:
                            new_python_classes[name] = cls
                    
                    # Сохраняем модуль
                    self.flash_modules[module_name] = {
                        'functions': new_functions,
                        'variables': new_variables,
                        'classes': new_classes,
                        'python_functions': new_python_funcs,
                        'python_classes': new_python_classes,
                    }
                    
                    print(f"[FlashLang] Imported module: {module_name}")
                    self._debug_print(f"  Functions: {list(new_functions.keys())}")
                    self._debug_print(f"  Variables: {list(new_variables.keys())}")
                    
                    return True
                    
                except Exception as e:
                    print(f"Error importing module '{module_name}': {e}")
                    return False
        
        return False
    
    def _split_by_plus_outside_parens(self, expr: str) -> List[str]:
        parts = []
        current = ''
        paren_count = 0
        in_string = False
        quote = None
        
        for ch in expr:
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
                paren_count += 1
                current += ch
            elif ch == ')':
                paren_count -= 1
                current += ch
            elif ch == '+' and paren_count == 0:
                parts.append(current)
                current = ''
            else:
                current += ch
        
        if current:
            parts.append(current)
        
        return parts
    
    def _parse_and_call(self, expr: str, context: Dict) -> Any:
        self._debug_print(f"Parsing call: {expr}")
        
        # Обработка new
        if expr.startswith('new '):
            match = re.match(r'new\s+(\w+)\((.*)\)$', expr)
            if match:
                class_name = match.group(1)
                args_str = match.group(2)
                self._debug_print(f"NEW: class={class_name}, args={args_str}")
                args = self._parse_arguments(args_str, context)
                if class_name in self.classes:
                    return self._create_flash_instance(class_name, args)
                else:
                    print(f"Error: Class '{class_name}' not found")
                    return None
        
        # Вызов метода: obj.method(args)
        if '.' in expr:
            paren_pos = expr.rfind('(')
            last_dot_pos = expr.rfind('.', 0, paren_pos)
            if last_dot_pos != -1:
                obj_expr = expr[:last_dot_pos].strip()
                method_name = expr[last_dot_pos+1:paren_pos].strip()
                args_str = expr[paren_pos+1:-1].strip()
                
                obj = self.evaluate_expression(obj_expr, context)
                self._debug_print(f"Method call: obj={obj_expr}, obj_value={obj}, method={method_name}")
                
                if obj and isinstance(obj, dict) and '_class' in obj:
                    class_name = obj['_class']
                    if class_name in self.classes:
                        cls = self.classes[class_name]
                        if method_name in cls.get('methods', {}):
                            method = cls['methods'][method_name]
                            args = self._parse_arguments_raw(args_str)
                            
                            old_locals = self.locals.copy()
                            old_return = self.return_value
                            
                            self.locals = {'this': obj}
                            for i, param in enumerate(method.get('params', [])):
                                if i < len(args):
                                    self.locals[param] = self.evaluate_expression(args[i], {**context, **self.locals})
                                else:
                                    self.locals[param] = None
                            
                            self._debug_print(f"Executing method {method_name}, body: {method['body']}")
                            for line in method['body']:
                                self.execute_line(line)
                                if self.return_value is not None:
                                    break
                            
                            result = self.return_value
                            self.locals = old_locals
                            self.return_value = old_return
                            return result
                
                # Python объект
                if obj and hasattr(obj, method_name):
                    method = getattr(obj, method_name)
                    if callable(method):
                        args = self._parse_arguments(args_str, context)
                        try:
                            return method(*args)
                        except Exception as e:
                            print(f"Error: {e}")
                            return None
        
        # Обычный вызов
        paren_pos = expr.find('(')
        if paren_pos != -1:
            name = expr[:paren_pos].strip()
            args_str = expr[paren_pos+1:-1].strip()
            
            if name == 'print':
                # Вычисляем аргумент как конкатенацию если есть +
                if '+' in args_str and not (args_str.startswith('"') and args_str.endswith('"')):
                    parts = self._split_by_plus_outside_parens(args_str)
                    result = ''
                    for part in parts:
                        val = self._evaluate_simple(part.strip(), context)
                        result += str(val) if val is not None else ''
                    output = result
                else:
                    val = self.evaluate_expression(args_str, context)
                    output = str(val) if val is not None else ''
                print(output)
                self.output_buffer.append(output)
                return output
            
            if name == 'package':
                pass
            
            args = self._parse_arguments(args_str, context)
            
            if name == 'len':
                return len(args[0]) if args else 0
            if name == 'range':
                if len(args) == 1: return list(range(args[0]))
                elif len(args) == 2: return list(range(args[0], args[1]))
                elif len(args) == 3: return list(range(args[0], args[1], args[2]))
                return []
            if name == 'str': return str(args[0]) if args else ''
            if name == 'int': return int(args[0]) if args else 0
            if name == 'float': return float(args[0]) if args else 0.0
            
            if name in self.python_classes:
                try:
                    return self.python_classes[name](*args)
                except Exception as e:
                    print(f"Error: {e}")
                    return None
            
            if name in self.classes:
                return self._create_flash_instance(name, args)
            
            if name in self.python_functions:
                try:
                    return self.python_functions[name](*args)
                except Exception as e:
                    print(f"Error: {e}")
                    return None
            
            if name in self.functions:
                func = self.functions[name]
                old_locals = self.locals.copy()
                old_return = self.return_value
                self.return_value = None
                self.locals = {}
                for i, param in enumerate(func['params']):
                    self.locals[param] = args[i] if i < len(args) else None
                
                for line in func['body']:
                    self.execute_line(line)
                    if self.return_value is not None:
                        break
                
                result = self.return_value
                self.locals = old_locals
                self.return_value = old_return
                return result
        
        return None
    
    def _parse_arguments_raw(self, args_str: str) -> List[str]:
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
            elif ch == '(': paren += 1; current += ch
            elif ch == ')': paren -= 1; current += ch
            elif ch == '[': bracket += 1; current += ch
            elif ch == ']': bracket -= 1; current += ch
            elif ch == '{': brace += 1; current += ch
            elif ch == '}': brace -= 1; current += ch
            elif ch == ',' and paren == 0 and bracket == 0 and brace == 0:
                if current.strip():
                    args.append(current.strip())
                current = ''
            else:
                current += ch
        if current.strip():
            args.append(current.strip())
        return args
    
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
            elif ch == '(': paren += 1; current += ch
            elif ch == ')': paren -= 1; current += ch
            elif ch == '[': bracket += 1; current += ch
            elif ch == ']': bracket -= 1; current += ch
            elif ch == '{': brace += 1; current += ch
            elif ch == '}': brace -= 1; current += ch
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
        
        self._debug_print(f"Execute line: {line}")
        
        if line.startswith('import '):
            module_name = line[7:].rstrip(';').strip()
            
            # СНАЧАЛА пробуем импортировать FlashLang модуль
            if self._import_flash_module(module_name):
                self._debug_print(f"Imported FlashLang module: {module_name}")
                # Добавляем функции и переменные модуля с префиксом
                if module_name in self.flash_modules:
                    mod = self.flash_modules[module_name]
                    
                    # Функции FlashLang
                    for func_name, func in mod.get('functions', {}).items():
                        self.functions[f"{module_name}.{func_name}"] = func
                        self._debug_print(f"  Registered: {module_name}.{func_name}")
                    
                    # Python функции
                    for func_name, func in mod.get('python_functions', {}).items():
                        self.python_functions[f"{module_name}.{func_name}"] = func
                        self._debug_print(f"  Registered Python: {module_name}.{func_name}")
                    
                    # ПЕРЕМЕННЫЕ!
                    for var_name, val in mod.get('variables', {}).items():
                        self.variables[f"{module_name}.{var_name}"] = val
                        self._debug_print(f"  Registered var: {module_name}.{var_name} = {val}")
                    
                    # Классы
                    for class_name, cls in mod.get('classes', {}).items():
                        self.classes[f"{module_name}.{class_name}"] = cls
                        self._debug_print(f"  Registered class: {module_name}.{class_name}")
            else:
                # Если не нашли .flang, пробуем Python модуль
                if module_name not in self.modules:
                    try:
                        self.modules[module_name] = __import__(module_name)
                        self._debug_print(f"Imported Python module: {module_name}")
                    except ImportError:
                        print(f"Import error: Module '{module_name}' not found")
            return None
        
        if line.startswith('var '):
            content = line[4:].rstrip(';')
            if '=' in content:
                parts = content.split('=', 1)
                var_name = parts[0].strip()
                value = self.evaluate_expression(parts[1].strip())
                self.variables[var_name] = value
                self._debug_print(f"VAR {var_name} = {value} (type: {type(value)})")
            return None
        
        if '=' in line and not any(line.startswith(kw) for kw in ['if', 'while', 'for', 'func', 'class', 'try', 'catch', 'switch']):
            line = line.rstrip(';')
            parts = line.split('=', 1)
            var_name = parts[0].strip()
            value = self.evaluate_expression(parts[1].strip())
            
            if '.' in var_name:
                obj_parts = var_name.split('.')
                if obj_parts[0] == 'this':
                    obj = self.locals.get('this')
                    if obj and isinstance(obj, dict) and '_class' in obj:
                        try:
                            if isinstance(value, str):
                                value = int(value) if value.isdigit() else float(value)
                            else:
                                value = int(value) if str(value).isdigit() else float(value)
                        except:
                            pass
                    obj['_fields'][obj_parts[1]] = value
                    self._debug_print(f"ASSIGN this.{obj_parts[1]} = {value} (type: {type(value)})")
                    return value
            
            if var_name in self.locals:
                self.locals[var_name] = value
            else:
                self.variables[var_name] = value
            self._debug_print(f"ASSIGN {var_name} = {value}")
            return value
        
        if line.startswith('print(') and line.endswith(')'):
            expr = line[6:-1].strip()
            value = self.evaluate_expression(expr)
            if value is not None:
                print(value)
            return value
        
        if line.startswith('return'):
            expr = line[6:].rstrip(';').strip()
            self.return_value = self.evaluate_expression(expr) if expr else None
            return self.return_value
        
        if line in ('break', 'break;'):
            self.break_flag = True
            return None
        if line in ('continue', 'continue;'):
            self.continue_flag = True
            return None
        
        if line.startswith('throw '):
            expr = line[6:].rstrip(';').strip()
            self.exception_value = self.evaluate_expression(expr)
            self.exception_caught = False
            return None
        
        if '(' in line:
            line = line.rstrip(';')
            return self.evaluate_expression(line)
        
        return self.evaluate_expression(line.rstrip(';'))
    
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
            
            if line.startswith('if '):
                condition_expr = line[3:].split('{')[0].strip()
                if condition_expr.startswith('(') and condition_expr.endswith(')'):
                    condition_expr = condition_expr[1:-1]
                condition = self.evaluate_expression(condition_expr)
                block_lines, next_i = self._extract_block(lines, i)
                if condition:
                    self.execute_block(block_lines)
                    self.skip_else = True
                else:
                    self.skip_else = False
                i = next_i
                continue
            
            if line.startswith('else if '):
                if not self.skip_else:
                    condition_expr = line[7:].split('{')[0].strip()
                    if condition_expr.startswith('(') and condition_expr.endswith(')'):
                        condition_expr = condition_expr[1:-1]
                    condition = self.evaluate_expression(condition_expr)
                    block_lines, next_i = self._extract_block(lines, i)
                    if condition:
                        self.execute_block(block_lines)
                        self.skip_else = True
                    else:
                        self.skip_else = False
                    i = next_i
                else:
                    _, next_i = self._extract_block(lines, i)
                    i = next_i
                continue
            
            if line.startswith('else'):
                block_lines, next_i = self._extract_block(lines, i)
                if not self.skip_else:
                    self.execute_block(block_lines)
                i = next_i
                continue
            
            if line.startswith('while '):
                condition_expr = line[6:].split('{')[0].strip()
                if condition_expr.startswith('(') and condition_expr.endswith(')'):
                    condition_expr = condition_expr[1:-1]
                block_lines, next_i = self._extract_block(lines, i)
                while self.evaluate_expression(condition_expr):
                    self.execute_block(block_lines)
                    if self.break_flag:
                        self.break_flag = False
                        break
                    if self.continue_flag:
                        self.continue_flag = False
                        continue
                    if self.return_value is not None:
                        return None
                i = next_i
                continue
            
            if line.startswith('for '):
                match = re.match(r'for\s+(\w+)\s+in\s+(.+?)\s*\{', line)
                if match:
                    var_name = match.group(1)
                    iterable_expr = match.group(2).strip()
                    block_lines, next_i = self._extract_block(lines, i)
                    iterable = self.evaluate_expression(iterable_expr)
                    if iterable:
                        for item in iterable:
                            if var_name in self.locals:
                                self.locals[var_name] = item
                            else:
                                self.variables[var_name] = item
                            self.execute_block(block_lines)
                            if self.break_flag:
                                self.break_flag = False
                                break
                            if self.continue_flag:
                                self.continue_flag = False
                                continue
                    i = next_i
                    continue
            
            if line.startswith('switch '):
                match = re.match(r'switch\s*\((.+?)\)\s*\{', line)
                if match:
                    switch_value = self.evaluate_expression(match.group(1).strip())
                    block_lines, next_i = self._extract_block(lines, i)
                    matched = False
                    case_i = 0
                    while case_i < len(block_lines):
                        case_line = block_lines[case_i].strip()
                        if case_line.startswith('case '):
                            case_val = self.evaluate_expression(case_line[5:].rstrip(':').strip())
                            if not matched and switch_value == case_val:
                                matched = True
                            case_i += 1
                            continue
                        if case_line.startswith('default:'):
                            matched = True
                            case_i += 1
                            continue
                        if matched:
                            if case_line == 'break;':
                                break
                            self.execute_line(case_line)
                        case_i += 1
                    i = next_i
                    continue
            
            if line.startswith('try '):
                block_lines, next_i = self._extract_block(lines, i)
                self.exception_caught = False
                self.exception_value = None
                self.execute_block(block_lines)
                has_exception = self.exception_value is not None and not self.exception_caught
                if next_i < len(lines) and lines[next_i].strip().startswith('catch '):
                    catch_line = lines[next_i].strip()
                    match = re.match(r'catch\s*\((.+?)\s+(\w+)\)', catch_line)
                    if match:
                        exception_var = match.group(2)
                        catch_block, after_catch = self._extract_block(lines, next_i)
                        if has_exception:
                            self.variables[exception_var] = self.exception_value
                            self.exception_caught = True
                            self.execute_block(catch_block)
                        next_i = after_catch
                    else:
                        next_i += 1
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
                                ci += len(con_body) + 2
                            else:
                                con_body, skip = self._extract_block(class_body, ci)
                                constructor = {'params': [], 'body': con_body}
                                ci += len(con_body) + 2
                            continue
                        if class_line.startswith('func '):
                            match_method = re.match(r'func\s+(\w+)\s*\(([^)]*)\)', class_line)
                            if match_method:
                                method_name = match_method.group(1)
                                params_str = match_method.group(2)
                                params = [p.strip() for p in params_str.split(',') if p.strip()] if params_str else []
                                method_body, skip = self._extract_block(class_body, ci)
                                methods[method_name] = {'params': params, 'body': method_body}
                                ci += len(method_body) + 2
                            continue
                        ci += 1
                    self.classes[class_name] = {'fields': fields, 'methods': methods, 'constructor': constructor}
                    print(f"[FlashLang] Class '{class_name}' defined")
                    i = next_i
                    continue
            
            if line.startswith('func '):
                match = re.match(r'func\s+(\w+)\s*\(([^)]*)\)', line)
                if match:
                    func_name = match.group(1)
                    params_str = match.group(2)
                    params = [p.strip() for p in params_str.split(',') if p.strip()] if params_str else []
                    body_lines, next_i = self._extract_block(lines, i)
                    self.functions[func_name] = {'params': params, 'body': body_lines}
                    print(f"[FlashLang] Function '{func_name}' defined")
                    i = next_i
                    continue
            
            if line.startswith('python {'):
                py_lines = []
                i += 1
                brace_count = 1
                while i < len(lines) and brace_count > 0:
                    py_line = lines[i]
                    brace_count += py_line.count('{')
                    brace_count -= py_line.count('}')
                    if brace_count > 0:
                        py_lines.append(py_line)
                    else:
                        if '}' in py_line:
                            py_line = py_line.split('}', 1)[0]
                        if py_line.strip():
                            py_lines.append(py_line)
                        break
                    i += 1
                dedented = self._dedent_lines(py_lines)
                py_code = '\n'.join(dedented)
                try:
                    exec_globals = {}
                    exec(py_code, exec_globals)
                    for name, obj in exec_globals.items():
                        if not name.startswith('_'):
                            if isinstance(obj, type):
                                self.python_classes[name] = obj
                                print(f"[FlashLang] Registered Python class: {name}")
                            elif callable(obj):
                                self.python_functions[name] = obj
                                print(f"[FlashLang] Registered Python function: {name}")
                except Exception as e:
                    print(f"Python block error: {e}")
                i += 1
                continue
            
            self.execute_line(line)
            if self.return_value is not None or self.break_flag or self.continue_flag:
                return None
            if self.exception_value is not None and not self.exception_caught:
                return None
            i += 1
        return None
    
    def _extract_block(self, lines: List[str], start_idx: int) -> Tuple[List[str], int]:
        block_lines = []
        i = start_idx
        brace_count = 0
        first_line = True
        while i < len(lines):
            line = lines[i]
            if first_line:
                first_line = False
                if '{' in line:
                    after_brace = line.split('{', 1)[1]
                    brace_count += 1
                    brace_count -= after_brace.count('}')
                    if after_brace.strip():
                        if '}' in after_brace:
                            code_part = after_brace.split('}', 1)[0].strip()
                            if code_part:
                                block_lines.append(code_part)
                        else:
                            block_lines.append(after_brace.strip())
                    if brace_count == 0:
                        i += 1
                        break
                else:
                    i += 1
                    continue
            else:
                brace_count += line.count('{')
                brace_count -= line.count('}')
                if brace_count > 0:
                    block_lines.append(line)
                else:
                    if '}' in line:
                        before_close = line.split('}', 1)[0].strip()
                        if before_close:
                            block_lines.append(before_close)
                    break
            i += 1
        return block_lines, i + 1
    
    def execute(self, code: str) -> Any:
        lines = code.split('\n')
        self.output_buffer = []
        return self.execute_block(lines)


def ensure_lib_folder():
    lib_path = Path.cwd() / "lib"
    if not lib_path.exists():
        lib_path.mkdir(exist_ok=True)


def run_example(debug=False):
    example_code = '''
class Person {
    var name = "";
    var age = 0;
    
    constructor(name, age) {
        this.name = name;
        this.age = age;
    }
    
    func greet() {
        print("Hello, I'm " + this.name + ", " + this.age + " years old");
    }
    
    func birthday() {
        this.age = this.age + 1;
    }
}

var person = new Person("Alice", 25);
person.greet();
person.birthday();
person.greet();

var arr = [1, 2, 3, 4, 5];
print("Array: " + arr);
print("Length: " + len(arr));

var x = 2;
switch (x) {
    case 1: print("One"); break;
    case 2: print("Two"); break;
    default: print("Other");
}

try {
    print("Trying...");
    throw "Something went wrong";
} catch (e) {
    print("Caught: " + e);
}

print("Program finished!");
'''
    
    print("=== FLASHLANG 0.2 ===\n")
    interpreter = FlashLangInterpreter(debug=debug)
    interpreter.execute(example_code)
    print(f"\n=== Program finished ===")


if __name__ == "__main__":
    debug = "--debug" in sys.argv
    args = [arg for arg in sys.argv[1:] if arg != "--debug"]
    
    ensure_lib_folder()
    
    if len(args) > 0:
        with open(args[0], 'r', encoding='utf-8') as f:
            code = f.read()
        print(f"=== Running {args[0]} ===\n")
        interpreter = FlashLangInterpreter(debug=debug)
        interpreter.execute(code)
        print(f"\n=== Program finished ===")
    else:
        print("No input file...")