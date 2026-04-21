#!/usr/bin/env python3
"""
FlashLang Language Interpreter - Версия 1.0
- Классы из версии 0.2 (РАБОТАЮТ!)
- Python блоки
- if/else if/else
- Массивы, JSON
- Импорт модулей
"""

import os
import sys
import re
import json
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import math
import random

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
        self._setup_builtins()
    
    def _setup_builtins(self):
        self.modules['math'] = math
        self.modules['random'] = random
        self.modules['json'] = json
    
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
    
    def _get_variable(self, name: str, context: Dict = None) -> Any:
        if context is None:
            context = {}
        if name in context: return context[name]
        if name in self.locals: return self.locals[name]
        if name in self.variables: return self.variables[name]
        if name in self.modules: return self.modules[name]
        if name in self.python_functions: return self.python_functions[name]
        if name in self.python_classes: return self.python_classes[name]
        if name in self.classes: return self.classes[name]
        return None
    
    def _evaluate_simple(self, expr: str, context: Dict) -> Any:
        expr = expr.strip()
        
        if expr.lstrip('-').replace('.', '').isdigit():
            return float(expr) if '.' in expr else int(expr)
        
        if (expr.startswith('"') and expr.endswith('"')) or (expr.startswith("'") and expr.endswith("'")):
            return expr[1:-1]
        
        if expr.lower() == 'true': return True
        if expr.lower() == 'false': return False
        if expr.lower() == 'null': return None
        
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
                    elif isinstance(obj, dict):
                        return obj.get(parts[1])
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
        
        if expr.lower() == 'true': return True
        if expr.lower() == 'false': return False
        if expr.lower() == 'null': return None
        
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
        
        if '(' in expr and expr.endswith(')'):
            return self._parse_and_call(expr, context)
        
        if '+' in expr:
            parts = self._split_by_plus_outside_parens(expr)
            if len(parts) > 1:
                result = ''
                for part in parts:
                    val = self.evaluate_expression(part.strip(), context)
                    if val is not None:
                        result += str(val)
                return result
        
        if (expr.startswith('"') and expr.endswith('"')) or (expr.startswith("'") and expr.endswith("'")):
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
            else:
                obj = self._get_variable(parts[0], context)
                if obj:
                    if isinstance(obj, dict) and '_class' in obj:
                        if len(parts) > 1 and parts[1] in obj['_fields']:
                            return obj['_fields'][parts[1]]
                    elif isinstance(obj, dict):
                        return obj.get(parts[1])
                return None
        
        result = self._get_variable(expr, context)
        if result is not None:
            return result
        
        return expr
    
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
                    with open(module_file, 'r', encoding='utf-8') as f:
                        code = f.read()
                    
                    old_functions = self.functions.copy()
                    old_variables = self.variables.copy()
                    old_classes = self.classes.copy()
                    old_python_funcs = self.python_functions.copy()
                    
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
                    
                    new_python_funcs = {}
                    for name, func in self.python_functions.items():
                        if name not in old_python_funcs:
                            new_python_funcs[name] = func
                    
                    self.flash_modules[module_name] = {
                        'functions': new_functions,
                        'variables': new_variables,
                        'classes': new_classes,
                        'python_functions': new_python_funcs,
                    }
                    
                    print(f"[FlashLang] Imported: {module_name}")
                    return True
                    
                except Exception as e:
                    print(f"Error importing '{module_name}': {e}")
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
                            
                            self._debug_print(f"Executing method {method_name}")
                            for line in method['body']:
                                self.execute_line(line)
                                if self.return_value is not None:
                                    break
                            
                            result = self.return_value
                            self.locals = old_locals
                            self.return_value = old_return
                            return result
        
        # Обычный вызов
        paren_pos = expr.find('(')
        if paren_pos != -1:
            name = expr[:paren_pos].strip()
            args_str = expr[paren_pos+1:-1].strip()
            
            if name == 'print':
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
                if len(args) == 1: return list(range(args[0]))
                elif len(args) == 2: return list(range(args[0], args[1]))
                return []
            if name == 'json_parse':
                val = self.evaluate_expression(args_str, context)
                return json.loads(val) if val else {}
            if name == 'json_stringify':
                val = self.evaluate_expression(args_str, context)
                return json.dumps(val) if val else "{}"
            
            args = self._parse_arguments(args_str, context)
            
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
                    self.modules[module_name] = __import__(module98)
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
            idx_str = left[bracket_pos+1:-1].strip()
            arr = self._get_variable(arr_name)
            idx = self.evaluate_expression(idx_str)
            if isinstance(arr, list):
                arr[idx] = val
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
                        return val
            
            if name in self.locals:
                self.locals[name] = val
            else:
                self.variables[name] = val
            return val
        
        if line.startswith('return '):
            expr = line[7:].rstrip(';').strip()
            self.return_value = self.evaluate_expression(expr) if expr else None
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
            if '}' in after:
                depth -= after.count('}')
            i += 1
        
        while i < len(lines) and depth > 0:
            line = lines[i].rstrip('\n')
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
                    iterable = self.evaluate_expression(match.group(2))
                    block, next_i = self._extract_block(lines, i)
                    for item in iterable:
                        self.variables[var] = item
                        self.execute_block(block)
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
                match = re.match(r'func\s+(\w+)\s*\(([^)]*)\)\s*\{?', line)
                if match:
                    name = match.group(1)
                    params = [p.strip() for p in match.group(2).split(',') if p.strip()]
                    body, next_i = self._extract_block(lines, i)
                    self.functions[name] = {'params': params, 'body': body}
                    print(f"[FlashLang] Function '{name}' defined")
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
                    exec_globals = {**self.modules, **self.variables}
                    exec(py_code, exec_globals)
                    
                    for name, obj in exec_globals.items():
                        if not name.startswith('_') and name not in self.modules:
                            if isinstance(obj, type):
                                self.python_classes[name] = obj
                                print(f"[FlashLang] Registered Python class: {name}")
                            elif callable(obj):
                                self.python_functions[name] = obj
                                print(f"[FlashLang] Registered Python function: {name}")
                except Exception as e:
                    print(f"Python block error: {e}")
                
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

class Person {
    var name = "";
    var age = 0;
    
    constructor(name, age) {
        this.name = name;
        this.age = age;
    }
    
    func introduce() {
        print("I'm " + this.name + ", " + this.age + " years old");
    }
}

var person = new Person("Alice", 25);
person.introduce();

var arr = [10, 20, 30];
arr[1] = 99;
print("Array: " + arr);

var score = 85;
if (score >= 90) {
    print("Grade A");
} else if (score >= 80) {
    print("Grade B");
} else {
    print("Grade C");
}

var py_msg = greet_py("FlashLang");
print(py_msg);
'''
    
    print("=== FLASHLANG v1.0 ===\n")
    interpreter = FlashLangInterpreter(debug=debug)
    interpreter.execute(code)


if __name__ == "__main__":
    debug = "--debug" in sys.argv
    args = [arg for arg in sys.argv[1:] if arg != "--debug"]
    
    if len(args) > 0:
        with open(args[0], 'r', encoding='utf-8') as f:
            code = f.read()
        print(f"=== Running {args[0]} ===\n")
        interpreter = FlashLangInterpreter(debug=debug)
        interpreter.execute(code)
    else:
        run_example(debug)